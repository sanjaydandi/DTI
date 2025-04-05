from flask import Flask
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db.init_app(app)

with app.app_context():
    import sqlite3
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info('attendances')")
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    print(columns)
    print('status exists:', 'status' in columns)