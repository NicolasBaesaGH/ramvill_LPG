CREATE DATABASE IF NOT EXISTS ramvill_lpg CHARACTER SET utf8mb4;
USE ramvill_lpg;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(100) NOT NULL,
  role ENUM('admin','staff') NOT NULL DEFAULT 'staff'
);

CREATE TABLE IF NOT EXISTS customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  type ENUM('Regular','Business') NOT NULL DEFAULT 'Regular',
  phone VARCHAR(30),
  address VARCHAR(255),
  discount_pct DECIMAL(5,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  brand VARCHAR(50) NOT NULL,
  size_kg DECIMAL(5,1) NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  full_qty INT NOT NULL DEFAULT 0,
  empty_qty INT NOT NULL DEFAULT 0,
  low_level INT NOT NULL DEFAULT 10,
  critical_level INT NOT NULL DEFAULT 3,
  UNIQUE KEY uq_brand_size (brand, size_kg)
);

CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  user_id INT,
  subtotal DECIMAL(10,2) NOT NULL,
  discount DECIMAL(10,2) NOT NULL DEFAULT 0,
  total DECIMAL(10,2) NOT NULL,
  fulfillment ENUM('Pick-up','Delivery') NOT NULL DEFAULT 'Pick-up',
  address VARCHAR(255),
  status ENUM('Pending','Completed','Cancelled') NOT NULL DEFAULT 'Pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  qty INT NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL,
  empty_returned TINYINT(1) NOT NULL DEFAULT 0,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS tank_records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  order_id INT,
  product_id INT NOT NULL,
  qty INT NOT NULL,
  borrowed_date DATE NOT NULL,
  expected_return_date DATE NOT NULL,
  returned_date DATE,
  status ENUM('Borrowed','Returned','Overdue') NOT NULL DEFAULT 'Borrowed',
  FOREIGN KEY (customer_id) REFERENCES customers(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

INSERT IGNORE INTO products (brand, size_kg, price, full_qty, empty_qty, low_level, critical_level) VALUES
('Petron Gasul', 11, 920.00, 40, 12, 10, 3),
('Petron Gasul', 22, 1800.00, 15, 5, 6, 2),
('Petron Gasul', 50, 4100.00, 8, 2, 4, 1),
('Solane', 11, 950.00, 35, 10, 10, 3),
('Solane', 22, 1850.00, 12, 4, 6, 2),
('Solane', 50, 4200.00, 5, 1, 4, 1),
('Shellane', 11, 930.00, 8, 6, 10, 3),
('Shellane', 22, 1820.00, 2, 3, 6, 2),
('Shellane', 50, 4150.00, 6, 0, 4, 1);
