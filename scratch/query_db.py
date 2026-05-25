import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / 'data' / 'hermes_brain.db'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("Searching database for rejected entries or ROLL attempts...")
rows = conn.execute('''
    SELECT id, timestamp, aapl_price, vix_level, earnings_days, 
           ai_decision, ai_override, override_reason, raw_output_json
    FROM pulse_history 
    WHERE ai_decision LIKE '%ROLL%' 
       OR override_reason LIKE '%reject%' 
       OR raw_output_json LIKE '%reject%' 
       OR raw_output_json LIKE '%Policy%'
    ORDER BY id DESC
''').fetchall()

print(f"Found {len(rows)} matching rows.")
for row in rows:
    print("="*60)
    print(f"ID: {row['id']} | Timestamp: {row['timestamp']}")
    print(f"Price: {row['aapl_price']} | VIX: {row['vix_level']}")
    print(f"Decision: {row['ai_decision']}")
    print(f"Override: {row['ai_override']} | Override Reason: {row['override_reason']}")
    print(f"Raw Output: {row['raw_output_json']}")
    print("="*60)
    print()

conn.close()
