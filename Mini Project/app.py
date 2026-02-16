from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)

# Database connection helper
def get_db_connection():
    # Use relative path for flexibility
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Vendor page
@app.route('/vendor', methods=['GET', 'POST'])
def vendor():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        location = request.form['location']

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO food (name, discounted_price, location, status) VALUES (?, ?, ?, ?)",
            (name, price, location, 'available')
        )
        conn.commit()
        conn.close()

        return redirect(url_for('vendor_dashboard'))

    return render_template('vendor.html')

# Vendor Dashboard
@app.route('/vendor/dashboard')
def vendor_dashboard():
    conn = get_db_connection()
    food_items = conn.execute(
        "SELECT * FROM food WHERE status='available' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    
    return render_template('vendor_dashboard.html', food_items=food_items)

# Delete food item
@app.route('/vendor/delete/<int:id>', methods=['POST'])
def delete_food(id):
    conn = get_db_connection()
    conn.execute("UPDATE food SET status='deleted' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('vendor_dashboard'))

# User page
@app.route('/user')
def user():
    search_food = request.args.get('food', '')
    search_location = request.args.get('location', '')
    
    conn = get_db_connection()
    
    query = "SELECT * FROM food WHERE status='available'"
    params = []
    
    if search_food:
        query += " AND name LIKE ?"
        params.append(f'%{search_food}%')
    
    if search_location:
        query += " AND location LIKE ?"
        params.append(f'%{search_location}%')
    
    query += " ORDER BY created_at DESC"
    
    foods = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('user.html', foods=foods)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)