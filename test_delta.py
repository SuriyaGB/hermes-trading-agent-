import sqlite3, json, datetime

conn = sqlite3.connect('data/hermes_brain.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get latest pulse
row = dict(cursor.execute('SELECT id, timestamp FROM pulse_history ORDER BY timestamp DESC LIMIT 1').fetchone())

# Get trade state
with open('data/trade_state.json', 'r') as f:
    state = json.load(f)

strike = state.get('current_option_strike')
expiry_str = state.get('current_option_expiry')

# Get options data for this pulse
opt_row = cursor.execute('SELECT chain_data_json FROM option_snapshots WHERE pulse_id = ?', (row['id'],)).fetchone()

delta = None
if opt_row and strike:
    chain = json.loads(opt_row['chain_data_json'])
    for opt in chain:
        if opt['strike'] == strike:
            delta = opt.get('delta')
            break

# Calculate DTE
dte = None
if expiry_str and row['timestamp']:
    try:
        pulse_dt = datetime.datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S")
        expiry_dt = datetime.datetime.strptime(expiry_str, "%Y%m%d")
        dte = (expiry_dt - pulse_dt).days
    except Exception as e:
        print("DTE Error:", e)

print(f"Strike: {strike}, Expiry: {expiry_str}")
print(f"Found Delta: {delta}")
print(f"Calculated DTE: {dte}")
