import sqlite3

conn = sqlite3.connect("users.db")
c = conn.cursor()

c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")

conn.commit()
conn.close()

print("Column added successfully!")