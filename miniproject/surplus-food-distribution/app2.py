from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from flask_socketio import SocketIO, emit 
import sqlite3
import os
import re
import secrets 
import string
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename # Added for images
from geopy.geocoders import Nominatim # Added for City to Location conversion

app = Flask(__name__)
app.secret_key = 'sunset_servings_key_123'

# Initialize Geocoder
geolocator = Nominatim(user_agent="sunset_servings_app")

# --- IMAGE CONFIGURATION ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*") 

# ================= DATABASE CONNECTION =================
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    conn = sqlite3.connect(db_path, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

# ================= AUTO-EXPIRY LOGIC =================
def auto_expire_food():
    """
    If restaurant closing time has passed, automatically mark food as 'expired'
    so it no longer appears in the customer search results.
    """
    conn = get_db_connection()
    now_local = datetime.now().strftime('%H:%M')
    try:
        conn.execute("""
            UPDATE food 
            SET status = 'expired' 
            WHERE id IN (
                SELECT f.id 
                FROM food f 
                JOIN restaurants r ON f.restaurant_id = r.id 
                WHERE f.status = 'available' 
                AND r.closing_time IS NOT NULL 
                AND r.closing_time < ?
            )
        """, (now_local,))
        conn.commit()
    except Exception as e:
        print(f"Auto-expire error: {e}")
    finally:
        conn.close()

# ================= SMART PRICING CALCULATOR ENGINE =================
def calculate_live_price(item, now):
    """
    Calculates dynamic price based on stock, urgency, and perishability.
    UPDATED: Ensures live_price is never higher than the starting discount
    and handles low-cost items (Porotta) correctly.
    """
    try:
        # --- 1. SETUP BASE DATA ---
        original_price = float(item['original_price'])
        starting_discount_price = float(item['discounted_price'])
        quantity = int(item['quantity'])
        category = item.get('category', 'Meals')
        
        # Parse listing time
        created_at_str = item['created_at'].split(".")[0]
        list_time = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        
        # --- 2. MULTIPLIERS ---
        mins_to_close = 120 
        if item.get('closing_time'):
            try:
                close_h, close_m = map(int, item['closing_time'].split(':'))
                close_dt = now.replace(hour=close_h, minute=close_m, second=0)
                if close_dt < now:
                    close_dt += timedelta(days=1)
                mins_to_close = (close_dt - now).total_seconds() / 60
            except: pass
        
        # Acceleration as time runs out
        m_time = 1.8 if mins_to_close < 45 else (1.4 if mins_to_close < 90 else 1.0)
        # Higher stock = faster price drop
        m_stock = 1.4 if quantity > 10 else (0.8 if quantity < 3 else 1.0)
        # Perishability factor
        cat_map = {'Meals': 1.3, 'Bakery': 0.9, 'Drinks': 0.7}
        m_type = cat_map.get(category, 1.0)
        # Weekend adjustment
        m_weekend = 0.85 if now.weekday() >= 5 else 1.0

        # --- 3. EXECUTE CALCULATION ---
        diff_seconds = (now - list_time).total_seconds()
        intervals = int(diff_seconds // 1800) # 30 min blocks
        
        base_step_pct = 0.05 
        total_multiplier = m_time * m_stock * m_type * m_weekend
        
        reduction = (original_price * base_step_pct) * intervals * total_multiplier
        live_price = starting_discount_price - reduction
        
        # --- 4. SAFETY LOGIC GUARDRAILS ---
        # Ensure price is never higher than the restaurant's initial discount
        live_price = min(live_price, starting_discount_price)

        # SMART SAFETY FLOOR:
        # Instead of a flat 25, we use 20% of MRP or a base 5.0 (whichever is higher)
        # This allows 10rs Porotta to drop to 5-7rs instead of being forced to 25.
        price_floor = max(5.00, original_price * 0.20)
        
        # Ensure we don't return a floor higher than the MRP itself
        price_floor = min(price_floor, original_price * 0.9)
        
        return round(max(live_price, price_floor), 2)
    except Exception as e:
        print(f"Pricing Error: {e}")
        return item['discounted_price']

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

# ================= SUGGESTION API =================
@app.route("/api/suggestions")
def get_suggestions():
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify({"suggestions": []})
    conn = get_db_connection()
    results = conn.execute(
        "SELECT DISTINCT name FROM food WHERE name LIKE ? AND status='available' LIMIT 5",
        (f'%{query}%',)
    ).fetchall()
    conn.close()
    suggestions = [row['name'] for row in results]
    return jsonify({"suggestions": suggestions})

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
        city = request.form.get('city', '').strip()
        
        if not all([name, email, password, city]):
            flash("All fields including city are required!")
            return redirect(url_for('register'))

        try:
            location_data = geolocator.geocode(city)
            if location_data:
                lat = location_data.latitude
                lon = location_data.longitude
            else:
                flash("Could not find that city. Please try e.g., 'Kochi, Kerala'")
                return redirect(url_for('register'))
        except Exception:
            lat, lon = 0.0, 0.0

        valid, msg = is_valid_email(email)
        if not valid:
            flash(msg)
            return redirect(url_for('register'))

        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (name, email, password, lat, lon) VALUES (?, ?, ?, ?, ?)",
                         (name, email, password, lat, lon))
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

# ================= CUSTOMER DASHBOARD =================

@app.route("/customer/home")
def customer_home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    auto_expire_food()

    food_query = request.args.get('food', '').strip()
    location_query = request.args.get('location', '').strip()
    
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    now_local = datetime.now().strftime('%H:%M')

    query = """
        SELECT f.*, r.name as restaurant_name, r.address as location, r.lat, r.lon, r.closing_time
        FROM food f 
        JOIN restaurants r ON f.restaurant_id = r.id 
        WHERE f.status='available' 
        AND f.quantity > 0
        AND (r.closing_time > ? OR r.closing_time IS NULL)
    """
    params = [now_local]

    if food_query:
        search_term = food_query.lower()
        if search_term == 'veg':
            query += " AND f.food_type = 'Veg'"
        elif search_term == 'non-veg':
            query += " AND f.food_type = 'Non-Veg'"
        elif search_term in ['meals', 'bakery', 'drinks', 'juice']:
            query += " AND f.category = ?"
            mapped_cat = 'Drinks' if search_term in ['juice', 'drinks'] else food_query.capitalize()
            params.append(mapped_cat)
        else:
            query += " AND (f.name LIKE ? OR f.category LIKE ? OR f.food_type LIKE ?)"
            params.extend([f'%{food_query}%', f'%{food_query}%', f'%{food_query}%'])
        
    if location_query:
        query += " AND r.address LIKE ?"
        params.append(f'%{location_query}%')

    rows = conn.execute(query + " ORDER BY f.id DESC", params).fetchall()
    conn.close()

    processed_foods = []
    now = datetime.now(timezone.utc)

    for row in rows:
        item = dict(row)
        item['live_price'] = calculate_live_price(item, now)
        processed_foods.append(item)

    locations_json = []
    for f in processed_foods:
        if f['lat'] is not None:
            locations_json.append({
                'food_name': f['name'],
                'restaurant_name': f['restaurant_name'],
                'address': f['location'],
                'lat': f['lat'],
                'lon': f['lon'],
                'price': f['live_price'],
                'original_price': f['original_price'],
                'food_type': f.get('food_type', 'Non-Veg')
            })

    return render_template("customer_home.html", foods=processed_foods, locations_json=locations_json, user=user)

@app.route("/customer/orders")
def customer_orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    orders = conn.execute("""
        SELECT o.*, r.name as restaurant_name, r.address as restaurant_address, r.lat, r.lon, f.name as food_name
        FROM orders o
        JOIN restaurants r ON o.restaurant_id = r.id
        JOIN food f ON o.food_id = f.id
        WHERE o.user_id = ?
        ORDER BY o.id DESC
    """, (session['user_id'],)).fetchall()
    conn.close()

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

@app.route('/remove_from_cart/<int:food_id>')
def remove_from_cart(food_id):
    if 'cart' in session:
        food_id_str = str(food_id)
        if food_id_str in session['cart']:
            session['cart'].pop(food_id_str)
            session.modified = True
            flash("Item removed from your bag.")
    return redirect(url_for('checkout'))
    
@app.route('/add_to_cart/<int:food_id>', methods=['POST'])
def add_to_cart(food_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    qty = int(request.form.get('order_quantity', 1))
    conn = get_db_connection()
    new_item = conn.execute("SELECT restaurant_id, name FROM food WHERE id = ?", (food_id,)).fetchone()
    
    if not new_item:
        conn.close()
        flash("Item not found.")
        return redirect(url_for('customer_home'))

    if 'cart' not in session:
        session['cart'] = {}
    cart = session['cart']

    if cart:
        first_item_id = int(next(iter(cart)))
        existing_item = conn.execute("SELECT restaurant_id FROM food WHERE id = ?", (first_item_id,)).fetchone()
        if existing_item and existing_item['restaurant_id'] != new_item['restaurant_id']:
            conn.close()
            flash("You can only add items from one restaurant at a time!")
            return redirect(url_for('customer_home'))

    conn.close()
    cart[str(food_id)] = cart.get(str(food_id), 0) + qty
    session['cart'] = cart
    session.modified = True
    flash(f"Added {new_item['name']} to rescue bag!")
    return redirect(url_for('customer_home'))

@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    flash("Cart cleared.")
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
    now = datetime.now(timezone.utc)
    
    for food_id_str, qty in session['cart'].items():
        item_row = conn.execute("""
            SELECT f.*, r.name as restaurant_name, r.address as restaurant_address, r.closing_time 
            FROM food f JOIN restaurants r ON f.restaurant_id = r.id 
            WHERE f.id = ?""", (int(food_id_str),)).fetchone()
        
        if item_row:
            item = dict(item_row)
            if not restaurant_info:
                restaurant_info = {
                    'name': item['restaurant_name'], 
                    'address': item['restaurant_address'],
                    'closing_time': item['closing_time']
                }
            current_price = calculate_live_price(item, now)
            total = current_price * qty
            grand_total += total
            cart_items.append({'details': item, 'qty': qty, 'item_total': total, 'current_price': current_price})
    conn.close()
    order_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
    return render_template("checkout.html", items=cart_items, grand_total=grand_total, restaurant=restaurant_info, order_time=order_time)

@app.route('/confirm_order', methods=['POST'])
def confirm_order():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    overall_total = 0
    order_token = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    now = datetime.now(timezone.utc)
    
    try:
        for f_id, qty in session['cart'].items():
            food_row = conn.execute("SELECT * FROM food WHERE id = ?", (int(f_id),)).fetchone()
            if food_row:
                food = dict(food_row)
                if food['quantity'] >= qty:
                    purchase_price = calculate_live_price(food, now)
                    new_qty = food['quantity'] - qty
                    conn.execute("UPDATE food SET quantity = ?, status = ? WHERE id = ?", (new_qty, 'sold' if new_qty == 0 else 'available', f_id))
                    total = purchase_price * qty
                    overall_total += total
                    conn.execute("INSERT INTO orders (user_id, food_id, restaurant_id, quantity, total_price, token, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                                 (session['user_id'], f_id, food['restaurant_id'], qty, total, order_token))
        conn.commit()
        session.pop('cart', None)
        socketio.emit('new_order_alert', {'message': f"New order: {order_token}", 'amount': f"{overall_total:.2f}"})
        return redirect(url_for('customer_orders')) 
    except Exception as e:
        conn.rollback()
        flash(f"Order failed: {str(e)}")
        return redirect(url_for('customer_home'))
    finally:
        conn.close()

# ================= VENDOR DASHBOARD =================

@app.route("/vendor/update_settings", methods=['POST'])
def update_settings():
    if 'restaurant_id' not in session:
        return redirect(url_for('restaurant_login'))
    
    closing_time = request.form.get('closing_time')
    conn = get_db_connection()
    conn.execute("UPDATE restaurants SET closing_time = ? WHERE id = ?", (closing_time, session['restaurant_id']))
    conn.commit()
    conn.close()
    flash("Closing time updated!")
    return redirect(url_for('vendor_dashboard'))

@app.route("/vendor/dashboard", methods=['GET', 'POST'])
def vendor_dashboard():
    if 'restaurant_id' not in session:
        return redirect(url_for('restaurant_login'))

    conn = get_db_connection()
    res_id = session['restaurant_id'] 
    
    restaurant_info = conn.execute("SELECT * FROM restaurants WHERE id = ?", (res_id,)).fetchone()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        orig_price = request.form.get('original_price')
        disc_price = request.form.get('price')
        qty = int(request.form.get('quantity', 0))
        category = request.form.get('category', 'Meals')
        food_type = request.form.get('food_type', 'Non-Veg')
        
        file = request.files.get('food_image')
        image_url = 'default_food.jpg'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_url = filename

        if name and disc_price and qty > 0:
            now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("""INSERT INTO food (restaurant_id, name, original_price, discounted_price, quantity, status, created_at, category, food_type, image_url) 
                         VALUES (?,?,?,?,?,?,?,?,?,?)""", 
                         (res_id, name, orig_price, disc_price, qty, 'available', now_utc, category, food_type, image_url))
            conn.commit()
            flash(f"Listed {name} successfully!")

    food_items = conn.execute("SELECT * FROM food WHERE restaurant_id = ? AND status='available' ORDER BY id DESC", (res_id,)).fetchall()
    stats = conn.execute("SELECT SUM(total_price) as revenue, COUNT(*) as count FROM orders WHERE restaurant_id = ? AND status = 'collected'", (res_id,)).fetchone()
    total_revenue = stats['revenue'] if stats['revenue'] else 0
    meals_saved = stats['count'] if stats['count'] else 0
    conn.close()

    return render_template("vendor_dashboard.html", food_items=food_items, 
                           restaurant_name=restaurant_info['name'], 
                           restaurant_info=restaurant_info,
                           closing_time=restaurant_info['closing_time'],
                           total_revenue=total_revenue, meals_saved=meals_saved)

@app.route("/reduce-stock/<int:item_id>", methods=['POST'])
def reduce_stock(item_id):
    if 'restaurant_id' not in session: return redirect(url_for('restaurant_login'))
    reduce_amount = int(request.form.get('reduce_amount', 1))
    conn = get_db_connection()
    item = conn.execute("SELECT name, quantity FROM food WHERE id = ? AND restaurant_id = ?", (item_id, session['restaurant_id'])).fetchone()
    if item and item['quantity'] >= reduce_amount:
        new_qty = item['quantity'] - reduce_amount
        conn.execute("UPDATE food SET quantity = ?, status = ? WHERE id = ?", (new_qty, 'available' if new_qty > 0 else 'sold', item_id))
        conn.commit()
        flash(f"Reduced {item['name']} stock.")
    conn.close()
    return redirect(url_for('vendor_dashboard'))

@app.route("/vendor/orders")
def vendor_orders():
    if 'restaurant_id' not in session: return redirect(url_for('restaurant_login'))
    conn = get_db_connection()
    raw = conn.execute("""SELECT o.*, u.name as customer_name, f.name as food_name 
                          FROM orders o JOIN users u ON o.user_id = u.id JOIN food f ON o.food_id = f.id 
                          WHERE o.restaurant_id = ? AND o.status = 'pending'""", (session['restaurant_id'],)).fetchall()
    conn.close()
    grouped = {}
    for r in raw:
        t = r['token']
        if t not in grouped: grouped[t] = {'customer': r['customer_name'], 'time': r['created_at'], 'food_list': [], 'grand_total': 0}
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

# ================= DATABASE AUTO-FIX =================
def ensure_columns_exist():
    conn = get_db_connection()
    try:
        columns_to_add = [
            ("restaurants", "category", "TEXT"), ("restaurants", "phone", "TEXT"), ("restaurants", "lat", "REAL"), ("restaurants", "lon", "REAL"), ("restaurants", "closing_time", "TEXT"),
            ("orders", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("users", "lat", "REAL"), ("users", "lon", "REAL"),
            ("food", "original_price", "REAL"), ("food", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"), ("food", "category", "TEXT DEFAULT 'Meals'"), ("food", "food_type", "TEXT DEFAULT 'Non-Veg'"), ("food", "image_url", "TEXT DEFAULT 'default_food.jpg'")
        ]
        for table, col, col_type in columns_to_add:
            try: conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError: pass 
        conn.commit()
    finally:
        conn.close()

# ================= PRESENTATION RESET ROUTE =================
@app.route("/reset-items")
def reset_items_timestamp():
    conn = get_db_connection()
    now_string = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    try:
        conn.execute("UPDATE food SET created_at = ?, status = 'available'", (now_string,))
        conn.execute("DELETE FROM orders")
        conn.commit()
        print(f"\nSYSTEM RESET: {now_string}\n")
        return f"""
            <div style="font-family:sans-serif; text-align:center; padding:50px; background:#000; color:white; min-height:100vh;">
                <h1 style="color:#2ecc71;">✅ SYSTEM READY FOR DEMO</h1>
                <p>All timestamps updated. Order history wiped.</p>
                <br><a href="/customer/home" style="color:#e67e22;">GO TO HOME</a>
            </div>
        """
    except Exception as e: return f"Error: {e}"
    finally: conn.close()

# ================= LOGIN LOGIC =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session.pop('restaurant_id', None) 
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
            session.pop('user_id', None)
            session['restaurant_id'] = res['id']  
            return redirect(url_for("vendor_dashboard"))
        flash("Invalid restaurant login")
    return render_template("restaurant_login.html")

if __name__ == "__main__":
    ensure_columns_exist() 
    socketio.run(app, debug=True)