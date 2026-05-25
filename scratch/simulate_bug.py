import json
from pathlib import Path

# Paths matching the active workspace
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
STATE_PATH = DATA_DIR / 'trade_state.json'
PORTFOLIO_PATH = DATA_DIR / 'portfolio.json'
EYE_CACHE_PATH = PROJECT_ROOT / '.eye_cache.json'

def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}

def simulate_validation(decision_data):
    eye_data = load_json(EYE_CACHE_PATH)
    state = load_json(STATE_PATH)
    portfolio = load_json(PORTFOLIO_PATH)
    
    decision = decision_data.get('decision')
    print("=== Input State & Decision ===")
    print(f"Decision: {decision}")
    print(f"State Phase: {state.get('current_phase')}")
    print(f"Portfolio Positions: {portfolio.get('positions')}")
    
    print("\n=== Evaluating Validation Gate ===")
    if decision == "ROLL_PUT":
        # Extract fields exactly as core/executor.py does
        delta_val = eye_data.get('delta_current')
        dte_val = eye_data.get('dte_current')
        
        print(f"Raw eye_data['delta_current']: {delta_val}")
        print(f"Raw eye_data['dte_current']: {dte_val}")
        
        delta = abs(float(eye_data.get('delta_current', 0)))
        dte = int(eye_data.get('dte_current', 99))
        
        print(f"Resolved Delta (with fallback 0): {delta}")
        print(f"Resolved DTE (with fallback 99): {dte}")
        
        # Policy Check
        condition_met = delta < 0.45 and dte >= 21
        print(f"Condition (Delta {delta} < 0.45 AND DTE {dte} >= 21): {condition_met}")
        
        if condition_met:
            print(f"\n🚨 REJECTED: Policy Block: ROLL rejected (Delta {delta} < 0.45 AND DTE {dte} >= 21).")
        else:
            print("\n✅ VALIDATED: Decision is allowed.")

if __name__ == "__main__":
    decision_data = {"decision": "ROLL_PUT"}
    simulate_validation(decision_data)
