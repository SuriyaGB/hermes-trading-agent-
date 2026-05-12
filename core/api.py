import json
import sqlite3
import csv
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Hermes Trading API", description="Data bridge for the Vercel Dashboard")

# IMPORTANT: CORS Middleware is required.
# Without this, Vercel (running on a different domain) will be blocked from fetching data here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows your Vercel frontend to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Find the absolute path to the data directory securely
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = BASE_DIR / "data"

@app.get("/api/portfolio")
def get_portfolio():
    """Returns the current cash, premium, and open positions."""
    path = DATA_DIR / "portfolio.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Portfolio not found")
    with open(path, "r") as f:
        return json.load(f)

@app.get("/api/status")
def get_status():
    """Returns the current Wheel phase and blackout status."""
    path = DATA_DIR / "trade_state.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Trade state not found")
    with open(path, "r") as f:
        return json.load(f)

@app.get("/api/trades")
def get_trades():
    """Parses the CSV log and returns all historical trades as JSON for the charts."""
    path = DATA_DIR / "trades_log.csv"
    if not path.exists():
        return []
    
    trades = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    return trades

@app.get("/api/pulses")
def get_pulses(limit: int = 50):
    """Fetches the AI's exact history from the SQLite brain for the Time Machine chart."""
    db_path = DATA_DIR / "hermes_brain.db"
    trade_state_path = DATA_DIR / "trade_state.json"
    
    if not db_path.exists():
        return []
        
    # Get current strike and expiry from trade state to find the relevant delta
    strike = None
    expiry_str = None
    if trade_state_path.exists():
        try:
            with open(trade_state_path, "r") as f:
                state = json.load(f)
                strike = state.get('current_option_strike')
                expiry_str = state.get('current_option_expiry')
        except:
            pass
    
    try:
        import datetime
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row  # This makes rows behave like dictionaries
        cursor = conn.cursor()
        
        # Pull the exact metrics needed for the VIX, Price, and Delta charts
        cursor.execute('''
            SELECT id, timestamp, aapl_price, vix_level, earnings_days, 
                   ai_decision, ai_reasoning
            FROM pulse_history
            ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        result = []
        
        for row in rows:
            row_dict = dict(row)
            
            # Default placeholders
            row_dict['delta_current'] = '--'
            row_dict['dte_current'] = '--'
            
            # Try to get the options chain data for this specific pulse
            opt_row = cursor.execute('SELECT chain_data_json FROM option_snapshots WHERE pulse_id = ?', (row_dict['id'],)).fetchone()
            
            if opt_row and strike:
                try:
                    chain = json.loads(opt_row['chain_data_json'])
                    for opt in chain:
                        if opt['strike'] == strike:
                            row_dict['delta_current'] = round(opt.get('delta', 0), 3)
                            break
                except:
                    pass
                    
            # Calculate DTE dynamically
            if expiry_str and row_dict['timestamp']:
                try:
                    pulse_dt = datetime.datetime.strptime(row_dict['timestamp'], "%Y-%m-%d %H:%M:%S")
                    expiry_dt = datetime.datetime.strptime(expiry_str, "%Y%m%d")
                    row_dict['dte_current'] = (expiry_dt - pulse_dt).days
                except:
                    pass
            
            result.append(row_dict)
            
        conn.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def get_health():
    """Bot health monitor endpoint."""
    return {"status": "ALIVE", "message": "FastAPI is running and ready for Vercel."}

@app.get("/api/income_history")
def get_income_history():
    """Dynamically reconstructs account balance history using trades log and portfolio."""
    portfolio_path = DATA_DIR / "portfolio.json"
    trades_path = DATA_DIR / "trades_log.csv"
    
    if not portfolio_path.exists() or not trades_path.exists():
        return []
        
    with open(portfolio_path, "r") as f:
        port_data = json.load(f)
        
    current_cash = port_data.get("total_cash", 250000.0)
    
    history = []
    baseline_cash = 250000.0  # The initial starting balance
    has_jumped = False
    
    with open(trades_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            action = row['action']
            timestamp = row['timestamp']
            
            # When the put is opened, the premium hits the account
            # We check the entire row string because the CSV headers are misaligned
            if action == 'SELL_NEW_PUT' and 'OPENED' in str(row.values()):
                baseline_cash = current_cash
                has_jumped = True
                
            history.append({
                "timestamp": timestamp, 
                "balance": baseline_cash
            })
                
    # If the history is empty, just return the current state
    if not history:
        history.append({"timestamp": port_data.get("last_update", ""), "balance": current_cash})
        
    return history
