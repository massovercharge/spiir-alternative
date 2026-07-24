import sqlite3
import json

try:
    con = sqlite3.connect("../data/peng.sqlite")
    cur = con.cursor()
    
    # Insert from budget_bill (which implies Fixed)
    cur.execute("""
        SELECT DISTINCT b.category_id, b.amount_minor 
        FROM budgetbill b
        LEFT JOIN category c ON b.category_id = c.id
        WHERE c.id IS NULL
    """)
    bills = cur.fetchall()
    
    for cat_id, amount_minor in bills:
        parts = cat_id.split('|')
        main_name = parts[0].capitalize()
        sub_name = parts[1].replace('-', ' ').capitalize() if len(parts) > 1 else main_name
        cat_type = "Income" if amount_minor > 0 else "Expense"
        
        cur.execute(
            "INSERT INTO category (id, main_name, sub_name, category_type, expense_type) VALUES (?, ?, ?, ?, ?)",
            (cat_id, main_name, sub_name, cat_type, "Fixed")
        )
        print(f"Inserted Category from Bill: {cat_id}")
        
    # Insert from budget (which implies Variable)
    cur.execute("""
        SELECT DISTINCT b.category_id, b.amount_minor 
        FROM budget b
        LEFT JOIN category c ON b.category_id = c.id
        WHERE c.id IS NULL
    """)
    budgets = cur.fetchall()
    
    for cat_id, amount_minor in budgets:
        parts = cat_id.split('|')
        main_name = parts[0].capitalize()
        sub_name = parts[1].replace('-', ' ').capitalize() if len(parts) > 1 else main_name
        cat_type = "Income" if amount_minor > 0 else "Expense"
        
        cur.execute(
            "INSERT INTO category (id, main_name, sub_name, category_type, expense_type) VALUES (?, ?, ?, ?, ?)",
            (cat_id, main_name, sub_name, cat_type, "Variable")
        )
        print(f"Inserted Category from Budget: {cat_id}")

    con.commit()
    print("Done")
except Exception as e:
    print(e)
