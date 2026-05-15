import subprocess
import json
import os
from pathlib import Path

def run_test(decision, eye_data, state, portfolio):
    print(f"\n--- Testing decision: {decision['decision']} ---")
    
    # Setup files
    with open('.eye_cache.json', 'w') as f: json.dump(eye_data, f)
    with open('data/trade_state.json', 'w') as f: json.dump(state, f)
    with open('data/portfolio.json', 'w') as f: json.dump(portfolio, f)

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
    
    # Read back state
    with open('data/trade_state.json', 'r') as f:
        final_state = json.load(f)
    
    return process.returncode, stdout, final_state

if __name__ == "__main__":
    eye = {"dte_current": 30, "price_seen": 280.0, "delta_current": 0.2}
    decision = {"decision": "HOLD_PUT_POSITION", "reason": "Just checking assignment"}
    
    # Test 9: 1st Pulse Detection
    print("Test 9: 1st Pulse Detection (Phase: CSP_ACTIVE, Shares: 100)")
    state = {"current_phase": "CSP_ACTIVE", "assignment_confirmed_once": False}
    portfolio = {"positions": [{"type": "Stock", "symbol": "AAPL", "quantity": 100}]}
    
    ret, out, fs = run_test(decision, eye, state, portfolio)
    if fs.get('assignment_confirmed_once') == True and fs.get('current_phase') == "CSP_ACTIVE":
        print("[RESULT] Test 9 PASSED (Flag set, phase held).")
    else:
        print(f"[RESULT] Test 9 FAILED. State: {fs}")

    # Test 10: 2nd Pulse Confirmation
    print("\nTest 10: 2nd Pulse Confirmation")
    state = fs # Carry over from T9
    ret, out, fs = run_test(decision, eye, state, portfolio)
    if fs.get('current_phase') == "ASSIGNED":
        print("[RESULT] Test 10 PASSED (Transitioned to ASSIGNED).")
    else:
        print(f"[RESULT] Test 10 FAILED. State: {fs}")

    # Test 11: Flicker Reset
    print("\nTest 11: Flicker Reset")
    state = {"current_phase": "CSP_ACTIVE", "assignment_confirmed_once": True}
    portfolio_empty = {"positions": []}
    ret, out, fs = run_test(decision, eye, state, portfolio_empty)
    if fs.get('assignment_confirmed_once') == False:
        print("[RESULT] Test 11 PASSED (Flag reset).")
    else:
        print(f"[RESULT] Test 11 FAILED. State: {fs}")
