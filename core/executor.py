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

def send_telegram(text: str):
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id or "your_" in token:
        sim_log("Telegram not configured — skipping.")
        return
    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        req  = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10):
            sim_log("Telegram alert sent.")
    except Exception as e:
        # BUG #1 FIX: Fail-safe
        sim_log(f"⚠️ TELEGRAM FAILED (Side effect ignored): {e}")

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

def execute_decision(decision_data, db, pulse_id):
    decision = decision_data.get('decision', 'UNKNOWN')
    
    if decision in SELL_DECISIONS:
        strike = decision_data.get('strike_to_trade')
        premium = decision_data.get('premium_to_collect')
        expiry = decision_data.get('dte_seen', 'N/A')
        
        portfolio = load_json(PORTFOLIO_PATH)
        state = load_json(STATE_PATH)
        
        # Update Portfolio
        portfolio["positions"].append({"type": "Option", "symbol": "AAPL", "strike": strike, "avg_cost": premium})
        portfolio["total_cash"] = round(portfolio.get("total_cash", 250000) + (premium * 100), 2)
        
        # Update State
        state.update({"current_phase": "CSP_ACTIVE", "current_option_strike": strike})
        
        write_json(PORTFOLIO_PATH, portfolio)
        write_json(STATE_PATH, state)
        db.save_trade(pulse_id, {"symbol": "AAPL", "action": "SELL_PUT", "strike": strike, "price": premium, "pnl": 0.0})
        _append_state_history(state)
        _append_trades_csv("SELL_PUT", "AAPL", strike, expiry, premium, 0.0, pulse_id)
        return f"SOLD strike {strike}"

    elif decision in CLOSE_DECISIONS:
        portfolio = load_json(PORTFOLIO_PATH)
        state = load_json(STATE_PATH)
        
        opt_pos = next((p for p in portfolio["positions"] if p.get("type") == "Option"), None)
        pnl = 0.0
        if opt_pos:
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
        
    return "No Action"

def build_memory_summary(decision, state, portfolio, eye_data, action_result, ai_override, override_reason):
    action = decision.get('decision')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    summary = f"🤖 AAPL Pulse: {action}\nTime: {timestamp}\nAction: {action_result}\n"
    if ai_override: summary += f"⚠️ OVERRIDE: {override_reason}\n"
    summary += f"Reason: {decision.get('reason', 'N/A')}"
    return summary

async def main_executor():
    sim_log("═══ Hermes Executor Starting ═══")
    raw_brain_output = sys.stdin.read()
    decision_data = extract_decision(raw_brain_output)
    if not decision_data: return

    eye_data = load_json(EYE_CACHE_PATH)
    db = HermesDatabase()
    pulse_id = db.save_pulse(eye_data, decision_data)
    
    decision_data, ai_override, override_reason = apply_yield_gate(decision_data)
    
    state = load_json(STATE_PATH)
    portfolio = load_json(PORTFOLIO_PATH)
    
    action_result = execute_decision(decision_data, db, pulse_id)
    
    summary = build_memory_summary(decision_data, load_json(STATE_PATH), load_json(PORTFOLIO_PATH), eye_data, action_result, ai_override, override_reason)
    
    # Audit Trail First
    try:
        with open(MEMORY_PATH, 'a') as f: f.write(f"--- PULSE #{pulse_id} ---\n{summary}\n\n")
    except: pass
    
    # Telegram Last (Hardened)
    try: send_telegram(summary)
    except Exception as e: sim_log(f"Telegram failed: {e}")

if __name__ == "__main__":
    asyncio.run(main_executor())
