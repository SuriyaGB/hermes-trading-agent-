import sqlite3
import json

def inspect():
    db_path = ".hermes/state.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables:", tables)
    
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"Table '{table}' has {count} rows")
        
        # Get columns
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row['name'] for row in cursor.fetchall()]
        print(f"  Columns: {columns}")
        
        # Get top 2 rows
        cursor.execute(f"SELECT * FROM {table} LIMIT 2")
        rows = cursor.fetchall()
        for idx, row in enumerate(rows):
            print(f"  Row {idx+1}: {dict(row)}")
            
    conn.close()

if __name__ == "__main__":
    inspect()
