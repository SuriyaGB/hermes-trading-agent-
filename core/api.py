import json
import sqlite3
import csv
import os
from pathlib import Path
from datetime import datetime, timedelta
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
    """Returns the current cash, premium, and open positions, enriched with unrealized PnL metrics from SQLite."""
    path = DATA_DIR / "portfolio.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Portfolio not found")
    with open(path, "r") as f:
        portfolio = json.load(f)
        
    # Enrich active option positions with real-time unrealized PnL from SQLite
    db_path = DATA_DIR / "hermes_brain.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Fetch the raw_input_json of the latest pulse
            row = cursor.execute("SELECT raw_input_json FROM pulse_history ORDER BY id DESC LIMIT 1").fetchone()
            conn.close()
            
            if row and row[0]:
                raw_data = json.loads(row[0])
                option_chain = raw_data.get("option_chain", [])
                
                # Build option chain lookup by strike
                chain_by_strike = {item["strike"]: item for item in option_chain if "strike" in item}
                
                for pos in portfolio.get("positions", []):
                    if pos.get("type") == "Option":
                        strike = float(pos.get("strike", 0))
                        avg_cost = float(pos.get("avg_cost", 0))
                        
                        # Find matching strike in the option chain of the latest pulse
                        if strike in chain_by_strike:
                            chain_item = chain_by_strike[strike]
                            mid_price = chain_item.get("mid")
                            
                            if mid_price is not None:
                                pos["current_price"] = mid_price
                                # For short options (which we sell): profit is avg_cost - mid_price
                                if pos.get("option_type") == "PUT" or pos.get("option_type") == "CALL":
                                    pos["unrealized_pnl"] = round((avg_cost - mid_price) * 100, 2)
                                    pos["unrealized_pnl_percent"] = round(((avg_cost - mid_price) / avg_cost) * 100, 2)
                                else:
                                    # For long options (bought)
                                    pos["unrealized_pnl"] = round((mid_price - avg_cost) * 100, 2)
                                    pos["unrealized_pnl_percent"] = round(((mid_price - avg_cost) / avg_cost) * 100, 2)
        except Exception as e:
            print(f"Error enriching portfolio with unrealized PnL: {e}")
            
    return portfolio

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
    """Dynamically reconstructs account balance history using trades log and portfolio daily sequence."""
    portfolio_path = DATA_DIR / "portfolio.json"
    trades_path = DATA_DIR / "trades_log.csv"
    
    if not portfolio_path.exists():
        return []
        
    with open(portfolio_path, "r") as f:
        port_data = json.load(f)
        
    current_cash = port_data.get("total_cash", 250000.0)
    
    # We initialize the starting balance at the beginning of history (May 14, 2026)
    start_date = datetime(2026, 5, 14).date()
    end_date = datetime.now().date()
    
    # Reconstruct trade events by date
    trades_by_date = {}
    if trades_path.exists():
        try:
            with open(trades_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    action = row.get('action', '')
                    timestamp_str = row.get('timestamp', '')
                    try:
                        price = float(row.get('price', 0.0))
                    except ValueError:
                        price = 0.0
                        
                    # Parse date portion only (e.g. YYYY-MM-DD)
                    if timestamp_str:
                        date_key = datetime.strptime(timestamp_str.split(' ')[0], "%Y-%m-%d").date()
                        if date_key not in trades_by_date:
                            trades_by_date[date_key] = []
                        trades_by_date[date_key].append((action, price))
        except Exception as e:
            print(f"Error parsing trades log: {e}")
            
    history = []
    running_cash = 250000.0
    
    # Generate daily sequence from May 14 to today
    current_date = start_date
    while current_date <= end_date:
        # Apply any trade cash flows that occurred on this day
        if current_date in trades_by_date:
            for action, price in trades_by_date[current_date]:
                if action == 'SELL_PUT' or action == 'SELL_CALL':
                    running_cash += price * 100
                elif action == 'BUY_CLOSE' or action == 'BUY_TO_CLOSE':
                    running_cash -= price * 100
                elif action == 'ROLL_PUT' or action == 'ROLL_CALL':
                    running_cash += price * 100
                    
        history.append({
            "timestamp": current_date.strftime("%Y-%m-%d"),
            "balance": round(running_cash, 2)
        })
        current_date += timedelta(days=1)
        
    return history
