import sqlite3
import os

# Use relative path
db_path = os.path.join(os.path.dirname(__file__), 'database.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# ⚠️ Reset food table (safe for development only)
c.execute("DROP TABLE IF EXISTS food")

# Food table
c.execute("""
CREATE TABLE IF NOT EXISTS food (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    original_price INTEGER,
    discounted_price INTEGER NOT NULL,
    quantity INTEGER DEFAULT 1,
    location TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    vendor_name TEXT,
    vendor_contact TEXT,
    dietary_tags TEXT,
    image_url TEXT,
    flash_sale INTEGER DEFAULT 0,
    pickup_deadline TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'available'
)
""")

# Vendors table (future authentication use)
c.execute("""
CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    business_name TEXT,
    contact TEXT,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Users table (future authentication use)
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    contact TEXT,
    dietary_preferences TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


    """)
# Sample data
sample_foods = [
    ('Chocolate Cake', 'Bakery', 'Fresh chocolate cake, must sell today', 300, 150, 3,
     'Edappally, Kochi', 10.0251, 76.3078, 'Sweet Treats Bakery', '9876543210',
     'Vegetarian,Contains Eggs', None, 1, '20:00', 'available'),

    ('Vegetable Biryani', 'Restaurant', 'Delicious veg biryani with raita', 250, 120, 5,
     'MG Road, Kochi', 9.9816, 76.2999, 'Spice Garden Restaurant', '9876543211',
     'Vegetarian,Vegan', None, 0, '21:00', 'available'),
    
    ('Margherita Pizza', 'Restaurant', 'Large wood-fired margherita pizza', 450, 220, 2,
     'Kaloor, Kochi', 10.0078, 76.2999, 'Italian Corner', '9876543212',
     'Vegetarian', None, 1, '22:30', 'available')
]

c.executemany("""
INSERT INTO food (
    name, category, description, original_price, discounted_price,
    quantity, location, latitude, longitude, vendor_name, vendor_contact,
    dietary_tags, image_url, flash_sale, pickup_deadline, status
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", sample_foods)

conn.commit()
conn.close()

print("✅ Database created successfully!")
print("📊 Sample data inserted")
print(f"📂 Database location: {db_path}")