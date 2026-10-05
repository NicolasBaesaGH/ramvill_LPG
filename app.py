import csv, io, os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps

import pymysql
from pymysql.cursors import DictCursor
from flask import (Flask, Response, g, jsonify, redirect, render_template,
                   request, session, url_for)
from flask.json.provider import DefaultJSONProvider
from werkzeug.security import check_password_hash

from dbconfig import DB_NAME, conn_kwargs

BORROW_DAYS = 7


def today_ph():
    """Today's date in the Philippines (servers like Render run on UTC)."""
    return datetime.now(timezone(timedelta(hours=8))).date()
  # days before a borrowed tank becomes overdue


def _default(o):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat(sep=" ") if isinstance(o, datetime) else o.isoformat()
    return DefaultJSONProvider.default(o)


class Provider(DefaultJSONProvider):
    default = staticmethod(_default)


app = Flask(__name__)
app.json = Provider(app)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")


# ---------- database helpers ----------
def db():
    if "db" not in g:
        g.db = pymysql.connect(**conn_kwargs(), database=DB_NAME, cursorclass=DictCursor,
                               init_command="SET time_zone='+08:00'")
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def q(sql, args=(), one=False):
    with db().cursor() as c:
        c.execute(sql, args)
        rows = c.fetchall()
    db().commit()
    return (rows[0] if rows else None) if one else rows


def status_of(qty, low, crit):
    return "Critical" if qty <= crit else "Low Stock" if qty <= low else "In Stock"


def refresh_overdue():
    """Same job as the scheduled Power Automate flow: flag late tanks."""
    q("UPDATE tank_records SET status='Overdue' WHERE status='Borrowed' AND expected_return_date < CURDATE()")


# ---------- auth ----------
def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if "uid" not in session:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in again."), 401
            return redirect(url_for("login"))
        return f(*a, **k)
    return wrapper


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **k):
        if session.get("role") != "admin":
            return jsonify(error="Only the admin can do this."), 403
        return f(*a, **k)
    return wrapper


@app.context_processor
def inject_user():
    return dict(user_name=session.get("name", ""), role=session.get("role", ""))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        u = q("SELECT * FROM users WHERE username=%s", (request.form.get("username", "").strip(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session.update(uid=u["id"], role=u["role"], name=u["full_name"])
            return redirect(url_for("dashboard"))
        error = "Wrong username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- pages ----------
def page(name, tpl):
    @login_required
    def view():
        return render_template(tpl, page=name)
    view.__name__ = f"page_{name}"
    return view


for _path, _name, _tpl in [("/", "dashboard", "dashboard.html"), ("/order", "order", "pos.html"),
                           ("/inventory", "inventory", "inventory.html"), ("/customers", "customers", "customers.html"),
                           ("/tanks", "tanks", "tanks.html"), ("/delivery", "delivery", "delivery.html"),
                           ("/reports", "reports", "reports.html")]:
    app.add_url_rule(_path, _name, page(_name, _tpl))


# ---------- dashboard ----------
@app.get("/api/dashboard")
@login_required
def api_dashboard():
    refresh_overdue()
    d = request.args.get("date") or today_ph().isoformat()
    stock = q("SELECT COALESCE(SUM(full_qty),0) f, COALESCE(SUM(empty_qty),0) e FROM products", one=True)
    sales = q("SELECT COUNT(*) n, COALESCE(SUM(total),0) s FROM orders WHERE status<>'Cancelled' AND DATE(created_at)=%s", (d,), one=True)
    low = [dict(p, status=status_of(p["full_qty"], p["low_level"], p["critical_level"]))
           for p in q("SELECT * FROM products WHERE full_qty <= low_level ORDER BY full_qty")]
    pending = q("""SELECT t.id, c.name customer, p.brand, p.size_kg, t.qty, t.expected_return_date, t.status
                   FROM tank_records t JOIN customers c ON c.id=t.customer_id JOIN products p ON p.id=t.product_id
                   WHERE t.status IN ('Borrowed','Overdue') ORDER BY t.expected_return_date""")
    return jsonify(full=stock["f"], empty=stock["e"], sales=sales["s"], orders=sales["n"], low=low, pending=pending)


# ---------- products / inventory ----------
@app.get("/api/products")
@login_required
def api_products():
    return jsonify(q("SELECT id, brand, size_kg, price FROM products ORDER BY brand, size_kg"))


@app.get("/api/inventory")
@login_required
def api_inventory():
    kind = request.args.get("kind", "Full")
    col = "empty_qty" if kind == "Empty" else "full_qty"
    sql, args = "SELECT * FROM products WHERE 1=1", []
    if request.args.get("q"):
        sql += " AND (brand LIKE %s OR size_kg LIKE %s)"
        args += [f"%{request.args['q']}%"] * 2
    if request.args.get("brand"):
        sql += " AND brand=%s"
        args.append(request.args["brand"])
    if request.args.get("size"):
        sql += " AND size_kg=%s"
        args.append(request.args["size"])
    rows = q(sql + " ORDER BY brand, size_kg", args)
    for r in rows:
        r["qty"] = r[col]
        r["status"] = status_of(r[col], r["low_level"], r["critical_level"])
    return jsonify(rows=rows, full=sum(r["full_qty"] for r in rows),
                   empty=sum(r["empty_qty"] for r in rows),
                   total=sum(r["full_qty"] + r["empty_qty"] for r in rows))


@app.post("/api/inventory/<int:pid>/add-stock")
@login_required
def api_add_stock(pid):
    d = request.get_json(force=True)
    qty = int(d.get("qty") or 0)
    if qty < 1:
        return jsonify(error="Enter a quantity of 1 or more."), 400
    col = "empty_qty" if d.get("kind") == "Empty" else "full_qty"
    q(f"UPDATE products SET {col}={col}+%s WHERE id=%s", (qty, pid))
    return jsonify(ok=True)


# ---------- customers ----------
def clean_customer(d):
    name = (d.get("name") or "").strip()
    ctype = d.get("type") if d.get("type") in ("Regular", "Business") else "Regular"
    if not name:
        return None
    disc = d.get("discount_pct")
    disc = Decimal(str(disc)) if disc not in (None, "") else Decimal("5" if ctype == "Business" else "0")
    return (name, ctype, (d.get("phone") or "").strip(), (d.get("address") or "").strip(), disc)


@app.get("/api/customers")
@login_required
def api_customers():
    s = f"%{request.args.get('q', '')}%"
    return jsonify(q("""
        SELECT c.*, COUNT(DISTINCT o.id) orders, COALESCE(SUM(o.total),0) total_purchases,
          (SELECT COALESCE(SUM(qty),0) FROM tank_records t WHERE t.customer_id=c.id AND t.status IN ('Borrowed','Overdue')) tanks_borrowed
        FROM customers c LEFT JOIN orders o ON o.customer_id=c.id AND o.status<>'Cancelled'
        WHERE c.name LIKE %s OR c.phone LIKE %s GROUP BY c.id ORDER BY c.name""", (s, s)))


@app.post("/api/customers")
@login_required
def api_add_customer():
    vals = clean_customer(request.get_json(force=True))
    if not vals:
        return jsonify(error="Customer name is required."), 400
    with db().cursor() as c:
        c.execute("INSERT INTO customers (name,type,phone,address,discount_pct) VALUES (%s,%s,%s,%s,%s)", vals)
        cid = c.lastrowid
    db().commit()
    return jsonify(q("SELECT * FROM customers WHERE id=%s", (cid,), one=True))


@app.put("/api/customers/<int:cid>")
@login_required
def api_edit_customer(cid):
    vals = clean_customer(request.get_json(force=True))
    if not vals:
        return jsonify(error="Customer name is required."), 400
    q("UPDATE customers SET name=%s,type=%s,phone=%s,address=%s,discount_pct=%s WHERE id=%s", vals + (cid,))
    return jsonify(ok=True)


@app.get("/api/customers/<int:cid>/orders")
@login_required
def api_customer_orders(cid):
    return jsonify(q("SELECT id, created_at, total, fulfillment, status FROM orders WHERE customer_id=%s ORDER BY created_at DESC", (cid,)))


# ---------- orders ----------
@app.post("/api/orders")
@login_required
def api_create_order():
    d = request.get_json(force=True)
    items = d.get("items") or []
    cust = q("SELECT * FROM customers WHERE id=%s", (d.get("customer_id"),), one=True)
    fulfil = "Delivery" if d.get("fulfillment") == "Delivery" else "Pick-up"
    addr = (d.get("address") or "").strip()
    if not cust or not items:
        return jsonify(error="Choose a customer and add at least one item."), 400
    if fulfil == "Delivery" and not addr:
        return jsonify(error="Enter a delivery address."), 400
    cur = db().cursor()
    try:
        lines, subtotal = [], Decimal(0)
        for it in items:
            qty = int(it["qty"])
            cur.execute("SELECT * FROM products WHERE id=%s FOR UPDATE", (it["product_id"],))
            p = cur.fetchone()
            if not p or qty < 1:
                raise ValueError("Invalid item in order.")
            if p["full_qty"] < qty:
                raise ValueError(f"Not enough stock for {p['brand']} {p['size_kg']:g}kg. Only {p['full_qty']} full left.")
            returned = bool(it.get("empty_returned"))
            subtotal += qty * p["price"]
            # Power Automate step 3: deduct full cylinders, add returned empties
            cur.execute("UPDATE products SET full_qty=full_qty-%s, empty_qty=empty_qty+%s WHERE id=%s",
                        (qty, qty if returned else 0, p["id"]))
            lines.append((p, qty, returned))
        discount = (subtotal * cust["discount_pct"] / 100).quantize(Decimal("0.01"))
        cur.execute("INSERT INTO orders (customer_id,user_id,subtotal,discount,total,fulfillment,address) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (cust["id"], session["uid"], subtotal, discount, subtotal - discount, fulfil, addr if fulfil == "Delivery" else None))
        oid = cur.lastrowid
        for p, qty, returned in lines:
            cur.execute("INSERT INTO order_items (order_id,product_id,qty,unit_price,empty_returned) VALUES (%s,%s,%s,%s,%s)",
                        (oid, p["id"], qty, p["price"], returned))
            if not returned:  # no empty tank handed back -> borrowed tank record
                cur.execute("INSERT INTO tank_records (customer_id,order_id,product_id,qty,borrowed_date,expected_return_date) VALUES (%s,%s,%s,%s,CURDATE(),CURDATE()+INTERVAL %s DAY)",
                            (cust["id"], oid, p["id"], qty, BORROW_DAYS))
        db().commit()
    except (ValueError, KeyError, TypeError) as e:
        db().rollback()
        return jsonify(error=str(e)), 400
    finally:
        cur.close()
    return jsonify(id=oid, total=subtotal - discount)


@app.get("/api/orders")
@login_required
def api_orders():
    sql = """SELECT o.*, c.name customer, c.type customer_type, c.phone, c.address customer_address,
               GROUP_CONCAT(CONCAT(oi.qty,' x ',p.brand,' ',CAST(p.size_kg AS DOUBLE),'kg') SEPARATOR ', ') items
             FROM orders o JOIN customers c ON c.id=o.customer_id
             JOIN order_items oi ON oi.order_id=o.id JOIN products p ON p.id=oi.product_id WHERE 1=1"""
    args = []
    if request.args.get("status"):
        sql += " AND o.status=%s"
        args.append(request.args["status"])
    if request.args.get("q"):
        sql += " AND (c.name LIKE %s OR o.id=%s)"
        args += [f"%{request.args['q']}%", request.args["q"] if request.args["q"].isdigit() else 0]
    return jsonify(q(sql + " GROUP BY o.id ORDER BY o.created_at DESC LIMIT 200", args))


@app.put("/api/orders/<int:oid>")
@login_required
def api_update_order(oid):
    d = request.get_json(force=True)
    fulfil = "Delivery" if d.get("fulfillment") == "Delivery" else "Pick-up"
    addr = (d.get("address") or "").strip()
    if fulfil == "Delivery" and not addr:
        return jsonify(error="Enter a delivery address."), 400
    q("UPDATE orders SET fulfillment=%s, address=%s WHERE id=%s AND status='Pending'", (fulfil, addr if fulfil == "Delivery" else None, oid))
    return jsonify(ok=True)


@app.post("/api/orders/<int:oid>/complete")
@login_required
def api_complete_order(oid):
    q("UPDATE orders SET status='Completed' WHERE id=%s AND status='Pending'", (oid,))
    return jsonify(ok=True)


@app.post("/api/orders/<int:oid>/cancel")
@login_required
def api_cancel_order(oid):
    cur = db().cursor()
    try:
        cur.execute("SELECT status FROM orders WHERE id=%s FOR UPDATE", (oid,))
        o = cur.fetchone()
        if not o or o["status"] != "Pending":
            return jsonify(error="Only pending orders can be cancelled."), 400
        cur.execute("SELECT * FROM order_items WHERE order_id=%s", (oid,))
        for it in cur.fetchall():  # put the stock back
            cur.execute("UPDATE products SET full_qty=full_qty+%s, empty_qty=GREATEST(empty_qty-%s,0) WHERE id=%s",
                        (it["qty"], it["qty"] if it["empty_returned"] else 0, it["product_id"]))
        cur.execute("DELETE FROM tank_records WHERE order_id=%s AND status<>'Returned'", (oid,))
        cur.execute("UPDATE orders SET status='Cancelled' WHERE id=%s", (oid,))
        db().commit()
    finally:
        cur.close()
    return jsonify(ok=True)


# ---------- tanks ----------
def tank_query(args):
    sql = """SELECT t.id, c.name customer, c.phone, p.brand, p.size_kg, t.qty, t.borrowed_date,
               t.expected_return_date, t.returned_date, t.status
             FROM tank_records t JOIN customers c ON c.id=t.customer_id JOIN products p ON p.id=t.product_id WHERE 1=1"""
    a = []
    if args.get("status") and args["status"] != "All":
        sql += " AND t.status=%s"
        a.append(args["status"])
    if args.get("q"):
        sql += " AND c.name LIKE %s"
        a.append(f"%{args['q']}%")
    if args.get("from"):
        sql += " AND t.borrowed_date>=%s"
        a.append(args["from"])
    if args.get("to"):
        sql += " AND t.borrowed_date<=%s"
        a.append(args["to"])
    return q(sql + " ORDER BY t.borrowed_date DESC, t.id DESC", a)


@app.get("/api/tanks")
@login_required
def api_tanks():
    refresh_overdue()
    s = q("""SELECT COUNT(*) total, COALESCE(SUM(status='Borrowed'),0) borrowed,
             COALESCE(SUM(status='Returned'),0) returned, COALESCE(SUM(status='Overdue'),0) overdue FROM tank_records""", one=True)
    return jsonify(rows=tank_query(request.args), summary=s)


@app.post("/api/tanks/<int:tid>/return")
@login_required
def api_return_tank(tid):
    cur = db().cursor()
    try:
        cur.execute("SELECT * FROM tank_records WHERE id=%s FOR UPDATE", (tid,))
        t = cur.fetchone()
        if not t or t["status"] == "Returned":
            return jsonify(error="This tank is already marked as returned."), 400
        cur.execute("UPDATE tank_records SET status='Returned', returned_date=CURDATE() WHERE id=%s", (tid,))
        cur.execute("UPDATE products SET empty_qty=empty_qty+%s WHERE id=%s", (t["qty"], t["product_id"]))
        db().commit()
    finally:
        cur.close()
    return jsonify(ok=True)


# ---------- sales ----------
def period():
    to = date.fromisoformat(request.args.get("to") or today_ph().isoformat())
    fr = date.fromisoformat(request.args.get("from") or (to - timedelta(days=29)).isoformat())
    return fr, to


def totals(fr, to):
    return q("SELECT COUNT(*) n, COALESCE(SUM(total),0) s FROM orders WHERE status<>'Cancelled' AND DATE(created_at) BETWEEN %s AND %s", (fr, to), one=True)


@app.get("/api/sales")
@login_required
def api_sales():
    fr, to = period()
    cur = totals(fr, to)
    days = (to - fr).days + 1
    prev_to = fr - timedelta(days=1)
    prev = totals(prev_to - timedelta(days=days - 1), prev_to)
    by_product = q("""SELECT CONCAT(p.brand,' ',CAST(p.size_kg AS DOUBLE),'kg') product, SUM(oi.qty) qty, SUM(oi.qty*oi.unit_price) revenue
        FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN products p ON p.id=oi.product_id
        WHERE o.status<>'Cancelled' AND DATE(o.created_at) BETWEEN %s AND %s GROUP BY p.id ORDER BY revenue DESC""", (fr, to))
    daily = q("""SELECT DATE(created_at) day, SUM(total) sales, COUNT(*) orders FROM orders
        WHERE status<>'Cancelled' AND DATE(created_at) BETWEEN %s AND %s GROUP BY day ORDER BY day""", (fr, to))
    avg = cur["s"] / cur["n"] if cur["n"] else 0
    change = ((cur["s"] - prev["s"]) / prev["s"] * 100) if prev["s"] else None
    return jsonify(total_sales=cur["s"], total_orders=cur["n"], average=avg, previous_sales=prev["s"],
                   change_pct=change, by_product=by_product, daily=daily)


# ---------- reports (admin only) ----------
@app.get("/api/reports/<kind>")
@admin_required
def api_report(kind):
    fr, to = period()
    if kind == "inventory":
        rows = [{"Brand": p["brand"], "Size (kg)": f"{p['size_kg']:g}", "Full": p["full_qty"], "Empty": p["empty_qty"],
                 "Total": p["full_qty"] + p["empty_qty"], "Status": status_of(p["full_qty"], p["low_level"], p["critical_level"])}
                for p in q("SELECT * FROM products ORDER BY brand, size_kg")]
    elif kind == "customers":
        rows = [{"Customer": r["name"], "Type": r["type"], "Phone": r["phone"], "Address": r["address"],
                 "Orders": r["n"], "Total Purchases": f"{r['s']:.2f}"} for r in q("""
            SELECT c.name, c.type, c.phone, c.address, COUNT(o.id) n, COALESCE(SUM(o.total),0) s FROM customers c
            LEFT JOIN orders o ON o.customer_id=c.id AND o.status<>'Cancelled' AND DATE(o.created_at) BETWEEN %s AND %s
            GROUP BY c.id ORDER BY s DESC""", (fr, to))]
    elif kind == "tanks":
        refresh_overdue()
        rows = [{"Customer": t["customer"], "Brand": t["brand"], "Size (kg)": f"{t['size_kg']:g}", "Qty": t["qty"],
                 "Borrowed": t["borrowed_date"], "Expected Return": t["expected_return_date"],
                 "Returned": t["returned_date"] or "", "Status": t["status"]}
                for t in tank_query({"from": fr.isoformat(), "to": to.isoformat()})]
    else:
        return jsonify(error="Unknown report."), 404
    columns = list(rows[0].keys()) if rows else []
    if request.args.get("format") == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=columns or ["No data"])
        w.writeheader()
        w.writerows(rows)
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={kind}_report_{fr}_{to}.csv"})
    return jsonify(columns=columns, rows=rows)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
