import subprocess
import json
import os

def run_test(decision):
    print(f"Testing decision: {decision}")
    process = subprocess.Popen(
        ['python3', '-m', 'core.executor'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate(input=json.dumps(decision))
    print(f"Exit Code: {process.returncode}")
    print(f"STDOUT: {stdout}")
    if stderr:
        print(f"STDERR: {stderr}")
    return process.returncode, stdout

if __name__ == "__main__":
    # Test 1: Unknown decision (ROLL_PUT is not handled yet)
    print("--- Running Test 1: Unknown Decision (Post-Fix) ---")
    ret, out = run_test({"decision": "ROLL_PUT", "reason": "Testing fix 1"})
    
    if ret == 1 and "CRITICAL ERROR" in out:
        print("\n[RESULT] Test 1 PASSED: System now ABORTS and ALERTS on unknown decisions.")
    else:
        print("\n[RESULT] Test 1 FAILED: System did not abort or alert correctly.")

    # Test 2: Known decision (HOLD_PUT_POSITION)
    print("\n--- Running Test 2: Known Decision (HOLD) ---")
    ret, out = run_test({"decision": "HOLD_PUT_POSITION", "reason": "Testing stability"})
    if ret == 0 and "Action Result: No Action" in out:
        print("\n[RESULT] Test 2 PASSED: Known decisions still work correctly.")
    else:
        print("\n[RESULT] Test 2 FAILED: HOLD logic broken.")
