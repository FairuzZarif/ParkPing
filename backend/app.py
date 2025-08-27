
"""
ParkPing Backend (Flask + SQLite)
---------------------------------

This Flask app powers the ParkPing web application.
It provides authentication, parking spot management,
and booking APIs for users and organizers.

Features:
- User authentication (register, login, logout)
- Organizer parking spot creation and management
- Booking and pre-booking with cost calculation
- Integration with frontend (HTML, JS, Google Maps)

Author: Fairuz
"""

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
    if db:
        db.close()

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
    except sqlite3.IntegrityError:
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
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    spots = db.execute("""
        SELECT p.*, SUBSTR(u.email, 1, INSTR(u.email, '@') - 1) AS creator_name
        FROM parking_spots p
        JOIN users u ON p.creator_id = u.id
        WHERE p.is_available = 1
    """).fetchall()

    return jsonify({"spots": [dict(row) for row in spots]})

# Book a parking spot immediately (by hours)
@app.route('/api/parking/book', methods=['POST'])
def book():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
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
                 datetime.now().isoformat(), (datetime.now() + timedelta(hours=float(data['hours']))).isoformat(), cost))
    db.commit()
    return jsonify({"message": "Booked", "cost": cost})

# Pre-book parking spot for specified date/time range
@app.route('/api/parking/prebook', methods=['POST'])
def prebook():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json

    spot_id = data.get('spot_id')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')

    if not spot_id or not start_time_str or not end_time_str:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
    except ValueError:
        return jsonify({"error": "Invalid date/time format"}), 400

    if start_time >= end_time:
        return jsonify({"error": "End time must be after start time"}), 400

    db = get_db()
    cur = db.cursor()

    # Check if spot is available now
    spot = cur.execute("SELECT * FROM parking_spots WHERE id = ? AND is_available = 1", (spot_id,)).fetchone()
    if not spot:
        return jsonify({"error": "Spot unavailable"}), 400

    # Check if any existing bookings overlap requested time for this spot
    overlapping = cur.execute("""
        SELECT * FROM bookings WHERE spot_id = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND start_time < ?)
        )
    """, (spot_id, end_time_str, start_time_str, start_time_str, end_time_str)).fetchone()

    if overlapping:
        return jsonify({"error": "Spot is already booked for the selected time"}), 400

    duration_hours = (end_time - start_time).total_seconds() / 3600
    cost = spot['rate'] * duration_hours

    # Insert booking, mark spot as unavailable if booking includes current time
    now = datetime.now()
    is_currently_booked = start_time <= now <= end_time

    cur.execute("""INSERT INTO bookings
                   (user_id, spot_id, start_time, end_time, cost, paid)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (session['user_id'], spot_id, start_time_str, end_time_str, cost))

    if is_currently_booked:
        cur.execute("UPDATE parking_spots SET is_available = 0 WHERE id = ?", (spot_id,))

    db.commit()

    return jsonify({"message": "Pre-booked successfully", "cost": cost})

# Complete payment for a booking
@app.route('/api/payment/complete', methods=['POST'])
def pay():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
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
        SELECT b.*, p.address, p.lat, p.lng, p.rate
        FROM bookings b
        JOIN parking_spots p ON b.spot_id = p.id
        WHERE b.user_id = ?
    """, (session['user_id'],)).fetchall()
    return jsonify({"bookings": [dict(row) for row in bookings]})

# Cancel booking via DELETE method matching frontend call
@app.route('/api/parking/bookings/<int:booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    cur = db.cursor()
    booking = cur.execute("SELECT * FROM bookings WHERE id = ? AND user_id = ?", (booking_id, session['user_id'])).fetchone()
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    cur.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    cur.execute("UPDATE parking_spots SET is_available = 1 WHERE id = ?", (booking['spot_id'],))
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

# Get spots created by organizer + their bookings including user email
@app.route('/api/organizer/spots_with_bookings')
def organizer_spots_with_bookings():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    cur = db.cursor()

    spots = cur.execute("SELECT * FROM parking_spots WHERE creator_id = ?", (session['user_id'],)).fetchall()

    spots_list = []
    for spot in spots:
        bookings = cur.execute("""
            SELECT b.*, u.email AS user_email FROM bookings b
            JOIN users u ON b.user_id = u.id
            WHERE b.spot_id = ?
            ORDER BY b.start_time DESC
        """, (spot['id'],)).fetchall()

        spot_dict = dict(spot)
        spot_dict['bookings'] = [dict(b) for b in bookings]
        spots_list.append(spot_dict)

    return jsonify({"spots": spots_list})

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

    cur.execute("DELETE FROM bookings WHERE spot_id = ?", (spot_id,))
    cur.execute("DELETE FROM parking_spots WHERE id = ?", (spot_id,))
    db.commit()
    return jsonify({"message": "Spot cancelled successfully"})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
