from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from flask_socketio import SocketIO, emit 
import sqlite3
import os
import re
import secrets 
import string
from datetime import datetime 

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

# ================= VALIDATION UTILITIES =================
def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, email):
        return False, "Invalid email format."
    
    allowed_domains = ['gmail.com', 'outlook.com', 'yahoo.com', 'icloud.com']
    domain = email.split('@')[-1].lower()
    if domain not in allowed_domains:
        return False, f"Domain '@{domain}' is not supported."
    
    return True, ""

# ================= BASIC PAGES =================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/restaurant")
def restaurant_home():
    if 'restaurant_id' in session:
        return redirect(url_for('vendor_dashboard'))
    return render_template("restaurant_login.html")

@app.route("/logout")
def logout():
    session.clear() 
    flash("You have been successfully logged out.")
    response = make_response(redirect(url_for('index')))
    # Anti-Cache Headers to prevent back-button access to dashboards
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, post-check=0, pre-check=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ================= REGISTRATION LOGIC =================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not name or not email or not password:
            flash("All fields are required!")
            return redirect(url_for('register'))

        valid, msg = is_valid_email(email)
        if not valid:
            flash(msg)
            return redirect(url_for('register'))

        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                         (name, email, password))
            conn.commit()
            flash("Registration successful! Please login.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
        finally:
            conn.close()
    return render_template("register.html")

@app.route('/restaurant/register', methods=['GET', 'POST'])
def restaurant_register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        category = request.form.get('category', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        lat = request.form.get('lat')
        lon = request.form.get('lon')

        if not all([name, email, address, password, lat, lon]):
            flash("Please fill all fields and pin your location on the map!")
            return redirect(url_for('restaurant_register'))

        valid, msg = is_valid_email(email)
        if not valid:
            flash(msg)
            return redirect(url_for('restaurant_register'))

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO restaurants (name, email, address, password, category, phone, lat, lon) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, email, address, password, category, phone, lat, lon))
            conn.commit()
            flash("Restaurant registered successfully! Please login.")
            return redirect(url_for('restaurant_login'))
        except sqlite3.IntegrityError:
            flash("Email already registered for a restaurant.")
        except Exception as e:
            flash(f"Database error: {str(e)}")
        finally:
            conn.close()
    return render_template("restaurant_register.html")

# ================= CUSTOMER DASHBOARD & ORDER HISTORY =================

@app.route("/customer/home")
def customer_home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    food_query = request.args.get('food', '')
    location_query = request.args.get('location', '')
    
    conn = get_db_connection()
    query = """
        SELECT f.*, r.name as restaurant_name, r.address as location, r.lat, r.lon
        FROM food f 
        JOIN restaurants r ON f.restaurant_id = r.id 
        WHERE f.status='available' AND f.quantity > 0
    """
    params = []
    if food_query:
        query += " AND f.name LIKE ?"
        params.append(f'%{food_query}%')
    if location_query:
        query += " AND r.address LIKE ?"
        params.append(f'%{location_query}%')

    foods = conn.execute(query + " ORDER BY f.id DESC", params).fetchall()
    conn.close()

    locations_data = [
        {
            'food_name': row['name'],
            'restaurant_name': row['restaurant_name'],
            'address': row['location'],
            'lat': row['lat'],
            'lon': row['lon'],
            'price': row['discounted_price']
        } for row in foods if row['lat'] is not None
    ]

    return render_template("customer_home.html", foods=foods, locations_json=locations_data)

@app.route("/customer/orders")
def customer_orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    # Pulling orders with coordinates for the universal navigation link
    orders = conn.execute("""
        SELECT o.*, r.name as restaurant_name, r.address as restaurant_address, r.lat, r.lon, f.name as food_name
        FROM orders o
        JOIN restaurants r ON o.restaurant_id = r.id
        JOIN food f ON o.food_id = f.id
        WHERE o.user_id = ?
        ORDER BY o.id DESC
    """, (session['user_id'],)).fetchall()
    conn.close()

    # FIX: Grouping logic to ensure "orders" is a dict for the loop
    grouped_orders = {}
    for order in orders:
        token = order['token']
        if token not in grouped_orders:
            grouped_orders[token] = {
                'restaurant': order['restaurant_name'],
                'address': order['restaurant_address'],
                'lat': order['lat'],
                'lon': order['lon'],
                'status': order['status'],
                'items': [],
                'total_amount': 0,
                'date': order['created_at']
            }
        grouped_orders[token]['items'].append({
            'name': order['food_name'],
            'qty': order['quantity']
        })
        grouped_orders[token]['total_amount'] += order['total_price']

    return render_template("customer_orders.html", orders=grouped_orders)

# ================= CART & CHECKOUT LOGIC =================

@app.route('/add_to_cart/<int:food_id>', methods=['POST'])
def add_to_cart(food_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    qty = int(request.form.get('order_quantity', 1))
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    cart[str(food_id)] = cart.get(str(food_id), 0) + qty
    session['cart'] = cart
    session.modified = True
    flash("Item added to cart!")
    return redirect(url_for('customer_home'))

@app.route('/checkout', methods=['GET'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if not session.get('cart'):
        flash("Your cart is empty.")
        return redirect(url_for('customer_home'))

    conn = get_db_connection()
    cart_items = []
    grand_total = 0
    restaurant_info = None 
    
    for food_id_str, qty in session['cart'].items():
        item = conn.execute("""
            SELECT f.*, r.name as restaurant_name, r.address as restaurant_address 
            FROM food f JOIN restaurants r ON f.restaurant_id = r.id 
            WHERE f.id = ?""", (int(food_id_str),)).fetchone()
        
        if item:
            if not restaurant_info:
                restaurant_info = {'name': item['restaurant_name'], 'address': item['restaurant_address']}
            total = item['discounted_price'] * qty
            grand_total += total
            cart_items.append({'details': item, 'qty': qty, 'item_total': total})
    conn.close()
    
    order_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
    return render_template("checkout.html", items=cart_items, grand_total=grand_total, 
                           restaurant=restaurant_info, order_time=order_time)

@app.route('/confirm_order', methods=['POST'])
def confirm_order():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    overall_total = 0
    order_token = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    
    try:
        for f_id, qty in session['cart'].items():
            food = conn.execute("SELECT * FROM food WHERE id = ?", (int(f_id),)).fetchone()
            if food and food['quantity'] >= qty:
                new_qty = food['quantity'] - qty
                conn.execute("UPDATE food SET quantity = ?, status = ? WHERE id = ?", 
                             (new_qty, 'sold' if new_qty == 0 else 'available', f_id))
                
                total = food['discounted_price'] * qty
                overall_total += total
                
                conn.execute("""INSERT INTO orders (user_id, food_id, restaurant_id, quantity, total_price, token, status) 
                                VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                             (session['user_id'], f_id, food['restaurant_id'], qty, total, order_token))
        
        conn.commit()
        session.pop('cart', None)
        # Real-time Order Alert for Vendor
        socketio.emit('new_order_alert', {'message': f"New order: {order_token}", 'amount': f"{overall_total:.2f}"})
        # Instant Redirect to History
        return redirect(url_for('customer_orders')) 
    except Exception as e:
        conn.rollback()
        flash(f"Order failed: {str(e)}")
        return redirect(url_for('customer_home'))
    finally:
        conn.close()

# ================= VENDOR DASHBOARD & ORDERS =================

@app.route("/vendor/dashboard", methods=['GET', 'POST'])
def vendor_dashboard():
    if 'restaurant_id' not in session:
        return redirect(url_for('restaurant_login'))

    conn = get_db_connection()
    res_id = session['restaurant_id'] 
    
    # SAFETY FIX: Prevents subscription error if restaurant is deleted
    restaurant_info = conn.execute("SELECT name FROM restaurants WHERE id = ?", (res_id,)).fetchone()
    if not restaurant_info:
        session.clear()
        flash("Restaurant account not found.")
        return redirect(url_for('restaurant_login'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price')
        qty = int(request.form.get('quantity', 0))

        if name and price and qty > 0:
            existing = conn.execute("SELECT id, quantity FROM food WHERE restaurant_id = ? AND LOWER(name) = ? AND status = 'available'", (res_id, name.lower())).fetchone()
            if existing:
                conn.execute("UPDATE food SET quantity = ?, discounted_price = ?, name = ? WHERE id = ?", (existing['quantity'] + qty, price, name, existing['id']))
            else:
                conn.execute("INSERT INTO food (restaurant_id, name, discounted_price, quantity, status) VALUES (?,?,?,?,?)", (res_id, name, price, qty, 'available'))
            conn.commit()

    # Dynamic Revenue Tracking
    stats = conn.execute("SELECT SUM(total_price) as revenue, COUNT(*) as count FROM orders WHERE restaurant_id = ? AND status = 'collected'", (res_id,)).fetchone()
    total_revenue = stats['revenue'] if stats['revenue'] else 0
    meals_saved = stats['count'] if stats['count'] else 0

    food_items = conn.execute("SELECT * FROM food WHERE restaurant_id = ? AND status='available' ORDER BY id DESC", (res_id,)).fetchall()
    conn.close()
    return render_template("vendor_dashboard.html", food_items=food_items, restaurant_name=restaurant_info['name'], total_revenue=total_revenue, meals_saved=meals_saved)

@app.route("/vendor/orders")
def vendor_orders():
    if 'restaurant_id' not in session: return redirect(url_for('restaurant_login'))
    conn = get_db_connection()
    raw = conn.execute("""SELECT o.*, u.name as customer_name, f.name as food_name 
                          FROM orders o 
                          JOIN users u ON o.user_id = u.id 
                          JOIN food f ON o.food_id = f.id 
                          WHERE o.restaurant_id = ? AND o.status = 'pending'""", 
                       (session['restaurant_id'],)).fetchall()
    conn.close()
    grouped = {}
    for r in raw:
        t = r['token']
        if t not in grouped: 
            grouped[t] = {'customer': r['customer_name'], 'time': r['created_at'], 'food_list': [], 'grand_total': 0}
        grouped[t]['food_list'].append({'name': r['food_name'], 'qty': r['quantity'], 'subtotal': r['total_price']})
        grouped[t]['grand_total'] += r['total_price']
    return render_template("vendor_orders.html", orders=grouped)

@app.route("/vendor/order/complete/<token>", methods=['POST'])
def complete_order(token):
    if 'restaurant_id' not in session: return redirect(url_for('restaurant_login'))
    conn = get_db_connection()
    conn.execute("UPDATE orders SET status = 'collected' WHERE token = ? AND restaurant_id = ?", (token, session['restaurant_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('vendor_orders'))

# ================= AUTHENTICATION =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session.clear()
            session['user_id'] = user['id'] 
            return redirect(url_for("customer_home"))
        flash("Invalid login credentials")
    return render_template("login.html")

@app.route('/restaurant/login', methods=['GET', 'POST'])
def restaurant_login():
    if request.method == "POST":
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        conn = get_db_connection()
        res = conn.execute("SELECT * FROM restaurants WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if res:
            session.clear()
            session['restaurant_id'] = res['id']  
            return redirect(url_for("vendor_dashboard"))
        flash("Invalid restaurant login")
    return render_template("restaurant_login.html")

# ================= DATABASE AUTO-FIX =================
def ensure_columns_exist():
    conn = get_db_connection()
    try:
        # Schema migration guard
        columns_to_add = [
            ("restaurants", "category", "TEXT"),
            ("restaurants", "phone", "TEXT"),
            ("restaurants", "lat", "REAL"),
            ("restaurants", "lon", "REAL"),
            ("orders", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        for table, col, col_type in columns_to_add:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass 
        conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    ensure_columns_exist() 
    socketio.run(app, debug=True)