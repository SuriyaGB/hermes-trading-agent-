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
MEMORY_PATH    = PROJECT_ROOT / '.hermes' / 'MEMORY.md'
EYE_CACHE_PATH = PROJECT_ROOT / '.eye_cache.json'
STATE_HISTORY_PATH = PROJECT_ROOT / 'trade_state_history.jsonl'
TRADES_CSV_PATH    = DATA_DIR / 'trades_log.csv'

MIN_PREMIUM_YIELD_PCT = 1.0

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
            if isinstance(data, dict) and 'decision' in data:
                return data
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

def load_json(path: Path) -> dict:
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return {}

def write_json(path: Path, data: dict):
    with open(path, 'w') as f: json.dump(data, f, indent=2)

def detect_assignment(portfolio, state):
    """
    Implements the 2-pulse verification rule for assignment detection.
    Prevents state-flipping during settlement lag.
    """
    positions = portfolio.get("positions", [])
    shares = next((p for p in positions if p.get("type") == "Stock" and p.get("symbol") == "AAPL"), None)
    share_count = shares.get("quantity", 0) if shares else 0
    
    current_phase = state.get("current_phase", "CASH_ONLY")
    confirmed_once = state.get("assignment_confirmed_once", False)
    
    if current_phase == "CSP_ACTIVE" and share_count >= 100:
        if confirmed_once:
            # 2nd Pulse Confirmed -> Transition
            sim_log("✅ Assignment Verified (2/2 Pulses). Transitioning to ASSIGNED.")
            state["current_phase"] = "ASSIGNED"
            state["assignment_confirmed_once"] = False
            state["current_option_strike"] = None # Put is gone
        else:
            # 1st Pulse Seen
            sim_log("🔍 Assignment Detected (1/2 Pulses). Waiting for settlement verification.")
            state["assignment_confirmed_once"] = True
    else:
        # Reset if shares disappear or we aren't in CSP phase
        if confirmed_once:
            sim_log("ℹ️ Assignment verification reset (shares cleared or phase changed).")
        state["assignment_confirmed_once"] = False
        
    return state

def validate_decision(decision_data, eye_data, state):
    decision = decision_data.get('decision')
    phase = state.get('current_phase', 'CASH_ONLY')
    
    # 1. STRATEGIC POLICY GATE (Delta Guard)
    if decision == "ROLL_PUT":
        delta = abs(float(eye_data.get('delta_current', 0)))
        dte = int(eye_data.get('dte_current', 99))
        # POLICY: Roll only if Delta > 0.45 or we are near expiration (< 21 days)
        if delta < 0.45 and dte >= 21:
            raise ValueError(f"Policy Block: ROLL rejected (Delta {delta} < 0.45 AND DTE {dte} >= 21).")

    # 2. EMERGENCY DTE GATE (Hard Safety)
    if (decision == "HOLD_PUT_POSITION" or decision == "HOLD_CALL_POSITION"):
        dte = int(eye_data.get('dte_current', 99))
        if dte < 1:
            sim_log("🚨 DTE < 1: Emergency Close Attempt Triggered.")
            # We explicitly override the decision and mark it as an emergency attempt
            decision_data['decision'] = 'CLOSE_FOR_PROFIT' 
            decision_data['is_emergency_close'] = True
            return decision_data, True

    # 3. PHASE CONSISTENCY GATE
    if decision == "SELL_NEW_PUT" and phase != "CASH_ONLY":
        raise ValueError(f"Phase Block: Cannot SELL_PUT while in {phase} phase.")
    
    if decision == "SELL_NEW_CALL" and phase != "ASSIGNED":
        raise ValueError(f"Phase Block: Cannot SELL_CALL while in {phase} phase.")

    return decision_data, False

def apply_yield_gate(decision_data: dict):
    decision = decision_data.get('decision', '')
    if decision not in SELL_DECISIONS: return decision_data, False, None
    premium = decision_data.get('premium_to_collect')
    strike = decision_data.get('strike_to_trade')
    if premium is None or strike is None or strike == 0: return decision_data, False, None
    
    yield_pct = (premium / strike) * 100.0
    if yield_pct < MIN_PREMIUM_YIELD_PCT:
        reason = f"Yield {yield_pct:.2f}% < {MIN_PREMIUM_YIELD_PCT}% floor."
        decision_data = dict(decision_data)
        decision_data['decision'] = 'WAIT_FOR_ENTRY'
        return decision_data, True, reason
    return decision_data, False, None

def build_critical_payload(decision_data, eye_data, error_msg, state):
    payload = (
        f"DECISION: {decision_data.get('decision')}\n"
        f"STATE: {state.get('current_phase')}\n"
        f"PRICE: {eye_data.get('price_seen', 'N/A')}\n"
        f"DELTA: {eye_data.get('delta_current', 'N/A')}\n"
        f"DTE: {eye_data.get('dte_current', 'N/A')}\n"
        f"ERROR: {error_msg}"
    )
    return payload

def build_memory_summary(decision, state, portfolio, eye_data, action_result, ai_override, override_reason):
    action = decision.get('decision')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    summary = f"🤖 AAPL Pulse: {action}\nTime: {timestamp}\nAction: {action_result}\n"
    if ai_override: summary += f"⚠️ OVERRIDE: {override_reason}\n"
    summary += f"Reason: {decision.get('reason', 'N/A')}"
    return summary

def execute_decision(decision_data, db, pulse_id):
    decision = decision_data.get('decision', 'UNKNOWN')
    portfolio = load_json(PORTFOLIO_PATH)
    state = load_json(STATE_PATH)
    
    # Defensive initialization of positions
    if "positions" not in portfolio: portfolio["positions"] = []
    
    if decision == 'HOLD_PUT_POSITION' or decision == 'WAIT_FOR_ENTRY':
        return "No Action"

    # --- HANDLER: SELL_NEW_PUT ---
    if decision == "SELL_NEW_PUT":
        strike = decision_data.get('strike_to_trade')
        premium = decision_data.get('premium_to_collect')
        expiry = decision_data.get('dte_seen', 'N/A')
        
        portfolio["positions"].append({"type": "Option", "symbol": "AAPL", "strike": strike, "avg_cost": premium, "option_type": "PUT"})
        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000) + (premium * 100), 2)
        state.update({"current_phase": "CSP_ACTIVE", "current_option_strike": strike})
        
        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "SELL_PUT", "strike": strike, "price": premium, "pnl": 0.0})
        _append_state_history(state)
        _append_trades_csv("SELL_PUT", "AAPL", strike, expiry, premium, 0.0, pulse_id)
        return f"SOLD PUT strike {strike}"

    # --- HANDLER: SELL_NEW_CALL ---
    elif decision == "SELL_NEW_CALL":
        strike = decision_data.get('strike_to_trade')
        premium = decision_data.get('premium_to_collect')
        expiry = decision_data.get('dte_seen', 'N/A')
        
        portfolio["positions"].append({"type": "Option", "symbol": "AAPL", "strike": strike, "avg_cost": premium, "option_type": "CALL"})
        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000) + (premium * 100), 2)
        state.update({"current_phase": "CC_ACTIVE", "current_option_strike": strike})
        
        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "SELL_CALL", "strike": strike, "price": premium, "pnl": 0.0})
        _append_state_history(state)
        _append_trades_csv("SELL_CALL", "AAPL", strike, expiry, premium, 0.0, pulse_id)
        return f"SOLD CALL strike {strike}"

    # --- HANDLER: CLOSE_FOR_PROFIT / LOSS ---
    elif decision in CLOSE_DECISIONS:
        opt_pos = next((p for p in portfolio["positions"] if p.get("type") == "Option"), None)
        
        # If DTE safety triggered but no position found, this is a failure
        if not opt_pos:
            if decision_data.get('is_emergency_close'):
                raise ValueError("Emergency Close FAILED: No open option position found in portfolio.")
            return "No Action (No position to close)"

        pnl = 0.0
        entry = opt_pos.get("avg_cost", 0)
        close = decision_data.get("premium_to_collect", 0)
        pnl = round((entry - close) * 100, 2)
        portfolio["positions"] = [p for p in portfolio["positions"] if p != opt_pos]
        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000) - (close * 100), 2)
        portfolio["realized_pnl"] = round(portfolio.get("realized_pnl", 0) + pnl, 2)
            
        state.update({"current_phase": "CASH_ONLY", "current_option_strike": None})
        
        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": decision, "pnl": pnl})
        _append_state_history(state)
        _append_trades_csv(decision, "AAPL", None, None, None, pnl, pulse_id)
        return f"CLOSED for {pnl}"

    # --- HANDLER: ROLL_PUT (The Maneuver) ---
    elif decision == "ROLL_PUT":
        # 1. Close current
        opt_pos = next((p for p in portfolio["positions"] if p.get("type") == "Option"), None)
        pnl = 0.0
        if opt_pos:
            entry = opt_pos.get("avg_cost", 0)
            close = decision_data.get("close_details", {}).get("premium_to_pay", 0)
            pnl = round((entry - close) * 100, 2)
            portfolio["positions"] = [p for p in portfolio["positions"] if p != opt_pos]
            portfolio["total_cash"] = round(portfolio.get("total_cash", 250000) - (close * 100), 2)
            portfolio["realized_pnl"] = round(portfolio.get("realized_pnl", 0) + pnl, 2)

        # 2. Open new
        new_strike = decision_data.get('open_details', {}).get('strike_to_trade')
        new_premium = decision_data.get('open_details', {}).get('premium_to_collect')
        new_expiry = decision_data.get('open_details', {}).get('dte_seen', 'N/A')
        
        portfolio["positions"].append({"type": "Option", "symbol": "AAPL", "strike": new_strike, "avg_cost": new_premium, "option_type": "PUT"})
        portfolio["total_cash"] = round(portfolio["total_cash"] + (new_premium * 100), 2)
        state.update({"current_phase": "CSP_ACTIVE", "current_option_strike": new_strike})

        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ROLL_PUT_CLOSE", "pnl": pnl})
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "ROLL_PUT_OPEN", "strike": new_strike, "price": new_premium})
        _append_state_history(state)
        _append_trades_csv("ROLL_PUT", "AAPL", new_strike, new_expiry, new_premium, pnl, pulse_id)
        return f"ROLLED to strike {new_strike} (PnL: {pnl})"
        
    # If we reach here, the decision is unknown to the executor
    raise ValueError(f"Unknown decision: {decision}")

async def main_executor():
    sim_log("═══ Hermes Executor Starting ═══")
    raw_brain_output = sys.stdin.read()
    decision_data = extract_decision(raw_brain_output)
    if not decision_data:
        sim_log("Invalid AI Output format. Pulse aborted.")
        return

    eye_data = load_json(EYE_CACHE_PATH)
    state = load_json(STATE_PATH)
    portfolio = load_json(PORTFOLIO_PATH)
    db = HermesDatabase()
    
    # 1. State Awareness (Assignment Detection)
    state = detect_assignment(portfolio, state)
    write_json(STATE_PATH, state) # Persist detection status
    
    # Pre-save pulse to DB
    pulse_id = db.save_pulse(eye_data, decision_data)
    
    try:
        # 2. Validation Interlock (The Smart Guard)
        decision_data, v_override = validate_decision(decision_data, eye_data, state)
        
        # 3. Yield Gate
        decision_data, y_override, y_reason = apply_yield_gate(decision_data)
        
        ai_override = v_override or y_override
        override_reason = "DTE Safety" if v_override else y_reason
        
        action_result = execute_decision(decision_data, db, pulse_id)
        sim_log(f"Action Result: {action_result}")
        
        summary = build_memory_summary(decision_data, state, portfolio, eye_data, action_result, ai_override, override_reason)
        
        # Audit Trail First
        try:
            with open(MEMORY_PATH, 'a') as f: f.write(f"--- PULSE #{pulse_id} ---\n{summary}\n\n")
        except: pass
        
        # Telegram Last (Hardened)
        send_telegram(summary)
        
    except Exception as e:
        error_msg = str(e)
        sim_log(f"🚨 CRITICAL ERROR: {error_msg}")
        
        payload = build_critical_payload(decision_data, eye_data, error_msg, state)
        send_telegram(payload, is_critical=True)
        
        # Abort the pulse with error code
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main_executor())
