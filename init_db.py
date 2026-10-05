"""Create the database, tables, sample data and the two default logins."""
import os, pymysql
from werkzeug.security import generate_password_hash
from dbconfig import DB_NAME, conn_kwargs

conn = pymysql.connect(**conn_kwargs())
with conn.cursor() as c:
    try:
        c.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4")
    except pymysql.MySQLError:
        pass  # hosted databases already exist and may not allow this
    conn.select_db(DB_NAME)
    script = open(os.path.join(os.path.dirname(__file__), "schema.sql"), encoding="utf8").read()
    for stmt in script.split(";\n"):
        s = stmt.strip()
        if s and not s.upper().startswith(("CREATE DATABASE", "USE ")):
            c.execute(s)
    # Set OWNER_PASSWORD / STAFF_PASSWORD to choose real passwords (also updates existing logins)
    for u, env, n in [("owner", "OWNER_PASSWORD", "Owner"), ("staff", "STAFF_PASSWORD", "Staff")]:
        pw = os.getenv(env)
        verb = "INSERT INTO" if pw else "INSERT IGNORE INTO"
        tail = " ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash)" if pw else ""
        c.execute(f"{verb} users (username, password_hash, full_name, role) VALUES (%s,%s,%s,%s){tail}",
                  (u, generate_password_hash(pw or u + "123"), n, u))
    c.execute("SELECT COUNT(*) n FROM customers")
    if c.fetchone()[0] == 0:  # sample customers only on a fresh database
        c.executemany("INSERT INTO customers (name,type,phone,address,discount_pct) VALUES (%s,%s,%s,%s,%s)", [
            ("Maria Santos", "Regular", "0917 123 4567", "Phase 1, Bagong Silang, Caloocan", 0),
            ("Carinderia ni Aling Nena", "Business", "0928 555 0102", "Zabarte Rd, Caloocan", 5),
            ("Kuya Jun Bakery", "Business", "0935 222 8890", "Camarin, Caloocan", 5)])
conn.commit()
print("Database ready. Logins: owner / owner123  and  staff / staff123 (change these!)")
