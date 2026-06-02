import sys
import json
import os
import asyncio
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.parse
from core.database import HermesDatabase

# ─────────────────────────────────────────────
# CONFIG — Universal Paths
# ─────────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).parent.parent
DATA_DIR       = PROJECT_ROOT / 'data'
STATE_PATH     = DATA_DIR / 'trade_state.json'
PORTFOLIO_PATH = DATA_DIR / 'portfolio.json'
TRACKER_PATH   = DATA_DIR / 'intraday_tracker.json'
MEMORY_PATH    = PROJECT_ROOT / '.hermes' / 'MEMORY.md'
EYE_CACHE_PATH = PROJECT_ROOT / '.eye_cache.json'
STATE_HISTORY_PATH = PROJECT_ROOT / 'trade_state_history.jsonl'
TRADES_CSV_PATH    = DATA_DIR / 'trades_log.csv'

MIN_PREMIUM_YIELD_PCT = 1.0
if os.getenv("SIM_MODE") == "1":
    MIN_PREMIUM_YIELD_PCT = float(os.getenv("FORCE_YIELD", "1.0"))

SELL_DECISIONS  = {"SELL_NEW_PUT", "SELL_NEW_CALL"}
CLOSE_DECISIONS = {"CLOSE_FOR_PROFIT", "CLOSE_FOR_LOSS"}

def sim_log(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[EXECUTOR {ts}] {msg}", flush=True)

def extract_decision(raw_input: str) -> dict | None:
    candidates = []
    depth = 0
    start = -1
    for i, char in enumerate(raw_input):
        if char == '{':
            if depth == 0: start = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start != -1:
                candidates.append(raw_input[start:i+1].strip())
                start = -1
    for candidate in reversed(candidates):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                if 'decisions' in data and isinstance(data['decisions'], list):
                    return data
                elif 'decision' in data:
                    return {"decisions": [data]}
        except: continue
    return None

def send_telegram(text: str, is_critical: bool = False):
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if is_critical:
        text = f"🚨 CRITICAL ALERT\n{text}"
        
    if not token or not chat_id or "your_" in token:
        sim_log(f"Telegram not configured — skipping {'critical ' if is_critical else ''}alert.")
        return
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        req  = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10):
            sim_log(f"{'Critical ' if is_critical else ''}Telegram alert sent.")
    except Exception as e:
        sim_log(f"⚠️ TELEGRAM FAILED: {e}")

def _append_state_history(state: dict):
    try:
        snapshot = dict(state)
        snapshot["last_pulse_timestamp"] = datetime.now().isoformat()
        with open(STATE_HISTORY_PATH, 'a') as f:
            f.write(json.dumps(snapshot) + '\n')
    except: pass

def _append_trades_csv(action, symbol, strike, expiry, price, pnl, pulse_id):
    try:
        import csv
        file_exists = TRADES_CSV_PATH.exists()
        with open(TRADES_CSV_PATH, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "pulse_id", "symbol", "action", "strike", "expiry", "price", "pnl_realized"])
            writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), pulse_id, symbol, action, strike, expiry, price, pnl])
    except: pass

from core.utils import load_json, write_json, get_market_date, ValidationError, PolicyBlockError, PacingBlockError

def reset_and_load_tracker() -> dict:
    today_str = get_market_date()
    tracker = load_json(TRACKER_PATH)
    if not tracker or tracker.get("date") != today_str:
        tracker = {
            "date": today_str,
            "contracts_written_today": 0,
            "first_strike": None,
            "first_premium": None
        }
        write_json(TRACKER_PATH, tracker)
    return tracker

# ─────────────────────────────────────────────
# SIMULATION EXPIRATION & ASSIGNMENT
# ─────────────────────────────────────────────
def check_simulation_expirations(portfolio, eye_data, db, pulse_id) -> bool:
    positions = portfolio.get("positions", [])
    updated_positions = []
    changed = False
    
    current_price = eye_data.get("price_seen", 0.0)
    if current_price <= 0.0:
        return False
        
    for p in positions:
        if p.get("type") == "Option":
            expiry = p.get("expiry")
            dte = 99
            if expiry:
                expiry_formatted = expiry
                if '-' not in expiry and len(expiry) == 8:
                    expiry_formatted = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:]}"
                try:
                    today = datetime.now().date()
                    exp_date = datetime.strptime(expiry_formatted, '%Y-%m-%d').date()
                    dte = (exp_date - today).days
                except:
                    pass
            
            if dte <= 0:
                changed = True
                strike = float(p.get("strike", 0.0))
                opt_type = p.get("option_type", "PUT").upper()
                
                if opt_type == "PUT":
                    if current_price < strike:
                        sim_log(f"🔔 Simulation Assignment Triggered! PUT strike {strike} expired ITM (Price: {current_price}).")
                        stock_pos = next((pos for pos in updated_positions if pos.get("type") == "Stock" and pos.get("symbol") == "AAPL"), None)
                        if stock_pos:
                            old_qty = stock_pos.get("quantity", 0)
                            old_avg = stock_pos.get("avg_cost", 0.0)
                            new_qty = old_qty + 100
                            new_avg = round(((old_qty * old_avg) + (100 * strike)) / new_qty, 2)
                            stock_pos["quantity"] = new_qty
                            stock_pos["avg_cost"] = new_avg
                        else:
                            updated_positions.append({
                                "type": "Stock",
                                "symbol": "AAPL",
                                "quantity": 100,
                                "avg_cost": strike
                            })
                        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) - (strike * 100), 2)
                        
                        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ASSIGNMENT_PUT", "strike": strike, "price": strike, "pnl": 0.0})
                        _append_trades_csv("ASSIGNMENT_PUT", "AAPL", strike, expiry, strike, 0.0, pulse_id)
                        send_telegram(f"🔔 Put Option Strike {strike} assigned. Purchased 100 AAPL shares at {strike} (Market: {current_price}).")
                    else:
                        sim_log(f"💨 Option PUT strike {strike} expired worthless (Price: {current_price}).")
                        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "EXPIRED_PUT", "strike": strike, "price": 0.0, "pnl": 0.0})
                        _append_trades_csv("EXPIRED_PUT", "AAPL", strike, expiry, 0.0, 0.0, pulse_id)
                        send_telegram(f"💨 Put Option Strike {strike} expired worthless (Market: {current_price}).")
                        
                elif opt_type == "CALL":
                    if current_price > strike:
                        sim_log(f"🔔 Simulation Assignment Triggered! CALL strike {strike} expired ITM (Price: {current_price}).")
                        stock_pos = next((pos for pos in updated_positions if pos.get("type") == "Stock" and pos.get("symbol") == "AAPL"), None)
                        pnl = 0.0
                        if stock_pos and stock_pos.get("quantity", 0) >= 100:
                            pnl = round((strike - stock_pos["avg_cost"]) * 100, 2)
                            stock_pos["quantity"] -= 100
                            if stock_pos["quantity"] <= 0:
                                updated_positions.remove(stock_pos)
                        
                        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) + (strike * 100), 2)
                        portfolio["realized_pnl"] = round(portfolio.get("realized_pnl", 0.0) + pnl, 2)
                        
                        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ASSIGNMENT_CALL", "strike": strike, "price": strike, "pnl": pnl})
                        _append_trades_csv("ASSIGNMENT_CALL", "AAPL", strike, expiry, strike, pnl, pulse_id)
                        send_telegram(f"🔔 Call Option Strike {strike} assigned. AAPL shares called away at {strike} (PnL: {pnl}).")
                    else:
                        sim_log(f"💨 Option CALL strike {strike} expired worthless (Price: {current_price}).")
                        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "EXPIRED_CALL", "strike": strike, "price": 0.0, "pnl": 0.0})
                        _append_trades_csv("EXPIRED_CALL", "AAPL", strike, expiry, 0.0, 0.0, pulse_id)
                        send_telegram(f"💨 Call Option Strike {strike} expired worthless (Market: {current_price}).")
            else:
                updated_positions.append(p)
        else:
            updated_positions.append(p)
            
    if changed:
        portfolio["positions"] = updated_positions
    return changed

def update_macro_state(portfolio, state):
    positions = portfolio.get("positions", [])
    has_shares = False
    has_put = False
    has_call = False
    shares_pos = next((p for p in positions if p.get("type") == "Stock" and p.get("symbol") == "AAPL"), None)
    if shares_pos and shares_pos.get("quantity", 0) >= 100:
        has_shares = True
        
    for p in positions:
        if p.get("type") == "Option":
            if p.get("option_type") == "PUT":
                has_put = True
            elif p.get("option_type") == "CALL":
                has_call = True
                
    if has_shares and has_call:
        state["current_phase"] = "CC_ACTIVE"
    elif has_shares:
        state["current_phase"] = "ASSIGNED"
    elif has_put:
        state["current_phase"] = "CSP_ACTIVE"
    else:
        state["current_phase"] = "CASH_ONLY"
        
    state["assignment_confirmed_once"] = False
    
    # Store first option strike/expiry for backward compatibility
    opt = next((p for p in positions if p.get("type") == "Option"), None)
    if opt:
        state["current_option_strike"] = opt.get("strike")
        state["current_option_expiry"] = opt.get("expiry")
    else:
        state["current_option_strike"] = None
        state["current_option_expiry"] = None
    return state

# ─────────────────────────────────────────────
# POSITION MATCHING HELPERS
# ─────────────────────────────────────────────
def find_matching_option(positions, key=None, strike=None, expiry=None, opt_type=None):
    for p in positions:
        if p.get("type") != "Option": continue
        if key:
            p_strike = int(p.get("strike", 0))
            p_exp = p.get("expiry", "").replace('-', '')
            p_type = p.get("option_type", "PUT").upper()
            p_key = f"{p_type}_{p_strike}_{p_exp}"
            if p_key == key.replace('-', ''):
                return p
        if strike is not None and abs(p.get("strike", 0.0) - float(strike)) < 0.1:
            p_exp = p.get("expiry", "").replace('-', '')
            target_exp = expiry.replace('-', '') if expiry else None
            if not target_exp or p_exp == target_exp:
                if not opt_type or p.get("option_type", "PUT").upper() == opt_type.upper():
                    return p
    return None

# ─────────────────────────────────────────────
# VALIDATION GATES (Smart Guard)
# ─────────────────────────────────────────────
def validate_single_decision(dec, eye_data, portfolio):
    decision = dec.get('decision')
    state = load_json(STATE_PATH)
    
    if decision == "ROLL_PUT":
        key = dec.get("position_key")
        close_strike = dec.get("close_strike")
        matched = None
        for p in eye_data.get("active_positions", []):
            if p.get("type") == "Option":
                if key and p.get("position_key") == key:
                    matched = p
                    break
                elif close_strike and abs(p.get("strike", 0.0) - close_strike) < 0.1:
                    matched = p
                    break
        if matched:
            delta = abs(float(matched.get('delta', 0.0)))
            dte = int(matched.get('dte', 99))
            if dte <= 15 and delta >= 0.30:
                raise PolicyBlockError(f"Policy Block: ROLL_PUT rejected (Delta {delta} >= 0.30 AND DTE {dte} <= 15). [BLOCKED_ROLL_ITM_PUT] Accept assignment instead.")

    if decision in ["HOLD_PUT_POSITION", "HOLD_CALL_POSITION", "HOLD"]:
        key = dec.get("position_key")
        matched = None
        for p in eye_data.get("active_positions", []):
            if p.get("type") == "Option" and key and p.get("position_key") == key:
                matched = p
                break
        if matched:
            dte = int(matched.get('dte', 99))
            if dte < 1:
                sim_log(f"🚨 DTE < 1 for option {key}: Emergency Close Attempt Triggered.")
                dec['decision'] = 'CLOSE_FOR_PROFIT' 
                dec['is_emergency_close'] = True
                return dec, True

    if decision == "SELL_NEW_PUT":
        strike = dec.get("strike_to_trade")
        current_price = eye_data.get("price_seen", 0.0)
        sma_200 = eye_data.get("market_regime", {}).get("200_sma", 0.0)
        sma_50 = eye_data.get("market_regime", {}).get("50_sma", 0.0)
        
        # Hard SMA ceilings removed. Brain handles safe strike selection via dynamic Deltas.

    if decision == "SELL_NEW_PUT":
        summary = eye_data.get("portfolio_summary", {})
        risk_units = summary.get("current_risk_units", 0)
        day_class = eye_data.get("market_regime", {}).get("day_classification", "NORMAL_DAY")
        
        max_allowed_units = 1 if day_class == "BEARISH_DAY" else 4
        if risk_units >= max_allowed_units:
            raise PolicyBlockError(f"Policy Block: Max Risk Units ({max_allowed_units}) reached for regime {day_class}. Cannot write new Put.")
            
        tracker = reset_and_load_tracker()
        written = tracker.get("contracts_written_today", 0)
        day_class = eye_data.get("market_regime", {}).get("day_classification", "NORMAL_DAY")
        
        try:
            if written >= 2:
                raise PacingBlockError(f"Pacing Block: Daily cap (2) reached. Cannot write new Put.")
            elif written == 1:
                if day_class in ["QUIET_DAY", "BEARISH_DAY", "NORMAL_DAY"]:
                    raise PacingBlockError(f"Pacing Block: Daily cap (1) reached for regime {day_class}. Cannot write new Put.")
                elif day_class == "GOOD_DAY":
                    first_strike = tracker.get("first_strike")
                    first_premium = tracker.get("first_premium")
                    candidate_strike = dec.get("strike_to_trade")
                    candidate_premium = dec.get("premium_to_collect")
                    if first_strike and first_premium and candidate_strike and candidate_premium:
                        if not (candidate_strike < first_strike and candidate_premium >= first_premium):
                            raise PacingBlockError(f"Pacing Block: Better Option check failed (strike {candidate_strike} >= {first_strike} or premium {candidate_premium} < {first_premium}).")
        except PacingBlockError as e:
            dec['decision'] = 'HOLD_PUT_POSITION'
            dec['reason'] = str(e)
            return dec, True
                    
    return dec, False

def apply_single_yield_gate(dec):
    decision = dec.get('decision', '')
    if decision not in SELL_DECISIONS: return dec, False, None
    premium = dec.get('premium_to_collect')
    strike = dec.get('strike_to_trade')
    if premium is None or strike is None or strike == 0: return dec, False, None
    
    yield_pct = (premium / strike) * 100.0
    if yield_pct < MIN_PREMIUM_YIELD_PCT:
        reason = f"Yield {yield_pct:.2f}% < {MIN_PREMIUM_YIELD_PCT}% floor."
        dec = dict(dec)
        dec['decision'] = 'HOLD_PUT_POSITION'  # Valid token — do nothing, wait for better conditions
        return dec, True, reason
    return dec, False, None

# ─────────────────────────────────────────────
# DECISION TRANSACTION HANDLER
# ─────────────────────────────────────────────
def execute_decision(dec, db, pulse_id, eye_data=None):
    decision = dec.get('decision', 'UNKNOWN')
    portfolio = load_json(PORTFOLIO_PATH)
    state = load_json(STATE_PATH)
    tracker = reset_and_load_tracker()
    
    if "positions" not in portfolio: portfolio["positions"] = []
    
    if decision in ['HOLD_PUT_POSITION', 'HOLD_CALL_POSITION', 'HOLD_ASSIGNED_EQUITY', 'HOLD']:
        return "No Action"

    if decision == "SELL_NEW_PUT":
        # Null guard: LLM MUST provide these fields. If missing → clean error, not a crash.
        if not dec.get('strike_to_trade'):
            raise ValueError("SELL_NEW_PUT: LLM did not provide strike_to_trade. Rejecting decision.")
        if not dec.get('premium_to_collect'):
            raise ValueError("SELL_NEW_PUT: LLM did not provide premium_to_collect. Rejecting decision.")
        strike = float(dec.get('strike_to_trade'))
        premium = float(dec.get('premium_to_collect'))

        # ── OPTION 2: Read expiry directly from the AI's explicit choice ──
        # AI must output expiry_to_trade (YYYYMMDD) copied from the option chain row.
        # Normalize: strip any dashes the AI may accidentally include.
        ai_expiry = dec.get('expiry_to_trade')
        if ai_expiry:
            chosen_expiry = str(ai_expiry).replace('-', '').strip()
        else:
            # Safety fallback: use Python's pre-selected shortest expiry
            sim_log("⚠️ AI did not output expiry_to_trade — falling back to chosen_expiry")
            chosen_expiry = eye_data.get('chosen_expiry', 'N/A') if eye_data else 'N/A'
        
        portfolio["positions"].append({
            "type": "Option", 
            "symbol": "AAPL", 
            "strike": strike, 
            "avg_cost": premium, 
            "option_type": "PUT",
            "expiry": chosen_expiry
        })
        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) + (premium * 100), 2)
        
        tracker["contracts_written_today"] += 1
        if tracker["contracts_written_today"] == 1:
            tracker["first_strike"] = strike
            tracker["first_premium"] = premium
        write_json(TRACKER_PATH, tracker)
        
        state = update_macro_state(portfolio, state)
        
        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "SELL_PUT", "strike": strike, "expiry": chosen_expiry, "price": premium, "pnl": 0.0})
        _append_state_history(state)
        _append_trades_csv("SELL_PUT", "AAPL", strike, chosen_expiry, premium, 0.0, pulse_id)
        return f"SOLD PUT strike {strike}"

    elif decision == "SELL_NEW_CALL":
        strike = float(dec.get('strike_to_trade'))
        premium = float(dec.get('premium_to_collect'))

        # ── OPTION 2: Read expiry directly from the AI's explicit choice ──
        ai_expiry = dec.get('expiry_to_trade')
        if ai_expiry:
            chosen_expiry = str(ai_expiry).replace('-', '').strip()
        else:
            sim_log("⚠️ AI did not output expiry_to_trade — falling back to chosen_expiry")
            chosen_expiry = eye_data.get('chosen_expiry', 'N/A') if eye_data else 'N/A'
        
        portfolio["positions"].append({
            "type": "Option", 
            "symbol": "AAPL", 
            "strike": strike, 
            "avg_cost": premium, 
            "option_type": "CALL",
            "expiry": chosen_expiry
        })
        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) + (premium * 100), 2)
        
        state = update_macro_state(portfolio, state)
        
        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "SELL_CALL", "strike": strike, "expiry": chosen_expiry, "price": premium, "pnl": 0.0})
        _append_state_history(state)
        _append_trades_csv("SELL_CALL", "AAPL", strike, chosen_expiry, premium, 0.0, pulse_id)
        return f"SOLD CALL strike {strike}"

    elif decision in CLOSE_DECISIONS:
        key = dec.get("position_key")
        strike = dec.get("close_strike")
        expiry = dec.get("close_expiry")
        
        opt_pos = find_matching_option(portfolio["positions"], key=key, strike=strike, expiry=expiry)
        
        if not opt_pos:
            if dec.get('is_emergency_close'):
                raise ValueError("Emergency Close FAILED: Matching open option position not found in portfolio.")
            return "No Action (Matching position to close not found)"

        pnl = 0.0
        entry = opt_pos.get("avg_cost", 0.0)
        close = dec.get("premium_to_collect")
        if close is None:
            close = 0.0
            if eye_data and "option_chain" in eye_data:
                for row in eye_data["option_chain"]:
                    if abs(row.get("strike", 0.0) - opt_pos.get("strike", 0.0)) < 0.1:
                        close = row.get("mid", 0.0)
                        break
        else:
            close = float(close)
        pnl = round((entry - close) * 100, 2)
        portfolio["positions"] = [p for p in portfolio["positions"] if p != opt_pos]
        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) - (close * 100), 2)
        portfolio["realized_pnl"] = round(portfolio.get("realized_pnl", 0.0) + pnl, 2)
            
        state = update_macro_state(portfolio, state)
        
        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": decision, "strike": opt_pos.get("strike"), "expiry": opt_pos.get("expiry"), "price": close, "pnl": pnl})
        _append_state_history(state)
        _append_trades_csv(decision, "AAPL", opt_pos.get("strike"), opt_pos.get("expiry"), close, pnl, pulse_id)
        return f"CLOSED position {opt_pos.get('position_key')} for PnL: {pnl}"

    elif decision == "ROLL_PUT":
        key = dec.get("position_key")
        close_strike = dec.get("close_strike")
        close_expiry = dec.get("close_expiry")
        opt_pos = find_matching_option(portfolio["positions"], key=key, strike=close_strike, expiry=close_expiry, opt_type="PUT")
        
        pnl = 0.0
        if opt_pos:
            entry = opt_pos.get("avg_cost", 0.0)
            close = dec.get("close_details", {}).get("premium_to_pay")
            if close is None:
                close = 0.0
                if eye_data and "option_chain" in eye_data:
                    for row in eye_data["option_chain"]:
                        if abs(row.get("strike", 0.0) - opt_pos.get("strike", 0.0)) < 0.1:
                            close = row.get("mid", 0.0)
                            break
            pnl = round((entry - close) * 100, 2)
            portfolio["positions"] = [p for p in portfolio["positions"] if p != opt_pos]
            portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) - (close * 100), 2)
            portfolio["realized_pnl"] = round(portfolio.get("realized_pnl", 0.0) + pnl, 2)
            db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ROLL_PUT_CLOSE", "strike": opt_pos.get("strike"), "expiry": opt_pos.get("expiry"), "price": close, "pnl": pnl})
            _append_trades_csv("ROLL_PUT_CLOSE", "AAPL", opt_pos.get("strike"), opt_pos.get("expiry"), close, pnl, pulse_id)

        new_strike = dec.get('open_details', {}).get('strike_to_trade') or dec.get('strike_to_trade')
        new_premium = dec.get('open_details', {}).get('premium_to_collect') or dec.get('premium_to_collect')
        new_expiry = dec.get('open_details', {}).get('expiry_to_trade') or eye_data.get('chosen_expiry', 'N/A') if eye_data else 'N/A'
        
        if new_strike is None or new_premium is None:
            raise ValueError(f"ROLL_PUT details missing: new_strike={new_strike}, new_premium={new_premium}")
        
        portfolio["positions"].append({
            "type": "Option", 
            "symbol": "AAPL", 
            "strike": new_strike, 
            "avg_cost": new_premium, 
            "option_type": "PUT",
            "expiry": new_expiry
        })
        portfolio["total_cash"] = round(portfolio["total_cash"] + (new_premium * 100), 2)
        
        state = update_macro_state(portfolio, state)

        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ROLL_PUT_OPEN", "strike": new_strike, "expiry": new_expiry, "price": new_premium, "pnl": 0.0})
        _append_state_history(state)
        _append_trades_csv("ROLL_PUT_OPEN", "AAPL", new_strike, new_expiry, new_premium, pnl, pulse_id)
        return f"ROLLED PUT to strike {new_strike} (PnL: {pnl})"

    elif decision == "ROLL_CALL":
        key = dec.get("position_key")
        close_strike = dec.get("close_strike")
        close_expiry = dec.get("close_expiry")
        opt_pos = find_matching_option(portfolio["positions"], key=key, strike=close_strike, expiry=close_expiry, opt_type="CALL")
        
        pnl = 0.0
        if opt_pos:
            entry = opt_pos.get("avg_cost", 0.0)
            close = dec.get("close_details", {}).get("premium_to_pay")
            if close is None:
                close = 0.0
                if eye_data and "option_chain" in eye_data:
                    for row in eye_data["option_chain"]:
                        if abs(row.get("strike", 0.0) - opt_pos.get("strike", 0.0)) < 0.1:
                            close = row.get("mid", 0.0)
                            break
            pnl = round((entry - close) * 100, 2)
            portfolio["positions"] = [p for p in portfolio["positions"] if p != opt_pos]
            portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) - (close * 100), 2)
            portfolio["realized_pnl"] = round(portfolio.get("realized_pnl", 0.0) + pnl, 2)
            db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ROLL_CALL_CLOSE", "strike": opt_pos.get("strike"), "expiry": opt_pos.get("expiry"), "price": close, "pnl": pnl})
            _append_trades_csv("ROLL_CALL_CLOSE", "AAPL", opt_pos.get("strike"), opt_pos.get("expiry"), close, pnl, pulse_id)

        new_strike = dec.get('open_details', {}).get('strike_to_trade') or dec.get('strike_to_trade')
        new_premium = dec.get('open_details', {}).get('premium_to_collect') or dec.get('premium_to_collect')
        new_expiry = dec.get('open_details', {}).get('expiry_to_trade') or eye_data.get('chosen_expiry', 'N/A') if eye_data else 'N/A'
        
        if new_strike is None or new_premium is None:
            raise ValueError(f"ROLL_CALL details missing: new_strike={new_strike}, new_premium={new_premium}")
        
        portfolio["positions"].append({
            "type": "Option", 
            "symbol": "AAPL", 
            "strike": new_strike, 
            "avg_cost": new_premium, 
            "option_type": "CALL",
            "expiry": new_expiry
        })
        portfolio["total_cash"] = round(portfolio["total_cash"] + (new_premium * 100), 2)
        
        state = update_macro_state(portfolio, state)

        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ROLL_CALL_OPEN", "strike": new_strike, "expiry": new_expiry, "price": new_premium, "pnl": 0.0})
        _append_state_history(state)
        _append_trades_csv("ROLL_CALL_OPEN", "AAPL", new_strike, new_expiry, new_premium, pnl, pulse_id)
        return f"ROLLED CALL to strike {new_strike} (PnL: {pnl})"

    elif decision == "ABORT_DUE_TO_RISK":
        opts = [p for p in portfolio["positions"] if p.get("type") == "Option"]
        for opt_pos in opts:
            close = 0.0
            if eye_data and "option_chain" in eye_data:
                for row in eye_data["option_chain"]:
                    if abs(row.get("strike", 0.0) - opt_pos.get("strike", 0.0)) < 0.1:
                        close = row.get("mid", 0.0)
                        break
            portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) - (close * 100), 2)
            portfolio["positions"] = [p for p in portfolio["positions"] if p != opt_pos]
            
        stocks = [p for p in portfolio["positions"] if p.get("type") == "Stock"]
        for stock_pos in stocks:
            qty = stock_pos.get("quantity", 0)
            spot = eye_data.get("price_seen", 0.0) if eye_data else 0.0
            portfolio["total_cash"] = round(portfolio.get("total_cash", 250000.0) + (qty * spot), 2)
            portfolio["positions"] = [p for p in portfolio["positions"] if p != stock_pos]
            
        state.update({
            "current_phase": "CASH_ONLY",
            "current_option_strike": None,
            "current_option_expiry": None,
            "assignment_confirmed_once": False
        })
        
        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ABORT_DUE_TO_RISK"})
        _append_state_history(state)
        return "ABORTED ALL POSITIONS DUE TO RISK"
        
    raise ValueError(f"Unknown decision: {decision}")

def build_critical_payload(decision_data, eye_data, error_msg, state):
    payload = (
        f"DECISIONS COUNT: {len(decision_data.get('decisions', []))}\n"
        f"STATE: {state.get('current_phase')}\n"
        f"PRICE: {eye_data.get('price_seen', 'N/A')}\n"
        f"ERROR: {error_msg}"
    )
    return payload

def build_memory_summary(decisions, state, portfolio, eye_data, action_results, ai_override, override_reason):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    summary = f"🤖 AAPL Pulse Execution\nTime: {timestamp}\n"
    if ai_override: 
        summary += f"⚠️ OVERRIDE: {override_reason}\n"
    summary += "\nDECISIONS RUN:\n"
    for i, dec in enumerate(decisions):
        act = dec.get('decision')
        res = action_results[i] if i < len(action_results) else "Not executed"
        reason = dec.get('reason', 'N/A')
        summary += f"{i+1}. Action: {act} -> {res}\n   Reason: {reason}\n"
    return summary

async def main_executor():
    sim_log("═══ Hermes Executor Starting ═══")
    raw_brain_output = sys.stdin.read()
    decision_data = extract_decision(raw_brain_output)
    if not decision_data:
        error_msg = (
            f"🚨 HERMES: LLM returned unparseable output.\n"
            f"Raw output (first 300 chars):\n{raw_brain_output[:300]}\n"
            f"Pulse aborted. Check OpenAI response format."
        )
        sim_log("Invalid AI Output format. Pulse aborted.")
        send_telegram(error_msg, is_critical=True)
        sys.exit(1)

    eye_data = load_json(EYE_CACHE_PATH)
    state = load_json(STATE_PATH)
    portfolio = load_json(PORTFOLIO_PATH)
    db = HermesDatabase()
    
    # 1. State Awareness (Assignment Detection) & Simulated Expiry Check
    if os.getenv("SIM_MODE") == "1":
        # Pre-assign trade pulse_id 0 to check expirations
        if check_simulation_expirations(portfolio, eye_data, db, 0):
            write_json(PORTFOLIO_PATH, portfolio)
        portfolio = load_json(PORTFOLIO_PATH)
        state = load_json(STATE_PATH)
        state = update_macro_state(portfolio, state)
        write_json(STATE_PATH, state)

    # Reset day tracking
    reset_and_load_tracker()
    
    # Pre-save pulse to DB (using blank/synthesized decisions first)
    pulse_id = db.save_pulse(eye_data, {"decision": "PENDING", "reason": "Execution in progress"})
    
    dec_list = decision_data.get("decisions", [])

    # Guard: LLM returned empty decisions array — this is a silent no-op.
    # Alert and abort so we can investigate.
    if not dec_list:
        warning_msg = (
            f"⚠️ HERMES: LLM returned empty decisions array.\n"
            f"Raw output: {raw_brain_output[:300]}\n"
            f"No actions taken this pulse. Investigate LLM reasoning."
        )
        sim_log("LLM returned empty decisions array. No actions taken.")
        # Clean up the PENDING DB row so it does not stay orphaned forever
        db.update_pulse(pulse_id,
                        {"decision": "EMPTY_DECISIONS", "reason": "LLM returned empty decisions array. No actions taken."},
                        ai_override=True, override_reason="Empty decisions array from LLM")
        send_telegram(warning_msg, is_critical=False)
        return

    # Sort: execute closes first to release margin, then opens
    close_legs = []
    open_legs = []
    for d in dec_list:
        if d.get("decision") in CLOSE_DECISIONS or d.get("decision") in ["ROLL_PUT", "ROLL_CALL", "ABORT_DUE_TO_RISK"]:
            close_legs.append(d)
        else:
            open_legs.append(d)
    sorted_decisions = close_legs + open_legs
    
    action_results = []
    ai_override = False
    override_reason = None
    processed_decisions = []
    
    try:
        for dec in sorted_decisions:
            # 2. Validation Interlock (The Smart Guard)
            dec, v_override = validate_single_decision(dec, eye_data, portfolio)
            
            # 3. Yield Gate
            dec, y_override, y_reason = apply_single_yield_gate(dec)
            
            if v_override or y_override:
                ai_override = True
                override_reason = "DTE Safety" if v_override else y_reason
            
            # Update state in loop for next check validation
            portfolio = load_json(PORTFOLIO_PATH)
            
            action_result = execute_decision(dec, db, pulse_id, eye_data)
            sim_log(f"Action Result: {action_result}")
            
            action_results.append(action_result)
            processed_decisions.append(dec)
            
        # Synthesize database columns
        decision_summary = ", ".join(d.get("decision") for d in processed_decisions)
        reasoning_summary = " | ".join(d.get("reason", "N/A") for d in processed_decisions)
        
        # Update the pre-saved PENDING row with final decisions (no new row created)
        db_decision_data = dict(decision_data)
        db_decision_data['decision'] = decision_summary
        db_decision_data['reason'] = reasoning_summary
        db.update_pulse(pulse_id, db_decision_data, ai_override=ai_override, override_reason=override_reason)

        
        summary = build_memory_summary(processed_decisions, state, portfolio, eye_data, action_results, ai_override, override_reason)
        
        # Audit Trail First
        try:
            with open(MEMORY_PATH, 'a') as f: f.write(f"--- PULSE #{pulse_id} ---\n{summary}\n\n")
        except: pass
        
        # Telegram Last
        send_telegram(summary)
        
    except Exception as e:
        error_msg = str(e)
        sim_log(f"🚨 CRITICAL ERROR: {error_msg}")
        
        payload = build_critical_payload(decision_data, eye_data, error_msg, state)
        send_telegram(payload, is_critical=True)
        
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main_executor())
