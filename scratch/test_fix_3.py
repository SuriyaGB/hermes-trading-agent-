import subprocess
import json
import os
from pathlib import Path

def run_test(decision, eye_data, state=None, portfolio=None):
    print(f"\n--- Testing decision: {decision['decision']} ---")
    
    # Setup Cache
    with open('.eye_cache.json', 'w') as f: json.dump(eye_data, f)
    
    # Setup State
    if state:
        with open('data/trade_state.json', 'w') as f: json.dump(state, f)
    else:
        with open('data/trade_state.json', 'w') as f: json.dump({"current_phase": "CSP_ACTIVE"}, f)

    # Setup Portfolio
    if portfolio:
        with open('data/portfolio.json', 'w') as f: json.dump(portfolio, f)
    else:
        # Default empty portfolio
        with open('data/portfolio.json', 'w') as f: json.dump({"positions": []}, f)

    process = subprocess.Popen(
        ['python3', '-m', 'core.executor'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate(input=json.dumps(decision))
    print(f"Exit Code: {process.returncode}")
    if stderr:
        print(f"STDERR: {stderr}")
    return process.returncode, stdout

if __name__ == "__main__":
    # Test 7a: DTE Emergency Close (Success)
    print("Test 7a: DTE Emergency Close (Success)")
    hold_decision = {"decision": "HOLD_PUT_POSITION", "reason": "Testing override success"}
    eye = {"dte_current": 0.5, "price_seen": 280.0, "delta_current": 0.1}
    portfolio = {"positions": [{"type": "Option", "symbol": "AAPL", "strike": 285.0, "avg_cost": 4.50}]}
    
    ret, out = run_test(hold_decision, eye, portfolio=portfolio)
    if ret == 0 and "DTE < 1: Emergency Close Attempt Triggered" in out and "CLOSED for" in out:
        print("[RESULT] Test 7a PASSED.")
    else:
        print(f"[RESULT] Test 7a FAILED. STDOUT: {out}")

    # Test 7b: DTE Emergency Close (Failure - No Position)
    print("\nTest 7b: DTE Emergency Close (Failure - No Position)")
    portfolio_empty = {"positions": []}
    ret, out = run_test(hold_decision, eye, portfolio=portfolio_empty)
    if ret == 1 and "CRITICAL ERROR: Emergency Close FAILED" in out:
        print("[RESULT] Test 7b PASSED (Correctly Aborted and Alerted).")
    else:
        print(f"[RESULT] Test 7b FAILED. STDOUT: {out}")

    # Test 8: Defensive Coding (Missing 'positions' key)
    print("\nTest 8: Defensive Coding (Missing 'positions' key)")
    portfolio_broken = {"total_cash": 250000.0} # Missing 'positions'
    ret, out = run_test(hold_decision, eye, portfolio=portfolio_broken)
    # It should still abort with the same error but not CRASH with a KeyError
    if ret == 1 and "CRITICAL ERROR: Emergency Close FAILED" in out:
        print("[RESULT] Test 8 PASSED (Defensively Handled).")
    else:
        print(f"[RESULT] Test 8 FAILED. STDOUT: {out}")
