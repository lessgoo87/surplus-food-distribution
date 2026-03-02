# import sqlite3
# import os

# def force_add_columns():
#     db_path = os.path.join(os.path.dirname(__file__), 'database.db')
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()
    
#     print("Checking for missing columns...")
    
#     columns = ["lat", "lon"]
#     for col in columns:
#         try:
#             # We use REAL because coordinates are decimal numbers
#             cursor.execute(f"ALTER TABLE restaurants ADD COLUMN {col} REAL")
#             print(f"Successfully added column: {col}")
#         except sqlite3.OperationalError:
#             print(f"Column {col} already exists.")

#     conn.commit()
#     conn.close()
#     print("Migration finished!")

# if __name__ == "__main__":
#     force_add_columns()