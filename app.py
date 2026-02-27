from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'user')''')

    cur.execute('''CREATE TABLE IF NOT EXISTS vehicles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT, model TEXT, price INTEGER, image TEXT)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, vehicle_id INTEGER, status TEXT DEFAULT 'Pending')''')

    cur.execute('''CREATE TABLE IF NOT EXISTS testimonials(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT, message TEXT, status TEXT DEFAULT 'Active')''')

    cur.execute('''CREATE TABLE IF NOT EXISTS contacts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT, message TEXT)''')

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route("/")
def index():
    conn = get_db()
    cars = conn.execute("SELECT * FROM vehicles").fetchall()
    return render_template("index.html", cars=cars)

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        is_admin = request.form.get("is_admin")  # Returns "on" if checked, None if unchecked

        conn = get_db()
        cur = conn.cursor()

        # Decide role
        if is_admin == "on":
            role = "admin"
        else:
            # If first user and checkbox not checked, still make first user admin
            user_count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            role = "admin" if user_count == 0 else "user"

        try:
            cur.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                        (name,email,password,role))
            conn.commit()
            flash(f"Registration successful! You are logged in as {role}.")
            return redirect("/login")
        except:
            flash("Email already exists!")
    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?",
                            (email,password)).fetchone()
        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect("/admin")
            return redirect("/dashboard")
        else:
            flash("Invalid credentials")
    return render_template("login.html")

# ---------------- USER DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("dashboard.html")

# ---------------- BOOK CAR ----------------
@app.route("/book/<int:id>")
def book(id):
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    conn.execute("INSERT INTO bookings(user_id,vehicle_id) VALUES(?,?)",
                 (session["user_id"],id))
    conn.commit()
    flash("Car booked successfully!")
    return redirect("/bookings")

# ---------------- VIEW BOOKINGS ----------------
@app.route("/bookings")
def bookings():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    data = conn.execute("""
        SELECT bookings.id, vehicles.model, vehicles.price, bookings.status
        FROM bookings JOIN vehicles ON vehicles.id = bookings.vehicle_id
        WHERE user_id=?""",(session["user_id"],)).fetchall()
    return render_template("bookings.html", bookings=data)

# ---------------- TESTIMONIAL ----------------
@app.route("/testimonial", methods=["GET","POST"])
def testimonial():
    if request.method=="POST":
        msg = request.form["message"]
        conn = get_db()
        conn.execute("INSERT INTO testimonials(user,message) VALUES(?,?)",
                     ("User",msg))
        conn.commit()
        flash("Testimonial submitted!")
    conn = get_db()
    data = conn.execute("SELECT * FROM testimonials WHERE status='Active'").fetchall()
    return render_template("testimonials.html", testimonials=data)

# ---------------- CONTACT ----------------
@app.route("/contact", methods=["GET","POST"])
def contact():
    if request.method=="POST":
        name = request.form["name"]
        email = request.form["email"]
        msg = request.form["message"]
        conn = get_db()
        conn.execute("INSERT INTO contacts(name,email,message) VALUES(?,?,?)",
                     (name,email,msg))
        conn.commit()
        flash("Query submitted!")
    return render_template("contact.html")

# ================= ADMIN PANEL =================
def admin_required():
    return "user_id" in session and session.get("role")=="admin"

@app.route("/admin")
def admin():
    if not admin_required():
        return redirect("/")

    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    cars = conn.execute("SELECT * FROM vehicles").fetchall()
    bookings = conn.execute("""
        SELECT bookings.id, users.name, vehicles.model, bookings.status
        FROM bookings
        JOIN users ON users.id = bookings.user_id
        JOIN vehicles ON vehicles.id = bookings.vehicle_id
    """).fetchall()
    testimonials = conn.execute("SELECT * FROM testimonials").fetchall()
    queries = conn.execute("SELECT * FROM contacts").fetchall()

    stats = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "bookings": conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
        "cars": conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0],
        "queries": conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
    }

    return render_template("admin.html", users=users, cars=cars,
                           bookings=bookings, testimonials=testimonials,
                           queries=queries, stats=stats)

# ---------- ADD VEHICLE WITH IMAGE ----------
@app.route("/add_car", methods=["POST"])
def add_car():
    if not admin_required():
        return redirect("/")

    brand = request.form["brand"]
    model = request.form["model"]
    price = request.form["price"]
    image = request.files["image"]

    filename = secure_filename(image.filename)
    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = get_db()
    conn.execute("INSERT INTO vehicles(brand,model,price,image) VALUES(?,?,?,?)",
                 (brand,model,price,filename))
    conn.commit()
    flash("Vehicle added successfully!")
    return redirect("/admin")

# ---------- DELETE VEHICLE ----------
@app.route("/delete_car/<int:id>")
def delete_car(id):
    if not admin_required():
        return redirect("/")
    conn = get_db()
    conn.execute("DELETE FROM vehicles WHERE id=?", (id,))
    conn.commit()
    flash("Vehicle deleted!")
    return redirect("/admin")

# ---------- BOOKING STATUS ----------
@app.route("/booking_status/<int:id>/<status>")
def booking_status(id, status):
    if not admin_required():
        return redirect("/")
    conn = get_db()
    conn.execute("UPDATE bookings SET status=? WHERE id=?", (status,id))
    conn.commit()
    flash("Booking updated!")
    return redirect("/admin")

# ---------- TESTIMONIAL STATUS ----------
@app.route("/testimonial_status/<int:id>/<status>")
def testimonial_status(id, status):
    if not admin_required():
        return redirect("/")
    conn = get_db()
    conn.execute("UPDATE testimonials SET status=? WHERE id=?", (status,id))
    conn.commit()
    flash("Testimonial updated!")
    return redirect("/admin")

# ---------- CHANGE PASSWORD ----------
@app.route("/change_password", methods=["POST"])
def change_password():
    if not admin_required():
        return redirect("/")
    newpass = request.form["password"]
    conn = get_db()
    conn.execute("UPDATE users SET password=? WHERE id=?",
                 (newpass, session["user_id"]))
    conn.commit()
    flash("Password changed!")
    return redirect("/admin")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)