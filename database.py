import sqlite3
import random

DB_NAME = "channel_cart.db"

def init_db():
    """Initializes database tables for orders and products."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            buyer_id INTEGER,
            username TEXT,
            product_id TEXT,
            quantity TEXT,
            latitude REAL,
            longitude REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Products Table for Management
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            title TEXT,
            price TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_latest_order_counter():
    """Finds the highest existing order number to prevent duplicate IDs."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT order_id FROM orders ORDER BY created_at DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0].startswith("ORD-"):
        try:
            return int(row[0].split("-")[1])
        except ValueError:
            return 1000
    return 1000

def get_next_item_id():
    """Generates a random unique product item ID."""
    return f"ITEM-{random.randint(1000, 9999)}"

def save_product(product_id, title, price):
    """Saves a newly posted product into the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO products (product_id, title, price) VALUES (?, ?, ?)', (product_id, title, price))
    conn.commit()
    conn.close()

def get_all_products():
    """Retrieves all active products."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT product_id, title, price, created_at FROM products ORDER BY created_at DESC')
    products = cursor.fetchall()
    conn.close()
    return products

def delete_product(product_id):
    """Deletes a product from database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE product_id = ?', (product_id,))
    conn.commit()
    conn.close()

def save_order(order_id, buyer_id, username, product_id, quantity, lat, lng):
    """Saves a new order into the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (order_id, buyer_id, username, product_id, quantity, latitude, longitude, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, buyer_id, username, product_id, quantity, lat, lng, "Pending"))
    conn.commit()
    conn.close()

def update_order_status(order_id, status):
    """Updates the status of an existing order."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', (status, order_id))
    conn.commit()
    conn.close()

def get_order(order_id):
    """Retrieves order details by Order ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
    order = cursor.fetchone()
    conn.close()
    return order

def get_all_orders():
    """Retrieves all orders from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT order_id, product_id, quantity, status, created_at FROM orders ORDER BY created_at DESC')
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_sales_stats():
    """Calculates analytics and order statistics."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM orders')
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Completed'")
    completed_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'")
    pending_orders = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Rejected'")
    rejected_orders = cursor.fetchone()[0]

    conn.close()
    return total_orders, completed_orders, pending_orders, rejected_orders