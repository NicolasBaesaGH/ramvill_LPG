# Ramvill LPG Trading: Sales and Inventory System

Flask + MySQL + HTML/CSS/JavaScript version of the "LPG Tank Tracking, Customer, and Order Management System".

## Run it
1. Install Python 3.10+ and MySQL 8 (XAMPP/MySQL Workbench works).
2. `pip install -r requirements.txt`
3. Set your MySQL login (defaults: host `localhost`, user `root`, empty password):
   `set DB_PASSWORD=yourpassword` (Windows) or `export DB_PASSWORD=yourpassword` (Mac/Linux)
4. `python init_db.py` creates the `ramvill_lpg` database, sample stock/customers and two logins.
5. `python app.py` then open http://127.0.0.1:5000

Logins (change them): `owner / owner123` and `staff / staff123`.
Owner can also generate and download reports. Staff can do everything else.

## How the Power Automate flows became code
- Place order: deducts full cylinders, adds returned empties, creates a borrowed-tank record if no empty came back (`api_create_order`)
- Overdue check: `refresh_overdue()` runs whenever the dashboard or tank pages load (due after 7 days, set `BORROW_DAYS`)
- Low/critical stock: per-product `low_level` and `critical_level` in the `products` table
- Cancel order: puts stock back and removes its borrowed-tank record
