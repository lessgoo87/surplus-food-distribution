import sqlite3
import os

# Define database path
db_path = os.path.join(os.path.dirname(__file__), 'database.db')

# Force a clean start by removing the old DB if it exists
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print("Existing database removed.")
    except PermissionError:
        print("❌ ERROR: Close your Flask server or DB viewers before running this!")
        exit()

conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Create users table
c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )''')

# 2. Create restaurants table with lat and lon
c.execute('''CREATE TABLE IF NOT EXISTS restaurants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                category TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                lat REAL,
                lon REAL
            )''')

# 3. Create food table
c.execute('''CREATE TABLE IF NOT EXISTS food (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_id INTEGER,
                name TEXT NOT NULL,
                discounted_price REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'available',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(restaurant_id) REFERENCES restaurants(id)
            )''')

# 4. Create orders table for Token System
c.execute('''CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                food_id INTEGER,
                restaurant_id INTEGER,
                quantity INTEGER NOT NULL,
                total_price REAL NOT NULL,
                token TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(food_id) REFERENCES food(id),
                FOREIGN KEY(restaurant_id) REFERENCES restaurants(id)
            )''')

conn.commit()
conn.close()

print("✅ Database created successfully with LAT/LON columns and the Orders table!")