import sqlite3

db = sqlite3.connect('parkping.db')
cur = db.cursor()

try:
    cur.execute("ALTER TABLE parking_spots ADD COLUMN creator_id INTEGER;")
    print("Column added successfully!")
except sqlite3.OperationalError as e:
    print("Error (probably column exists):", e)

db.commit()
db.close()
