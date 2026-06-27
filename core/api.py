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

# Use scratch/vps_data when running locally for audit (pulled VPS snapshot).
# Fall back to data/ when running on the VPS itself in production.
_SCRATCH_DIR = BASE_DIR / "scratch" / "vps_data"
DATA_DIR = _SCRATCH_DIR if _SCRATCH_DIR.exists() else BASE_DIR / "data"

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
            # Fetch recent pulse chains from SQLite (up to 10 recent pulses)
            rows = cursor.execute("SELECT id, timestamp, raw_input_json FROM pulse_history ORDER BY id DESC LIMIT 10").fetchall()
            conn.close()
            
            pulses_chain_data = []
            for r_id, r_ts, r_json in rows:
                if r_json:
                    try:
                        p_data = json.loads(r_json)
                        p_chain = p_data.get("option_chain", [])
                        chain_lookup = {}
                        strike_lookup = {}
                        for item in p_chain:
                            if "strike" in item and "expiry" in item:
                                chain_lookup[(float(item["strike"]), item["expiry"])] = item
                                strike_lookup[float(item["strike"])] = item
                        pulses_chain_data.append({"timestamp": str(r_ts).replace(" ", "T"), "chain": chain_lookup, "strike_chain": strike_lookup})
                    except Exception:
                        pass
            
            if pulses_chain_data:
                latest_chain = pulses_chain_data[0]["chain"]
                latest_strike_chain = pulses_chain_data[0]["strike_chain"]
                
                for pos in portfolio.get("positions", []):
                    if pos.get("type") == "Option":
                        strike = float(pos.get("strike", 0))
                        pos_expiry = pos.get("expiry", "N/A")
                        avg_cost = float(pos.get("avg_cost", 0))
                        
                        # Calculate DTE perfectly using mathematics, not fallbacks
                        if pos_expiry != "N/A":
                            try:
                                exp_dt = datetime.strptime(pos_expiry, "%Y%m%d").date()
                                pos["dte"] = (exp_dt - datetime.now().date()).days
                            except Exception:
                                pass
                                
                        # Recover missing entry_time from historical logs
                        if "entry_time" not in pos:
                            log_path = DATA_DIR / "trades_log.csv"
                            if log_path.exists():
                                try:
                                    with open(log_path, "r") as f:
                                        rows_csv = list(csv.DictReader(f))
                                        for r in reversed(rows_csv):
                                            log_strike = float(r.get("strike", 0))
                                            log_expiry = r.get("expiry", "N/A")
                                            if r.get("symbol") == pos.get("symbol", "") and log_strike == strike and log_expiry == pos_expiry:
                                                pos["entry_time"] = r.get("timestamp", "").replace(" ", "T")
                                                break
                                except Exception:
                                    pass
                                    
                            # Secondary fallback: if trades_log failed, check trade_state_history.jsonl
                            if "entry_time" not in pos:
                                hist_path = DATA_DIR / "trade_state_history.jsonl"
                                if hist_path.exists():
                                    try:
                                        with open(hist_path, "r") as f:
                                            # We want the FIRST time this strike appeared in history
                                            for line in f:
                                                try:
                                                    state_obj = json.loads(line.strip())
                                                    if state_obj.get("current_option_strike") == strike and state_obj.get("current_option_expiry") == pos_expiry:
                                                        if state_obj.get("last_pulse_timestamp"):
                                                            pos["entry_time"] = state_obj["last_pulse_timestamp"]
                                                            break
                                                except:
                                                    continue
                                    except Exception:
                                        pass
                        
                        # Find matching strike and expiry across recent pulses (only after entry_time)
                        chain_item = None
                        pos_entry_time = str(pos.get("entry_time", ""))
                        
                        # 1. Try exact match in latest pulse
                        if pos_expiry != "N/A" and (strike, pos_expiry) in latest_chain:
                            chain_item = latest_chain[(strike, pos_expiry)]
                            pos["is_fallback_data"] = False
                        else:
                            # 2. Search backward in recent pulses (max 3 previous pulses = 1.5 hours, and only >= entry_time)
                            for p_obj in pulses_chain_data[1:4]:
                                if not pos_entry_time or p_obj["timestamp"] >= pos_entry_time[:19]:
                                    if pos_expiry != "N/A" and (strike, pos_expiry) in p_obj["chain"]:
                                        chain_item = p_obj["chain"][(strike, pos_expiry)]
                                        pos["is_fallback_data"] = False
                                        break
                        
                        # 3. If still not found, fallback to strike match in latest pulse
                        if not chain_item and strike in latest_strike_chain:
                            chain_item = latest_strike_chain[strike]
                            pos["is_fallback_data"] = True
                            
                        if chain_item:
                            mid_price = chain_item.get("mid")
                            
                            # Inject Delta (We DO NOT overwrite Expiry or DTE with fallback lies)
                            if "delta" in chain_item:
                                pos["delta"] = chain_item["delta"]
                            
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
    """Dynamically reconstructs account balance and net liquidation history using trades log and DB snapshots."""
    portfolio_path = DATA_DIR / "portfolio.json"
    trades_path = DATA_DIR / "trades_log.csv"
    db_path = DATA_DIR / "hermes_brain.db"
    
    if not portfolio_path.exists():
        return []
        
    start_date = datetime(2026, 5, 14).date()
    end_date = datetime.now().date()
    
    # 1. Reconstruct Cash from trades_log.csv
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
                    if timestamp_str:
                        date_key = datetime.strptime(timestamp_str.split(' ')[0], "%Y-%m-%d").date()
                        if date_key not in trades_by_date:
                            trades_by_date[date_key] = []
                        trades_by_date[date_key].append((action, price))
        except Exception as e:
            print(f"Error parsing trades log: {e}")
            
    # 2. Reconstruct Net Liquidation from hermes_brain.db
    db_nlv_by_date = {}
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.execute("SELECT timestamp, raw_input_json FROM pulse_history ORDER BY id ASC")
            for row in cur.fetchall():
                ts_str = row[0]
                date_key = datetime.strptime(ts_str.split(' ')[0], "%Y-%m-%d").date()
                j = json.loads(row[1])
                
                # The DB 'net_liquidation_value' historically just tracked Total Cash
                raw_cash = j.get('portfolio_summary', {}).get('net_liquidation_value', 250000.0)
                
                # Calculate liability of open positions
                active_positions = j.get('active_positions', [])
                liability = 0
                for pos in active_positions:
                    if pos.get('type') == 'Option':
                        price = pos.get('current_premium', pos.get('avg_cost', 0))
                        liability += price * 100
                        
                true_nlv = raw_cash - liability
                
                # Overwrites with the latest pulse of the day
                db_nlv_by_date[date_key] = float(true_nlv)
            conn.close()
        except Exception as e:
            print(f"Error parsing database for NLV: {e}")
            
    # Overwrite the most recent/current day with LIVE portfolio data so the chart matches the live metric cards
    try:
        live_port = get_portfolio()
        if live_port:
            live_cash = live_port.get('total_cash', 250000.0)
            live_liab = 0
            for pos in live_port.get('positions', []):
                if pos.get('type') == 'Option':
                    # get_portfolio injects current_price automatically
                    live_liab += (pos.get('current_price', pos.get('avg_cost', 0)) * 100 * pos.get('quantity', 1))
            db_nlv_by_date[end_date] = float(live_cash - live_liab)
    except Exception as e:
        print(f"Error fetching live portfolio for NLV: {e}")
            
    history = []
    running_cash = 250000.0
    last_known_nlv = 250000.0
    
    current_date = start_date
    while current_date <= end_date:
        if current_date in trades_by_date:
            for action, price in trades_by_date[current_date]:
                if action == 'SELL_PUT' or action == 'SELL_CALL':
                    running_cash += price * 100
                elif action == 'BUY_CLOSE' or action == 'BUY_TO_CLOSE':
                    running_cash -= price * 100
                elif action == 'ROLL_PUT' or action == 'ROLL_CALL':
                    running_cash += price * 100
                    
        if current_date in db_nlv_by_date:
            last_known_nlv = db_nlv_by_date[current_date]
            
        history.append({
            "timestamp": current_date.strftime("%Y-%m-%d"),
            "total_cash": round(running_cash, 2),
            "net_liquidation": round(last_known_nlv, 2),
            "balance": round(last_known_nlv, 2)  # Return NLV as balance for existing frontend charts
        })
        current_date += timedelta(days=1)
        
    return history


# ===========================================================================
# INSTITUTIONAL ANALYTICS ENDPOINTS — Added for Full Dashboard Build
# ===========================================================================

@app.get("/api/analytics/master_chart")
def get_master_chart():
    """
    Returns the COMPLETE market regime timeline from the very first pulse to now.
    Every 30-min data point. Includes AAPL price, VIX, 200 SMA, 50 SMA, IV30 rank,
    day classification, earnings countdown, and all trade event markers.
    This powers the full multi-indicator Chart A in the dashboard.
    """
    db_path = DATA_DIR / "hermes_brain.db"
    trades_path = DATA_DIR / "trades_log.csv"

    if not db_path.exists():
        return {"pulses": [], "events": []}

    pulses = []
    events = []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, timestamp, aapl_price, vix_level, earnings_days,
                   ai_decision, ai_reasoning, raw_input_json
            FROM pulse_history
            ORDER BY timestamp ASC
        """)
        rows = cursor.fetchall()

        for row in rows:
            row_dict = dict(row)
            pulse_point = {
                "id": row_dict["id"],
                "timestamp": row_dict["timestamp"],
                "aapl_price": row_dict["aapl_price"],
                "vix_level": row_dict["vix_level"],
                "earnings_days": row_dict["earnings_days"],
                "ai_decision": row_dict["ai_decision"],
                "sma_200": None,
                "sma_50": None,
                "iv_rank": None,
                "day_classification": None,
            }

            # Parse the rich raw_input_json for market regime data
            if row_dict.get("raw_input_json"):
                try:
                    raw = json.loads(row_dict["raw_input_json"])
                    # Market regime keys (varies slightly by version)
                    regime = raw.get("market_regime", raw.get("regime", {}))
                    if isinstance(regime, dict):
                        pulse_point["sma_200"] = regime.get("sma_200") or regime.get("200_sma")
                        pulse_point["sma_50"] = regime.get("sma_50") or regime.get("50_sma")
                        pulse_point["day_classification"] = regime.get("day_classification") or regime.get("classification")

                    # IV rank stored at top level or in market_data
                    pulse_point["iv_rank"] = (
                        raw.get("iv30_rank")
                        or raw.get("iv_rank")
                        or raw.get("market_data", {}).get("iv30_rank")
                    )
                except Exception:
                    pass

            pulses.append(pulse_point)

        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {str(e)}")

    # Build trade event markers from trades_log.csv
    if trades_path.exists():
        try:
            with open(trades_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    action = row.get("action", "")
                    if action in ("SELL_PUT", "ROLL_PUT_CLOSE", "ROLL_PUT_OPEN",
                                  "CLOSE_FOR_PROFIT", "SELL_CALL", "BUY_CLOSE"):
                        events.append({
                            "timestamp": row.get("timestamp", ""),
                            "action": action,
                            "strike": row.get("strike"),
                            "expiry": row.get("expiry"),
                            "price": row.get("price"),
                            "pnl_realized": row.get("pnl_realized"),
                        })
        except Exception:
            pass

    return {"pulses": pulses, "events": events}


@app.get("/api/analytics/slot_lifecycle")
def get_slot_lifecycle():
    """
    Reconstructs the complete per-slot contract genealogy from trades_log.csv
    and overlays per-pulse Delta, DTE, and unrealized PnL% by parsing raw_input_json.
    Returns one entry per slot (1-4) with its full roll chain and time-series metrics.
    Powers the Slot Lifecycle Swimlane charts (Graph B) in the dashboard.
    """
    db_path = DATA_DIR / "hermes_brain.db"
    trades_path = DATA_DIR / "trades_log.csv"

    # ---- Step 1: Build raw trade list ordered by time ----
    raw_trades = []
    if trades_path.exists():
        try:
            with open(trades_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_trades.append({
                        "timestamp": row.get("timestamp", ""),
                        "action": row.get("action", ""),
                        "strike": float(row.get("strike", 0) or 0),
                        "expiry": row.get("expiry", ""),
                        "price": float(row.get("price", 0) or 0),
                        "pnl_realized": float(row.get("pnl_realized", 0) or 0),
                    })
        except Exception:
            pass

    # ---- Step 2: Assign slots by first-sell ordering ----
    slots = {}       # slot_num -> list of generations {open, close, events}
    slot_contract = {}  # slot_num -> current (strike, expiry)
    sell_events = [t for t in raw_trades if t["action"] in ("SELL_PUT", "SELL_CALL", "ROLL_PUT_OPEN")]
    slot_counter = 1

    # Reconstruct slot assignment: each SELL_PUT that is NOT a ROLL_PUT_OPEN gets a slot
    slot_opens = [t for t in raw_trades if t["action"] == "SELL_PUT"]
    for i, ev in enumerate(slot_opens):
        snum = i + 1
        slots[snum] = [{
            "generation": 1,
            "open_time": ev["timestamp"],
            "open_strike": ev["strike"],
            "open_expiry": ev["expiry"],
            "open_price": ev["price"],
            "close_time": None,
            "close_price": None,
            "pnl_realized": None,
            "close_action": None,
            "rolls": []
        }]
        slot_contract[snum] = (ev["strike"], ev["expiry"])

    # ---- Step 3: Attach rolls and closes ----
    # Match ROLL_PUT_CLOSE → ROLL_PUT_OPEN pairs by timestamp+pulse alignment
    i = 0
    while i < len(raw_trades):
        ev = raw_trades[i]
        if ev["action"] == "ROLL_PUT_CLOSE":
            # Find the matching slot by (strike, expiry)
            matched_slot = None
            for snum, current in slot_contract.items():
                if current[0] == ev["strike"] and current[1] == ev["expiry"]:
                    matched_slot = snum
                    break
            # Find the matching ROLL_PUT_OPEN at same timestamp
            open_ev = None
            for j in range(i + 1, min(i + 10, len(raw_trades))):
                if (raw_trades[j]["action"] == "ROLL_PUT_OPEN"
                        and raw_trades[j]["timestamp"] == ev["timestamp"]
                        and raw_trades[j]["strike"] != ev["strike"] or
                        raw_trades[j]["expiry"] != ev["expiry"]):
                    open_ev = raw_trades[j]
                    break
            if matched_slot and open_ev:
                # Close current generation
                if slots[matched_slot]:
                    slots[matched_slot][-1]["close_time"] = ev["timestamp"]
                    slots[matched_slot][-1]["close_price"] = ev["price"]
                    slots[matched_slot][-1]["close_action"] = "ROLLED"
                    slots[matched_slot][-1]["pnl_realized"] = ev["pnl_realized"]
                # Open new generation
                gen_num = len(slots[matched_slot]) + 1
                slots[matched_slot].append({
                    "generation": gen_num,
                    "open_time": open_ev["timestamp"],
                    "open_strike": open_ev["strike"],
                    "open_expiry": open_ev["expiry"],
                    "open_price": open_ev["price"],
                    "close_time": None,
                    "close_price": None,
                    "pnl_realized": None,
                    "close_action": None,
                    "rolls": []
                })
                slot_contract[matched_slot] = (open_ev["strike"], open_ev["expiry"])
        elif ev["action"] in ("CLOSE_FOR_PROFIT", "BUY_CLOSE"):
            for snum, current in slot_contract.items():
                if current[0] == ev["strike"] and current[1] == ev["expiry"]:
                    if slots[snum]:
                        slots[snum][-1]["close_time"] = ev["timestamp"]
                        slots[snum][-1]["close_price"] = ev["price"]
                        slots[snum][-1]["close_action"] = "CLOSED_PROFIT"
                        slots[snum][-1]["pnl_realized"] = ev["pnl_realized"]
                    break
        i += 1

    # ---- Step 4: Extract per-pulse per-slot time series from DB ----
    pulse_series = {}  # (strike, expiry) -> list of {timestamp, delta, dte, pnl_pct}
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT timestamp, raw_input_json FROM pulse_history ORDER BY timestamp ASC")
            for row in cur.fetchall():
                ts = row[0]
                if not row[1]:
                    continue
                try:
                    raw = json.loads(row[1])
                    positions = raw.get("active_positions", raw.get("positions", []))
                    for pos in positions:
                        strike = float(pos.get("strike", 0) or pos.get("current_option_strike", 0) or 0)
                        expiry = str(pos.get("expiry", "") or pos.get("current_option_expiry", "") or "")
                        if strike == 0 or not expiry:
                            continue
                        key = (strike, expiry)
                        delta = pos.get("delta") or pos.get("current_delta")
                        dte = pos.get("dte") or pos.get("days_to_expiry")
                        pnl_pct = pos.get("profit_pct") or pos.get("pnl_pct") or pos.get("unrealized_pnl_pct")
                        if key not in pulse_series:
                            pulse_series[key] = []
                        pulse_series[key].append({
                            "timestamp": ts,
                            "delta": delta,
                            "dte": dte,
                            "pnl_pct": pnl_pct
                        })
                except Exception:
                    continue
            conn.close()
        except Exception:
            pass

    # ---- Step 5: Attach time series to each generation ----
    result = []
    for snum in sorted(slots.keys()):
        generations = slots[snum]
        enriched_gens = []
        for gen in generations:
            key = (gen["open_strike"], gen["open_expiry"])
            series = pulse_series.get(key, [])
            enriched_gens.append({**gen, "time_series": series})
        result.append({
            "slot": snum,
            "generations": enriched_gens,
            "current_contract": slot_contract.get(snum)
        })

    return result


@app.get("/api/analytics/kpi_summary")
def get_kpi_summary():
    """
    Computes the key performance indicators for the KPI banner:
    - Win rate (% contracts closed for profit vs rolled defensively)
    - Total premium collected (gross)
    - Total roll costs (defensive debit payments)
    - Net realized PnL
    - Days since strategy inception
    - Annualized yield on $250k capital
    - Estimated daily theta velocity (avg cash per day)
    - Total pulses run
    """
    trades_path = DATA_DIR / "trades_log.csv"
    db_path = DATA_DIR / "hermes_brain.db"

    STARTING_CAPITAL = 250000.0
    inception_date = datetime(2026, 5, 27).date()
    today = datetime.now().date()
    days_running = max((today - inception_date).days, 1)

    total_premium_collected = 0.0
    total_roll_debits = 0.0
    net_realized_pnl = 0.0
    profit_closes = 0
    defensive_rolls = 0
    total_trades = 0

    if trades_path.exists():
        try:
            with open(trades_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    action = row.get("action", "")
                    price = float(row.get("price", 0) or 0)
                    pnl = float(row.get("pnl_realized", 0) or 0)
                    total_trades += 1

                    if action in ("SELL_PUT", "SELL_CALL", "ROLL_PUT_OPEN"):
                        total_premium_collected += price * 100
                    elif action in ("ROLL_PUT_CLOSE", "BUY_CLOSE"):
                        total_roll_debits += price * 100
                        net_realized_pnl += pnl
                        if pnl < 0:
                            defensive_rolls += 1
                    elif action == "CLOSE_FOR_PROFIT":
                        profit_closes += 1
                        net_realized_pnl += pnl
        except Exception:
            pass

    total_closes = profit_closes + defensive_rolls
    win_rate = round((profit_closes / total_closes * 100), 1) if total_closes > 0 else 0.0
    annualized_yield = round((net_realized_pnl / STARTING_CAPITAL) * (365 / days_running) * 100, 2)
    daily_theta = round(net_realized_pnl / days_running, 2)

    # Pulse count from DB
    total_pulses = 0
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute("SELECT COUNT(*) FROM pulse_history").fetchone()
            total_pulses = row[0] if row else 0
            conn.close()
        except Exception:
            pass

    return {
        "days_running": days_running,
        "inception_date": str(inception_date),
        "total_pulses": total_pulses,
        "total_premium_collected": round(total_premium_collected, 2),
        "net_premium_retained": round(total_premium_collected - total_roll_debits, 2),
        "total_roll_debits": round(total_roll_debits, 2),
        "net_realized_pnl": round(net_realized_pnl, 2),
        "profit_closes": profit_closes,
        "defensive_rolls": defensive_rolls,
        "win_rate_pct": win_rate,
        "annualized_yield_pct": annualized_yield,
        "daily_theta_velocity": daily_theta,
        "starting_capital": STARTING_CAPITAL,
    }
