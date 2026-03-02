import sqlite3
import os

def add_location_columns():
    # Get the path to your database
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Starting database migration...")
    
    try:
        # Add Latitude column
        cursor.execute("ALTER TABLE restaurants ADD COLUMN lat REAL")
        print("Successfully added 'lat' column.")
    except sqlite3.OperationalError:
        print("Column 'lat' already exists.")

    try:
        # Add Longitude column
        cursor.execute("ALTER TABLE restaurants ADD COLUMN lon REAL")
        print("Successfully added 'lon' column.")
    except sqlite3.OperationalError:
        print("Column 'lon' already exists.")

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    add_location_columns()