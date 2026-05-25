import sqlite3
from pathlib import Path

db_path = Path("/home/gbrithp2/Documents/krc_Lab/ hermes-vps-audit/data/hermes_brain.db")
if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM pulse_history;")
count = cursor.fetchone()[0]
print(f"Total pulses in database: {count}")

cursor.execute("SELECT id, timestamp, aapl_price, ai_decision FROM pulse_history ORDER BY id DESC LIMIT 10;")
rows = cursor.fetchall()
print("Last 10 pulses:")
for r in rows:
    print(f"  ID: {r['id']} | Timestamp: {r['timestamp']} | Price: {r['aapl_price']} | Decision: {r['ai_decision']}")

conn.close()
