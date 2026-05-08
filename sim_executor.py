import sys
import json
import os
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.parse

# ─────────────────────────────────────────────
# CONFIG — Paths
# ─────────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).parent
STATE_PATH     = PROJECT_ROOT / 'trade_state.json'
PORTFOLIO_PATH = PROJECT_ROOT / 'portfolio.json'
EYE_CACHE_PATH = PROJECT_ROOT / '.eye_cache.json'
MEMORY_PATH    = PROJECT_ROOT / '.hermes' / 'MEMORY.md'

def sim_log(msg: str):
    print(f"[SIM] {msg}", flush=True)

def extract_decision(raw_input: str) -> dict | None:
    """Institutional JSON Extractor (Robust)."""
    sim_log(f"Brain Raw Output Length: {len(raw_input)}")
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
                sim_log(f"Found valid decision: {data['decision']}")
                return data
        except: continue
    
    sim_log("ERROR: No valid JSON decision found in Brain output.")
    return None

def build_memory_summary(decision: dict, trade_state: dict, portfolio: dict) -> str:
    action = decision.get('decision', 'UNKNOWN')
    
    # RECOVERY: Try to get raw eye data if the Brain stripped it
    eye_data = {}
    if EYE_CACHE_PATH.exists():
        try:
            with open(EYE_CACHE_PATH, 'r') as f: eye_data = json.load(f)
        except: pass
    
    price = decision.get('price_seen') or eye_data.get('price_seen', 'N/A')
    vix = decision.get('vix_seen') or eye_data.get('vix_seen', 'N/A')
    iv_now = decision.get('iv_current') or eye_data.get('iv_current', 'N/A')
    earn = decision.get('earnings_days') or eye_data.get('earnings_days', 'N/A')
    phase = trade_state.get('current_phase', 'UNKNOWN')
    reason = decision.get('reason', '')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M IST')
    
    # P&L Calculation
    pnl_line = ""
    opt_pos = None
    for p in portfolio.get("positions", []):
        if p.get("type") == "Option": opt_pos = p; break
        
    if opt_pos:
        mid = None
        chain = eye_data.get("option_chain", [])
        held_strike = opt_pos.get("strike")
        target = next((x for x in chain if abs(x.get("strike") - held_strike) < 0.1), None)
        if target: mid = target.get("mid")
        
        if mid is not None:
            entry_cost = opt_pos.get("avg_cost", 0)
            pnl_dollars = round((entry_cost - mid) * 100, 2)
            max_profit = round(entry_cost * 100, 2)
            pnl_pct = round((pnl_dollars / max_profit) * 100, 1) if max_profit > 0 else 0.0
            pnl_line = f"P&L: ${pnl_dollars} / ${max_profit} ({pnl_pct}% Captured)\n"
        else:
            pnl_line = "P&L: [Stale Mid-Price - Waiting for Liquidity]\n"

    headlines = eye_data.get('recent_news', [])
    top_news = headlines[0][:65] + "..." if headlines else "No relevant news"
    
    summary = f"🤖 AAPL Pulse: {action}\n"
    summary += f"{timestamp} | Phase: {phase}\n"
    
    iv_display = f"{iv_now}" if isinstance(iv_now, str) else f"{iv_now}%"
    summary += f"AAPL: ${price} | VIX: {vix} | IV_Current: {iv_display}\n"
    if pnl_line: summary += pnl_line
    
    strike = opt_pos.get('strike') if opt_pos else 'none'
    delta = decision.get('delta_seen') or (target.get('delta') if 'target' in locals() and target else 'N/A')
    dte = decision.get('dte_seen') or eye_data.get('chosen_dte', 'N/A')
    
    summary += f"Strike: ${strike} | Delta: {delta} | DTE: {dte} | Earn: {earn}d\n"
    summary += f"News: {top_news}\n"
    summary += f"Reason: {reason}"
    return summary

def main():
    sim_log("=" * 60)
    raw_brain_output = sys.stdin.read()
    decision_data = extract_decision(raw_brain_output)
    if not decision_data: return
    
    # Load state
    try:
        with open(STATE_PATH, 'r') as f: state = json.load(f)
        with open(PORTFOLIO_PATH, 'r') as f: portfolio = json.load(f)
    except Exception as e:
        sim_log(f"ERROR: Could not load state/portfolio: {e}")
        return
    
    # Reporting
    summary = build_memory_summary(decision_data, state, portfolio)
    
    # Store
    try:
        with open(MEMORY_PATH, 'a') as f: f.write(summary + "\n\n")
        sim_log("Memory storage successful.")
    except Exception as e:
        sim_log(f"ERROR: Memory write failed: {e}")
    
    # Send
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id and "your_" not in token:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": summary}).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=10) as response:
                sim_log("Telegram alert sent.")
        except Exception as e:
            sim_log(f"ERROR: Telegram send failed: {e}")

    sim_log("Pulse Complete.")
    sim_log("=" * 60)

if __name__ == "__main__": main()
