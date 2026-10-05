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
    # Migrate an older install: the 'owner' account/role becomes 'admin'
    c.execute("ALTER TABLE users MODIFY role ENUM('owner','admin','staff') NOT NULL DEFAULT 'staff'")
    c.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if c.fetchone()[0] == 0:
        c.execute("UPDATE users SET username='admin', full_name='Admin' WHERE username='owner'")
    c.execute("UPDATE users SET role='admin' WHERE role='owner'")
    c.execute("ALTER TABLE users MODIFY role ENUM('admin','staff') NOT NULL DEFAULT 'staff'")
    # Set ADMIN_PASSWORD / STAFF_PASSWORD to choose real passwords (also updates existing logins)
    for u, pw, n in [("admin", os.getenv("ADMIN_PASSWORD") or os.getenv("OWNER_PASSWORD"), "Admin"),
                     ("staff", os.getenv("STAFF_PASSWORD"), "Staff")]:
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
print("Database ready. Logins: admin and staff (passwords = ADMIN_PASSWORD / STAFF_PASSWORD you set; defaults admin123 / staff123, change them!)")
