import subprocess
import json
from pathlib import Path

def run_test(decision, eye_data, state=None):
    print(f"\n--- Testing decision: {decision['decision']} ---")
    with open('.eye_cache.json', 'w') as f: json.dump(eye_data, f)
    if state:
        with open('data/trade_state.json', 'w') as f: json.dump(state, f)

    process = subprocess.Popen(
        ['python3', '-m', 'core.executor'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    stdout, stderr = process.communicate(input=json.dumps(decision))
    print(f"Exit Code: {process.returncode}")
    return process.returncode, stdout

if __name__ == "__main__":
    # Test 3: ROLL_PUT with valid Delta (>= 0.45) in ASSIGNED state
    print("Test 3: Valid ROLL_PUT (Delta 0.50, DTE 30)")
    with open('data/portfolio.json', 'w') as f:
        json.dump({"positions": [{"type": "Option", "symbol": "AAPL", "strike": 285.0, "avg_cost": 4.50, "option_type": "PUT"}], "total_cash": 250000.0}, f)
    
    roll_decision = {
        "decision": "ROLL_PUT",
        "close_details": {"premium_to_pay": 5.20},
        "open_details": {"strike_to_trade": 275.0, "premium_to_collect": 6.50, "dte_seen": 45},
        "reason": "Test rolling with high delta"
    }
    eye = {"delta_current": 0.50, "dte_current": 30, "price_seen": 280.0}
    state = {"current_phase": "CSP_ACTIVE", "current_option_strike": 285.0}
    ret, out = run_test(roll_decision, eye, state)
    if ret == 0 and "ROLLED to strike 275.0" in out:
        print("[RESULT] Test 3 PASSED.")
    else:
        print(f"[RESULT] Test 3 FAILED. STDOUT: {out}")

    # Test 4: SELL_NEW_CALL with correct ASSIGNED state
    print("\nTest 4: Valid SELL_NEW_CALL (Phase: ASSIGNED)")
    with open('data/portfolio.json', 'w') as f:
        json.dump({"positions": [{"type": "Stock", "symbol": "AAPL", "quantity": 100}], "total_cash": 250000.0}, f)
    
    call_decision = {
        "decision": "SELL_NEW_CALL",
        "strike_to_trade": 310.0,
        "premium_to_collect": 4.50,
        "dte_seen": 30,
        "reason": "Sell CC on assigned shares"
    }
    state = {"current_phase": "ASSIGNED"}
    ret, out = run_test(call_decision, eye, state)
    if ret == 0 and "SOLD CALL strike 310.0" in out:
        print("[RESULT] Test 4 PASSED.")
        with open('data/trade_state.json') as f:
            fs = json.load(f)
            if fs.get('current_phase') == 'CC_ACTIVE':
                print("[RESULT] State = CC_ACTIVE PASSED.")
    else:
        print(f"[RESULT] Test 4 FAILED. STDOUT: {out}")
