import sqlite3
from pathlib import Path

db_path = Path("/home/gbrithp2/Documents/krc_Lab/ hermes-vps-audit/.hermes/state.db")
if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cursor.fetchall()]

search_terms = ["policy", "block", "reject", "0.45"]

for table in tables:
    if "fts" in table: # Skip FTS shadow tables to avoid clutter
        continue
    cursor.execute(f"PRAGMA table_info({table});")
    columns = [col[1] for col in cursor.fetchall()]
    
    for col in columns:
        for term in search_terms:
            try:
                # Case-insensitive search
                query = f"SELECT rowid, [{col}] FROM [{table}] WHERE CAST([{col}] AS TEXT) LIKE ?"
                cursor.execute(query, (f"%{term}%",))
                results = cursor.fetchall()
                if results:
                    print(f"Found match for '{term}' in table '{table}', column '{col}':")
                    for rowid, val in results[:5]: # Limit to 5 results per match
                        print(f"  RowID {rowid}: {str(val)[:200]}")
            except Exception as e:
                # Some tables may not support rowid or have other issues
                pass

conn.close()
