import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("users.db")
c = conn.cursor()

c.execute("""
INSERT INTO users (username, email, password, role)
VALUES (?, ?, ?, ?)
""", ("Admin", "admin@gmail.com", generate_password_hash("admin123"), "admin"))

conn.commit()
conn.close()

print("Admin added successfully!")