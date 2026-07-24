import sqlite3
import json

try:
    con = sqlite3.connect("backend/data/peng.db")
    cur = con.cursor()
    cur.execute("SELECT id, category_type, expense_type FROM category WHERE id LIKE '%fagforening%';")
    print(json.dumps(cur.fetchall(), indent=2))
except Exception as e:
    print("Error:", e)
