from flask import Flask, request, session, jsonify, g, render_template, redirect
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
app.config['SECRET_KEY'] = 'devkey'
DATABASE = 'parkping.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    cur = db.cursor()
    # Users table
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT
    )''')
    # Parking spots with creator_id to track which organizer created it
    cur.execute('''CREATE TABLE IF NOT EXISTS parking_spots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        address TEXT,
        lat REAL,
        lng REAL,
        rate REAL,
        is_available INTEGER,
        creator_id INTEGER
    )''')
    # Bookings table
    cur.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        spot_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        cost REAL,
        paid INTEGER
    )''')
    db.commit()
    db.close()

init_db()

@app.route('/')
def home():
    return render_template('index.html') if 'user_id' in session else redirect('/login')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/organizer')
def organizer_page():
    return render_template('organizer.html') if 'user_id' in session else redirect('/login')

# Register new user
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    db = get_db()
    try:
        db.execute("INSERT INTO users (email, password) VALUES (?, ?)", 
                   (data['email'], generate_password_hash(data['password'])))
        db.commit()
        return jsonify({"message": "Registered"}), 201
    except:
        return jsonify({"error": "User exists"}), 400

# Login user
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (data['email'],)).fetchone()
    if user and check_password_hash(user['password'], data['password']):
        session['user_id'] = user['id']
        return jsonify({"message": "Login success"})
    return jsonify({"error": "Invalid credentials"}), 401

# Logout user
@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

# Get all available parking spots (for users)
@app.route('/api/parking/spots')
def get_spots():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    spots = get_db().execute("SELECT * FROM parking_spots WHERE is_available = 1").fetchall()
    return jsonify({"spots": [dict(row) for row in spots]})

# Book a parking spot
@app.route('/api/parking/book', methods=['POST'])
def book():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    db = get_db()
    cur = db.cursor()
    spot = cur.execute("SELECT * FROM parking_spots WHERE id = ?", (data['spot_id'],)).fetchone()
    if not spot or spot['is_available'] == 0:
        return jsonify({"error": "Unavailable"}), 400
    cost = spot['rate'] * float(data['hours'])
    cur.execute("UPDATE parking_spots SET is_available = 0 WHERE id = ?", (data['spot_id'],))
    cur.execute("INSERT INTO bookings (user_id, spot_id, start_time, end_time, cost, paid) VALUES (?, ?, ?, ?, ?, 0)",
                (session['user_id'], data['spot_id'],
                 datetime.now(), datetime.now() + timedelta(hours=float(data['hours'])), cost))
    db.commit()
    return jsonify({"message": "Booked", "cost": cost})

# Complete payment for a booking
@app.route('/api/payment/complete', methods=['POST'])
def pay():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    db = get_db()
    db.execute("UPDATE bookings SET paid = 1 WHERE id = ? AND user_id = ?", 
               (data['booking_id'], session['user_id']))
    db.commit()
    return jsonify({"message": "Payment complete"})

# Get bookings of logged-in user
@app.route('/api/parking/bookings')
def get_bookings():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    bookings = db.execute("""
        SELECT b.*, p.address, p.lat, p.lng
        FROM bookings b
        JOIN parking_spots p ON b.spot_id = p.id
        WHERE b.user_id = ?
    """, (session['user_id'],)).fetchall()
    return jsonify({"bookings": [dict(row) for row in bookings]})

# Cancel a booking
@app.route('/api/parking/cancel', methods=['POST'])
def cancel_booking():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    booking_id = data.get('booking_id')
    if not booking_id:
        return jsonify({"error": "Missing booking_id"}), 400
    
    db = get_db()
    cur = db.cursor()

    booking = cur.execute("SELECT * FROM bookings WHERE id = ? AND user_id = ?", 
                          (booking_id, session['user_id'])).fetchone()
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    spot_id = booking['spot_id']

    cur.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    cur.execute("UPDATE parking_spots SET is_available = 1 WHERE id = ?", (spot_id,))
    db.commit()
    return jsonify({"message": "Booking canceled successfully"})

# Add parking spot as organizer (track creator_id)
@app.route('/api/organizer/add_spot', methods=['POST'])
def add_spot():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    db = get_db()
    db.execute("""INSERT INTO parking_spots (address, lat, lng, rate, is_available, creator_id)
                  VALUES (?, ?, ?, ?, 1, ?)""",
               (data['address'], data['lat'], data['lng'], data['rate'], session['user_id']))
    db.commit()
    return jsonify({"message": "Spot added"})

# Get spots created by logged-in organizer only
@app.route('/api/organizer/spots')
def organizer_spots():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    spots = db.execute("SELECT * FROM parking_spots WHERE creator_id = ?", (session['user_id'],)).fetchall()
    return jsonify({"spots": [dict(row) for row in spots]})

# Cancel spot created by logged-in organizer (authorization check)
@app.route('/api/organizer/cancel_spot', methods=['POST'])
def cancel_spot():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    spot_id = data.get('spot_id')
    if not spot_id:
        return jsonify({"error": "Missing spot_id"}), 400

    db = get_db()
    cur = db.cursor()
    spot = cur.execute("SELECT * FROM parking_spots WHERE id = ? AND creator_id = ?", (spot_id, session['user_id'])).fetchone()
    if not spot:
        return jsonify({"error": "Spot not found or unauthorized"}), 404

    cur.execute("DELETE FROM parking_spots WHERE id = ?", (spot_id,))
    db.commit()
    return jsonify({"message": "Spot cancelled successfully"})

if __name__ == '__main__':
    app.run(debug=True)
