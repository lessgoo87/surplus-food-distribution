from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit 
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'sunset_servings_key_123'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*") 

# ================= DATABASE CONNECTION =================
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    conn = sqlite3.connect(db_path, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

# ================= BASIC PAGES =================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/restaurant")
def restaurant_home():
    return render_template("restaurant_home.html")

@app.route("/customer/home")
def customer_home():
    food_query = request.args.get('food', '')
    location_query = request.args.get('location', '')
    
    conn = get_db_connection()
    query = "SELECT * FROM food WHERE status='available'"
    params = []

    if food_query:
        query += " AND name LIKE ?"
        params.append(f'%{food_query}%')
    
    if location_query:
        query += " AND location LIKE ?"
        params.append(f'%{location_query}%')

    query += " ORDER BY id DESC"
    foods = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("customer_home.html", foods=foods)

# ================= VENDOR DASHBOARD =================
@app.route("/vendor/dashboard", methods=['GET', 'POST'])
def vendor_dashboard():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        location = request.form.get('location')

        if name and price and location:
            conn.execute(
                "INSERT INTO food (name, discounted_price, location, status) VALUES (?, ?, ?, ?)",
                (name, price, location, 'available')
            )
            conn.commit()
            conn.close()
            flash(f"Successfully listed {name}!")
            return redirect(url_for('vendor_dashboard'))
        else:
            flash("All fields are required!")

    food_items = conn.execute("SELECT * FROM food WHERE status='available' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("vendor_dashboard.html", food_items=food_items)

# ================= CUSTOMER ORDERING LOGIC =================

@app.route('/order_item/<int:food_id>', methods=['POST'])
def order_item(food_id):
    conn = get_db_connection()
    try:
        food = conn.execute("SELECT * FROM food WHERE id = ?", (food_id,)).fetchone()
        if food:
            conn.execute("UPDATE food SET status = 'sold' WHERE id = ?", (food_id,))
            conn.commit()
            amount = food['discounted_price']
            food_name = food['name']
            conn.close() 
            
            socketio.emit('new_order_alert', {
                'message': f"New order received for {food_name}!",
                'amount': amount
            })
            return redirect(url_for('order_success', amount=amount))
        conn.close()
        return redirect(url_for('customer_home'))
    except Exception:
        if conn: conn.close()
        flash("System busy, please try again.")
        return redirect(url_for('customer_home'))

@app.route('/order/success')
def order_success():
    amount = request.args.get('amount', '0.00')
    return render_template("order_success.html", amount=amount)

# ================= LOGIN / REGISTER =================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # CHANGED: Added 'name' to capture from your register.html form
        name = request.form.get('name') 
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        try:
            # CHANGED: Inserting name along with email and password
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", 
                         (name, email, password))
            conn.commit()
            conn.close()
            flash("Registration successful! Please login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            if conn: conn.close()
            flash("Email already registered.")
        except Exception:
            if conn: conn.close()
            flash("An error occurred. Please try again.")
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            return redirect(url_for("customer_home"))
        flash("Invalid login credentials")
    return render_template("login.html")

@app.route('/restaurant/login', methods=['GET', 'POST'])
def restaurant_login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        res = conn.execute("SELECT * FROM restaurants WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if res:
            return redirect(url_for("vendor_dashboard"))
        flash("Invalid restaurant login")
    return render_template("restaurant_login.html")

@app.route('/restaurant/register', methods=['GET', 'POST'])
def restaurant_register():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        category = request.form.get('category')
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO restaurants (name, address, category, phone, email, password) VALUES (?, ?, ?, ?, ?, ?)",
                (name, address, category, phone, email, password)
            )
            conn.commit()
            conn.close()
            flash("Registration successful!")
            return redirect(url_for("restaurant_login"))
        except:
            if conn: conn.close()
            flash("Registration failed.")
    return render_template("restaurant_register.html")

@app.route('/vendor/delete/<int:id>', methods=['POST'])
def delete_food(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM food WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Item removed.")
    return redirect(url_for("vendor_dashboard"))

if __name__ == "__main__":
    socketio.run(app, debug=True)