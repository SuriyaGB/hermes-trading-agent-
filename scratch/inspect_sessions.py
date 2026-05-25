import sqlite3
from pathlib import Path

db_path = Path("/home/gbrithp2/Documents/krc_Lab/ hermes-vps-audit/.hermes/state.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT * FROM sessions;")
rows = cursor.fetchall()
# Get column names
cursor.execute("PRAGMA table_info(sessions);")
cols = [col[1] for col in cursor.fetchall()]
print(f"Columns: {cols}")
print(f"Found {len(rows)} sessions:")
for r in rows:
    # Map row values to columns
    row_dict = dict(zip(cols, r))
    session_id = row_dict.get('id') or row_dict.get('uuid') or 'unknown'
    prompt = row_dict.get('system_prompt') or ''
    print(f"Session ID: {session_id}, Prompt length: {len(prompt)}")
    if prompt:
        for line in prompt.split("\n"):
            if any(term in line.lower() for term in ["policy", "block", "roll", "0.45"]):
                print(f"  Line: {line.strip()[:150]}")

conn.close()
