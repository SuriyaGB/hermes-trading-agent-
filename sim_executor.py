"""
sim_executor.py — Institutional Simulation Executor for Hermes AAPL Wheel Agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mirrors the full decision-handling logic of executor.py but:
  - NO IBKR connection required
  - Reads Brain JSON from stdin (same as executor.py)
  - Fetches live fill prices via yfinance options chain
  - Writes trade results to portfolio.json (virtual account)
  - Updates trade_state.json with atomic synchronization
  - Appends to trades_log.csv with 15 audit fields

Every print line is prefixed with [SIM] so logs are always unambiguous.
"""

import sys
import json
import csv
import math
import os
from pathlib import Path
from datetime import datetime

import yfinance as yf
import subprocess
import os
import urllib.request
import urllib.parse

# ─────────────────────────────────────────────
# CONFIG — Paths
# ─────────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).parent
STATE_PATH     = PROJECT_ROOT / 'trade_state.json'
PORTFOLIO_PATH = PROJECT_ROOT / 'portfolio.json'
LOG_PATH       = PROJECT_ROOT / 'trades_log.csv'


def sim_log(msg: str):
    print(f"[SIM] {msg}", flush=True)


def extract_decision(raw_input: str) -> dict | None:
    """Professional Stack-Based JSON Extractor."""
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
                candidate = raw_input[start:i+1].strip()
                candidates.append(candidate)
                start = -1
    for candidate in reversed(candidates):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and 'decision' in data:
                return data
        except: continue
    return None


# ─────────────────────────────────────────────
# STATE & PORTFOLIO LOADERS
# ─────────────────────────────────────────────
def load_state() -> dict:
    default = {"current_phase": "CASH_ONLY", "adjusted_cost_basis": None}
    try:
        if STATE_PATH.exists():
            with open(STATE_PATH, 'r') as f:
                return json.load(f)
        return default
    except: return default


def load_portfolio() -> dict:
    default = {"total_cash": 250000.00, "positions": [], "realized_pnl": 0.0}
    try:
        if PORTFOLIO_PATH.exists():
            with open(PORTFOLIO_PATH, 'r') as f:
                return json.load(f)
        return default
    except: return default


def get_option_position(portfolio: dict) -> dict | None:
    for p in portfolio.get("positions", []):
        if p.get("type") == "Option" and p.get("symbol") == "AAPL":
            return p
    return None


def get_stock_position(portfolio: dict) -> dict | None:
    for p in portfolio.get("positions", []):
        if p.get("type") == "Stock" and p.get("symbol") == "AAPL":
            return p
    return None


# ─────────────────────────────────────────────
# FIX 3D: AUDIT LOGGING (15 Fields)
# ─────────────────────────────────────────────
def append_to_audit_log(decision_data: dict, action: str, result: str, reason: str = ""):
    """
    Append one row to trades_log.csv with full institutional audit fields.
    """
    header = [
        "timestamp", "action", "strike", "expiry", "dte", "delta", "premium",
        "premium_per_contract", "min_premium_required", "floor_used",
        "earnings_days", "iv30_rank", "vix_seen", "reason", "result"
    ]
    
    strike  = decision_data.get("strike_held")
    premium = decision_data.get("mid") or decision_data.get("avg_cost", 0)
    
    # Calculate derived audit values
    min_premium_req = round(strike * 0.01, 2) if strike else 0.0
    floor_A = round(decision_data.get("fifty_two_week_low", 0) * 1.15, 2)
    floor_B = round(decision_data.get("ma_200", 0) * 0.95, 2)
    floor_used = max(floor_A, floor_B)

    row = [
        datetime.now().isoformat(),
        action,
        strike,
        decision_data.get("chosen_expiry"),
        decision_data.get("chosen_dte"),
        decision_data.get("delta_seen"),
        premium,
        round(premium * 100, 2) if premium else 0.0,
        min_premium_req,
        floor_used,
        decision_data.get("earnings_days"),
        decision_data.get("iv30_rank"),
        decision_data.get("vix_seen"),
        reason,
        result
    ]

    file_exists = LOG_PATH.exists()
    with open(LOG_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow(row)
    sim_log(f"Audit log updated: {result}")


# ─────────────────────────────────────────────
# FIX 4B: MEMORY STORAGE (Closing the Loop)
# ─────────────────────────────────────────────
def build_memory_summary(decision: dict, trade_state: dict, portfolio: dict, action: str = None) -> str:
    """
    Translates the technical decision into a plain English narrative for SQLite.
    """
    if action is None:
        action = decision.get('action') or decision.get('decision', 'UNKNOWN')
    
    price      = decision.get('price_seen', 'N/A')
    vix        = decision.get('vix_seen', 'N/A')
    iv_rank    = decision.get('iv30_rank', 'N/A')
    earn       = decision.get('earnings_days', 'N/A')
    strike     = decision.get('strike_held') or decision.get('strike', None)
    delta      = decision.get('delta_seen', None)
    dte        = decision.get('dte_seen') or decision.get('chosen_dte', None)
    premium    = decision.get('mid') or decision.get('premium', None)
    phase      = trade_state.get('current_phase', 'UNKNOWN')
    mem_obs    = decision.get('memory_observation', 'No relevant memory found.')
    reason     = decision.get('reason', '')
    timestamp  = datetime.now().strftime('%Y-%m-%d %H:%M IST')
    
    # Build summary based on action type
    if action == 'SELL_NEW_PUT':
        summary = (
            f"{timestamp} | ACTION: Opened CSP | "
            f"Strike: ${strike} | Delta: {delta} | DTE: {dte} | "
            f"Premium: ${premium} | AAPL: ${price} | "
            f"VIX: {vix} | IV_Rank: {iv_rank}% | "
            f"Earnings: {earn}d away | "
            f"Memory: {mem_obs}"
        )
    elif action == 'WAIT_FOR_ENTRY':
        summary = (
            f"{timestamp} | ACTION: Waited for entry | "
            f"Phase: CASH_ONLY | AAPL: ${price} | "
            f"VIX: {vix} | IV_Rank: {iv_rank}% | "
            f"Earnings: {earn}d away | Reason: {reason} | "
            f"Memory: {mem_obs}"
        )
    elif action in ['HOLD_PUT_POSITION', 'HOLD_CALL_POSITION', 'HOLD']:
        existing_strike = trade_state.get('current_option_strike', 'none')
        summary = (
            f"{timestamp} | ACTION: Held position | "
            f"Phase: {phase} | Strike held: ${existing_strike} | "
            f"AAPL: ${price} | VIX: {vix} | IV_Rank: {iv_rank}% | "
            f"Earnings: {earn}d away | Reason: {reason} | "
            f"Memory: {mem_obs}"
        )
    elif action == 'CLOSE_PUT_POSITION':
        summary = (
            f"{timestamp} | ACTION: Closed CSP | "
            f"Strike: ${strike} | AAPL: ${price} | "
            f"VIX: {vix} | Reason: {reason} | "
            f"Memory: {mem_obs}"
        )
    elif action == 'SELL_NEW_CALL':
        summary = (
            f"{timestamp} | ACTION: Opened CC | "
            f"Strike: ${strike} | Delta: {delta} | DTE: {dte} | "
            f"Premium: ${premium} | AAPL: ${price} | "
            f"VIX: {vix} | Memory: {mem_obs}"
        )
    elif action == 'ROLL_PUT':
        summary = (
            f"{timestamp} | ACTION: Rolled Put | "
            f"New strike: ${strike} | AAPL: ${price} | "
            f"VIX: {vix} | Reason: {reason} | "
            f"Memory: {mem_obs}"
        )
    else:
        summary = (
            f"{timestamp} | ACTION: {action} | "
            f"Phase: {phase} | AAPL: ${price} | "
            f"VIX: {vix} | IV_Rank: {iv_rank}% | "
            f"Reason: {reason} | Memory: {mem_obs}"
        )
    
    return summary


def store_memory(summary: str) -> None:
    """
    Directly appends the summary to .hermes/MEMORY.md.
    Unbreakable, no CLI dependency.
    """
    memory_file = PROJECT_ROOT / '.hermes' / 'MEMORY.md'
    try:
        with open(memory_file, 'a') as f:
            f.write(summary + "\n\n")
        sim_log("Memory storage successful (Direct Write to MEMORY.md).")
    except Exception as e:
        sim_log(f"Memory storage skipped (Non-critical): {e}")


def send_telegram_alert(summary: str) -> None:
    """
    Sends the pulse summary to the user's Telegram bot.
    Fail-safe: errors are logged but never block execution.
    """
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id or "your_" in token:
        sim_log("Telegram alert skipped: Credentials not set in .env")
        return

    # Clean the summary for Telegram (escaped characters if needed, but plain text is usually fine)
    # Prefix with a bot icon for visibility
    text = f"🤖 AAPL Pulse Alert\n\n{summary}"
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                sim_log("Telegram alert sent successfully.")
            else:
                sim_log(f"Telegram alert failed with status: {response.status}")
    except Exception as e:
        sim_log(f"Telegram alert skipped (Network/API Error): {e}")


# ─────────────────────────────────────────────
# FIX 3C: ATOMIC COMMIT
# ─────────────────────────────────────────────
def commit_trade(portfolio: dict, state: dict):
    """
    Atomic write: Portfolio first, then State.
    """
    # 1. Write Portfolio
    with open(PORTFOLIO_PATH, 'w') as f:
        json.dump(portfolio, f, indent=2)
    
    # Verify write
    with open(PORTFOLIO_PATH, 'r') as f:
        verify = json.load(f)
        if len(verify.get("positions", [])) != len(portfolio.get("positions", [])):
            raise IOError("Portfolio write verification failed!")

    # 2. Write State
    state['last_pulse_timestamp'] = datetime.now().isoformat()
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)
    
    # 3. History log
    history_path = PROJECT_ROOT / 'trade_state_history.jsonl'
    with open(history_path, 'a') as f:
        f.write(json.dumps(state) + '\n')
    
    sim_log("Atomic Sync Complete: Portfolio and State persistent.")


# ─────────────────────────────────────────────
# FIX 3A & 3B: VALIDATION GATES (Audit Hardened)
# ─────────────────────────────────────────────
def validate_csp_trade(strike, delta, dte, premium, decision_data):
    """
    5-Point Safety Gate for Cash Secured Puts.
    Re-validates the Brain's decision against hard math rules.
    """
    # 1. NULL GUARDS (Audit Fix)
    if strike is None: return False, "Strike is missing (NoneType)"
    if delta is None:  return False, "Delta is missing (NoneType)"
    if dte is None:    return False, "DTE is missing (NoneType)"
    if premium is None: return False, "Premium is missing (NoneType)"

    # 2. DELTA & DTE GATES
    if delta > 0.35: return False, f"delta {delta} > 0.35"
    if dte < 25:     return False, f"dte {dte} < 25"
    if dte > 55:     return False, f"dte {dte} > 55"

    # 3. STRIKE FLOOR GATE
    floor_a = decision_data.get('ma_200', 0)
    floor_b = decision_data.get('fifty_two_week_low', 0)
    min_strike = max(floor_a or 0, floor_b or 0)
    
    if strike < min_strike: return False, f"strike {strike} < floor {min_strike}"
    
    # 4. EARNINGS GATE
    earnings_days = decision_data.get("earnings_days")
    if earnings_days is not None and dte >= earnings_days:
        return False, f"expiry DTE {dte} >= earnings {earnings_days}"
        
    # 5. PREMIUM YIELD GATE (1.0% rule)
    min_prem = round(strike * 0.01, 2)
    if premium < min_prem:
        return False, f"premium {premium} < min {min_prem}"
        
    return True, ""


def validate_cc_trade(strike, dte, premium, decision_data, portfolio):
    """
    3-Point Safety Gate for Covered Calls.
    """
    # 1. NULL GUARDS (Audit Fix)
    if strike is None: return False, "Strike is missing (NoneType)"
    if dte is None:    return False, "DTE is missing (NoneType)"

    # 2. DTE GATES
    if dte < 25: return False, f"dte {dte} < 25"
    if dte > 55: return False, f"dte {dte} > 55"

    # 3. COST BASIS PROTECTION
    cost_basis = portfolio.get('aapl_cost_basis', 0)
    if strike <= cost_basis: return False, f"strike {strike} <= cost basis {cost_basis}"
    
    return True, ""


# ─────────────────────────────────────────────
# MARKET DATA HELPERS
# ─────────────────────────────────────────────
def get_aapl_price() -> float:
    try: return round(yf.Ticker('AAPL').fast_info.last_price, 2)
    except: return 0.0


# ─────────────────────────────────────────────
# DECISION HANDLERS
# ─────────────────────────────────────────────
def handle_sell_new_put(decision_data: dict, state: dict, portfolio: dict):
    sim_log("Decision: SELL_NEW_PUT")
    # Priority: strike_to_trade (new field) -> strike_held (fallback)
    strike = decision_data.get("strike_to_trade") or decision_data.get("strike_held")
    delta = decision_data.get("delta_seen")
    dte = decision_data.get("dte_seen") or decision_data.get("chosen_dte")
    premium = decision_data.get("premium_to_collect") or decision_data.get("mid")
    
    passed, reason = validate_csp_trade(strike, delta, dte, premium, decision_data)
    
    if not passed:
        sim_log(f"ABORTED: {reason}")
        append_to_audit_log(decision_data, "SELL_NEW_PUT", "ABORTED", reason)
        return

    # Execution (Atomic State Update)
    expiry = decision_data.get("chosen_expiry")
    collateral = round(float(strike) * 100, 2)
    premium_total = round(float(premium) * 100, 2)
    
    if portfolio["total_cash"] < collateral:
        sim_log("ABORTED: Insufficient cash for collateral.")
        return

    portfolio["total_cash"] = round(portfolio["total_cash"] + premium_total - collateral, 2)
    portfolio["reserved_collateral"] = portfolio.get("reserved_collateral", 0) + collateral
    portfolio["positions"].append({
        "symbol": "AAPL", "type": "Option", "right": "P", "strike": strike,
        "expiry": expiry, "quantity": -1, "avg_cost": premium, "multiplier": 100
    })

    state["current_phase"] = "CSP_ACTIVE"
    state["current_option_strike"] = strike
    state["current_option_expiry"] = expiry
    state["adjusted_cost_basis"] = round(strike - premium, 2)

    commit_trade(portfolio, state)
    append_to_audit_log(decision_data, "SELL_NEW_PUT", "OPENED")


def handle_sell_new_call(decision_data: dict, state: dict, portfolio: dict):
    sim_log("Decision: SELL_NEW_CALL")
    stock_pos = get_stock_position(portfolio)
    if not stock_pos:
        sim_log("ABORTED: No shares held.")
        return

    # Priority: strike_to_trade (new field) -> strike_held (fallback)
    strike = decision_data.get("strike_to_trade") or decision_data.get("strike_held")
    cost_basis = state.get("adjusted_cost_basis")
    days_to_exdiv = decision_data.get("days_to_exdiv")

    passed, reason = validate_cc_trade(strike, cost_basis, days_to_exdiv)
    if not passed:
        sim_log(f"ABORTED: {reason}")
        append_to_audit_log(decision_data, "SELL_NEW_CALL", "ABORTED", reason)
        return

    premium = decision_data.get("mid") or 0.0
    expiry = decision_data.get("chosen_expiry")
    
    portfolio["total_cash"] = round(portfolio["total_cash"] + (premium * 100), 2)
    portfolio["positions"].append({
        "symbol": "AAPL", "type": "Option", "right": "C", "strike": strike,
        "expiry": expiry, "quantity": -1, "avg_cost": premium, "multiplier": 100
    })

    state["current_phase"] = "CC_ACTIVE"
    state["current_option_strike"] = strike
    state["current_option_expiry"] = expiry

    commit_trade(portfolio, state)
    append_to_audit_log(decision_data, "SELL_NEW_CALL", "OPENED")


def handle_close_for_profit(decision_data: dict, state: dict, portfolio: dict, action="CLOSE_FOR_PROFIT"):
    sim_log(f"Decision: {action}")
    pos = get_option_position(portfolio)
    if not pos: return

    mid = decision_data.get("mid") or pos["avg_cost"]
    pnl = round((pos["avg_cost"] - mid) * 100, 2)
    
    # Release collateral if it was a Put
    if pos["right"] == "P":
        collateral = round(pos["strike"] * 100, 2)
        portfolio["total_cash"] = round(portfolio["total_cash"] + collateral - (mid * 100), 2)
        portfolio["reserved_collateral"] = max(0, portfolio.get("reserved_collateral", 0) - collateral)
    else:
        portfolio["total_cash"] = round(portfolio["total_cash"] - (mid * 100), 2)

    portfolio["realized_pnl"] = round(portfolio.get("realized_pnl", 0.0) + pnl, 2)
    portfolio["positions"] = [p for p in portfolio["positions"] if p != pos]

    state["current_phase"] = "CASH_ONLY" if pos["right"] == "P" else "SHARES_ASSIGNED"
    state["current_option_strike"] = None
    state["current_option_expiry"] = None

    commit_trade(portfolio, state)
    append_to_audit_log(decision_data, action, "CLOSED")


def handle_hold(decision: str, state: dict, decision_data: dict):
    phase = state.get("current_phase", "CASH_ONLY")
    
    # Language Correction: Phase-aware action naming
    actual_action = decision
    if phase == "CASH_ONLY":
        actual_action = "WAIT_FOR_ENTRY"
    elif phase == "CSP_ACTIVE":
        actual_action = "HOLD_PUT_POSITION"
    elif phase == "CC_ACTIVE":
        actual_action = "HOLD_CALL_POSITION"
        
    sim_log(f"Decision: {actual_action}")
    state["last_decision"] = actual_action
    # Update timestamp even on hold
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)
    append_to_audit_log(decision_data, actual_action, "HOLD")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    sim_log("=" * 60)
    decision_data = extract_decision(sys.stdin.read())
    if not decision_data: return

    decision = decision_data.get("decision", "")
    state = load_state()
    portfolio = load_portfolio()

    if decision == "SELL_NEW_PUT": handle_sell_new_put(decision_data, state, portfolio)
    elif decision == "SELL_NEW_CALL": handle_sell_new_call(decision_data, state, portfolio)
    elif decision == "CLOSE_FOR_PROFIT": handle_close_for_profit(decision_data, state, portfolio)
    elif decision == "CLOSE_FOR_LOSS": handle_close_for_profit(decision_data, state, portfolio, "CLOSE_FOR_LOSS")
    elif decision.startswith("HOLD") or decision == "WAIT_FOR_ENTRY":
        handle_hold(decision, state, decision_data)
    
    # --- Final Step: Record Learning (Fix 4B) ---
    # Use the corrected 'actual_action' if it was a hold, otherwise use the decision
    actual_action = state.get("last_decision", decision)
    summary = build_memory_summary(decision_data, state, portfolio, actual_action)
    store_memory(summary)
    
    # --- Telegram Notification (Option 1) ---
    send_telegram_alert(summary)
    
    sim_log("Pulse Complete.")
    sim_log("=" * 60)

if __name__ == "__main__":
    main()
