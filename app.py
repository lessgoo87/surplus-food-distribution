from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

# ------------------------ DATABASE CONNECTION ------------------------
def get_db_connection():
    conn = sqlite3.connect("database.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------ HOME PAGE ------------------------
@app.route("/")
def home():
    return render_template("index.html")


# ------------------------ USER REGISTER ------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password)
        )
        conn.commit()
        conn.close()

        return "Registration Successful!"
    return render_template("register.html")


# ------------------------ USER LOGIN ------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            return redirect("/customer/home")
        else:
            return "Invalid login!"

    return render_template("login.html")


# ------------------------ CUSTOMER HOME PAGE ------------------------
@app.route('/customer/home')
def customer_home():
    return render_template("customer_home.html")


# ------------------------ RESTAURANT HOME PAGE ------------------------
@app.route('/restaurant')
def restaurant_home():
    return render_template("restaurant_home.html")


# ------------------------ RESTAURANT REGISTER ------------------------
@app.route('/restaurant/register', methods=['GET', 'POST'])
def restaurant_register():
    if request.method == 'POST':

        name = request.form['name']
        address = request.form['address']
        category = request.form['category']
        phone = request.form['phone']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO restaurants (name, address, category, phone, email, password) VALUES (?, ?, ?, ?, ?, ?)",
            (name, address, category, phone, email, password)
        )
        conn.commit()
        conn.close()

        return "Restaurant Registered Successfully!"

    return render_template("restaurant_register.html")


# ------------------------ RESTAURANT LOGIN ------------------------
@app.route('/restaurant/login', methods=['GET', 'POST'])
def restaurant_login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        restaurant = conn.execute(
            "SELECT * FROM restaurants WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        conn.close()

        if restaurant:
            return "Restaurant Login Successful!"
        else:
            return "Invalid Restaurant login!"

    return render_template("restaurant_login.html")


# ------------------------ RUN FLASK ------------------------
if __name__ == "__main__":
    app.run(debug=True)
