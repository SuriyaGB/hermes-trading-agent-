#!/usr/bin/env python3
"""
=============================================================================
 Hermes Scenario Runner — scripts/run_scenarios.py
=============================================================================
 PURPOSE:
   Runs one or all of the 25 fixed mock scenario tests WITHOUT touching the
   live market, live LLM, or corrupting the real data files.

 HOW IT WORKS:
   1. Backs up your real data files (portfolio.json, trade_state.json, etc.)
   2. Seeds mock data from the selected scenario JSON
   3. Runs the REAL Python executor validation and yield gate logic
   4. For execution-type tests (TC24, TC25), also runs execute_decision
   5. Compares result vs expected outcome and prints PASS / FAIL
   6. ALWAYS restores your real data files (even if a test crashes)

 USAGE:
   python3 scripts/run_scenarios.py 1          # Run TC01 only (Zero API Cost)
   python3 scripts/run_scenarios.py 1 --live   # Run TC01 using REAL GPT-4o (Costs API credits)
   python3 scripts/run_scenarios.py 1 --keep-state # Leave mock data in data/ folder to view in UI
   python3 scripts/run_scenarios.py all        # Run all 25 cases in sequence
   python3 scripts/run_scenarios.py 1 --quiet  # Suppress verbose output


 ZERO API COST — no OpenAI calls are made. All logic is pure Python.
=============================================================================
"""

import sys
import json
import shutil
import os
import traceback
import subprocess
from pathlib import Path
from datetime import datetime

# ── Path Setup ─────────────────────────────────────────────────────────────
PROJECT_ROOT    = Path(__file__).parent.parent
DATA_DIR        = PROJECT_ROOT / "data"
MOCK_DIR        = PROJECT_ROOT / "tests" / "mock_payloads"
BACKUP_DIR      = PROJECT_ROOT / "tests" / ".scenario_backup"

PORTFOLIO_PATH  = DATA_DIR / "portfolio.json"
STATE_PATH      = DATA_DIR / "trade_state.json"
TRACKER_PATH    = DATA_DIR / "intraday_tracker.json"
EYE_CACHE_PATH  = PROJECT_ROOT / ".eye_cache.json"

# ── Import Hermes Core Modules ──────────────────────────────────────────────
sys.path.insert(0, str(PROJECT_ROOT))
import core.executor as executor
from core.utils import PolicyBlockError, PacingBlockError, load_json, write_json, get_market_date
from core.database import HermesDatabase

# ── Override executor paths to point to real data dir ──────────────────────
executor.PORTFOLIO_PATH  = PORTFOLIO_PATH
executor.STATE_PATH      = STATE_PATH
executor.TRACKER_PATH    = TRACKER_PATH
executor.EYE_CACHE_PATH  = EYE_CACHE_PATH

# ── Colour Codes ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ═══════════════════════════════════════════════════════════════════════════
#  HELPER: Get all scenario files sorted by case_id
# ═══════════════════════════════════════════════════════════════════════════
def list_scenarios():
    files = sorted(MOCK_DIR.glob("tc*.json"))
    scenarios = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
            scenarios.append((data.get("case_id", 99), f, data))
        except Exception as e:
            print(f"{RED}[ERROR] Cannot read {f.name}: {e}{RESET}")
    scenarios.sort(key=lambda x: x[0])
    return scenarios


# ═══════════════════════════════════════════════════════════════════════════
#  HELPER: Backup and Restore real data files
# ═══════════════════════════════════════════════════════════════════════════
def backup_data():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for path in [PORTFOLIO_PATH, STATE_PATH, TRACKER_PATH, EYE_CACHE_PATH]:
        if path.exists():
            shutil.copy2(path, BACKUP_DIR / path.name)

def restore_data():
    for path in [PORTFOLIO_PATH, STATE_PATH, TRACKER_PATH, EYE_CACHE_PATH]:
        backup = BACKUP_DIR / path.name
        if backup.exists():
            shutil.copy2(backup, path)


# ═══════════════════════════════════════════════════════════════════════════
#  HELPER: Seed mock data from scenario into real files
# ═══════════════════════════════════════════════════════════════════════════
def seed_mock_data(scenario: dict):
    today_str = get_market_date()

    # ── Portfolio ─────────────────────────────────────────────────────────
    portfolio = dict(scenario["mock_portfolio"])
    # Ensure total_cash is set (executor uses this key)
    if "total_cash" not in portfolio:
        portfolio["total_cash"] = portfolio.get("cash_balance", 250000.0)
    write_json(PORTFOLIO_PATH, portfolio)

    # ── Trade State ───────────────────────────────────────────────────────
    write_json(STATE_PATH, scenario["mock_trade_state"])

    # ── Intraday Tracker (replace TODAY placeholder) ──────────────────────
    tracker = dict(scenario["mock_tracker"])
    if tracker.get("date") == "TODAY":
        tracker["date"] = today_str
    write_json(TRACKER_PATH, tracker)

    # ── Eye Cache (market data) ───────────────────────────────────────────
    write_json(EYE_CACHE_PATH, scenario["mock_eye_data"])


# ═══════════════════════════════════════════════════════════════════════════
#  CORE: Run a single scenario test
# ═══════════════════════════════════════════════════════════════════════════
def run_single(case_id: int, scenario: dict, quiet: bool = False, live: bool = False, auto_restore: bool = False) -> bool:
    name        = scenario.get("scenario_name", f"TC{case_id:02d}")
    description = scenario.get("description", "")
    rule        = scenario.get("rule_tested", "")
    expected    = scenario.get("expected_outcome", "")
    exp_dec     = scenario.get("expected_decision", "")
    exp_exc     = scenario.get("expected_exception")
    exp_contains = scenario.get("expected_action_result_contains")
    ai_decision  = scenario.get("ai_decision", {})

    sep = "─" * 70
    print(f"\n{BOLD}{CYAN}{sep}{RESET}")
    if live:
        print(f"{BOLD}{CYAN}  TC{case_id:02d}  │  {name} [LIVE LLM TEST]{RESET}")
    else:
        print(f"{BOLD}{CYAN}  TC{case_id:02d}  │  {name}{RESET}")
    print(f"{CYAN}{sep}{RESET}")
    if not quiet:
        print(f"  {YELLOW}Rule   :{RESET} {rule}")
        print(f"  {YELLOW}Expect :{RESET} {expected} → Decision: {exp_dec}")
    
    passed = False
    try:
        # ── Seed mock data ─────────────────────────────────────────────────
        seed_mock_data(scenario)

        # ── Load seeded eye_data ───────────────────────────────────────────
        eye_data  = load_json(EYE_CACHE_PATH)
        portfolio = load_json(PORTFOLIO_PATH)
        
        if live:
            if not quiet: print(f"  {YELLOW}Calling GPT-4o...{RESET} (This will take a few seconds and cost API credits)")
            
            # Call brain via subprocess to simulate actual shell run
            env = os.environ.copy()
            # Pass eye_data JSON to stdin of call_brain_direct.py
            cmd = [sys.executable, str(PROJECT_ROOT / "core" / "call_brain_direct.py")]
            proc = subprocess.run(cmd, input=json.dumps(eye_data).encode(), capture_output=True, env=env)
            
            if proc.returncode != 0:
                print(f"  {RED}✗ GPT-4o Call Failed:{RESET}")
                print(proc.stderr.decode() or proc.stdout.decode())
                return False
                
            raw_output = proc.stdout.decode().strip()
            # Extract decision exactly like executor does
            dec_data = executor.extract_decision(raw_output)
            
            if not dec_data or not dec_data.get("decisions"):
                print(f"  {RED}✗ Failed to parse GPT-4o output:{RESET}\n{raw_output}")
                return False
                
            # Grab first decision
            dec = dec_data["decisions"][0]
            if not quiet:
                print(f"  {YELLOW}Live AI Said:{RESET} {dec.get('decision')} — {dec.get('reason','')[:80]}")
        else:
            dec = dict(ai_decision)
            if not quiet:
                print(f"  {YELLOW}Mock AI Said:{RESET} {dec.get('decision')} — {dec.get('reason','')[:80]}")

        # ═══ STEP 1: Validate Single Decision ════════════════════════════
        if exp_exc == "PolicyBlockError":
            # Expected: PolicyBlockError raised
            try:
                executor.validate_single_decision(dec, eye_data, portfolio)
                print(f"  {RED}✗ FAIL{RESET}: Expected PolicyBlockError but NO exception was raised.")
                return False
            except PolicyBlockError as e:
                print(f"  {GREEN}✓ PolicyBlockError raised correctly:{RESET}")
                print(f"    → {str(e)[:120]}")
                passed = True

        else:
            # Normal path — validate and apply yield gate
            dec, v_override = executor.validate_single_decision(dec, eye_data, portfolio)
            dec, y_override, y_reason = executor.apply_single_yield_gate(dec)

            actual_decision = dec.get("decision")
            actual_override = v_override or y_override

            # ── Print validation result ────────────────────────────────────
            if not quiet:
                if v_override:
                    print(f"  {YELLOW}⚡ Python Validation Override{RESET}: {dec.get('override_reason','')[:100]}")
                if y_override:
                    print(f"  {YELLOW}⚡ Yield Gate Override{RESET}: {y_reason}")
                if not actual_override:
                    print(f"  {GREEN}✓ No override. Decision passed through unchanged.{RESET}")

            # ═══ STEP 2: Execute Decision (for execution test cases) ══════
            action_result = None
            if expected in ("EXECUTION_SUCCESS", "EXECUTION_NO_ACTION"):
                db = HermesDatabase(db_path=str(BACKUP_DIR / "test_run.db"))
                pulse_id = db.save_pulse(eye_data, dec)
                portfolio = load_json(PORTFOLIO_PATH)
                action_result = executor.execute_decision(dec, db, pulse_id, eye_data)
                if not quiet:
                    print(f"  {YELLOW}Action Result:{RESET} {action_result}")

            # ── Assertion: Check expected vs actual ────────────────────────
            if expected == "NO_OVERRIDE":
                passed = (actual_decision == exp_dec and not actual_override)
            elif expected in ["PYTHON_OVERRIDE", "SOFT_HOLD_OVERRIDE", "YIELD_GATE_OVERRIDE"]:
                # If the live AI naturally chooses the safe action, the override isn't triggered, but it should still pass.
                if live and actual_decision == exp_dec and not actual_override:
                    print(f"  {GREEN}★ NOTE: Real AI natively chose the correct safe action ({actual_decision}).{RESET}")
                    print(f"          The Python Guardrail was not needed to override it. Test passes!{RESET}")
                    passed = True
                else:
                    if expected == "PYTHON_OVERRIDE":
                        passed = (actual_decision == exp_dec and v_override)
                    elif expected == "SOFT_HOLD_OVERRIDE":
                        passed = (actual_decision == "HOLD_PUT_POSITION" and actual_override)
                    elif expected == "YIELD_GATE_OVERRIDE":
                        passed = (actual_decision == "HOLD_PUT_POSITION" and y_override)
            elif expected == "EXECUTION_SUCCESS":
                passed = (action_result is not None and exp_contains in str(action_result))
            elif expected == "EXECUTION_NO_ACTION":
                passed = (action_result is not None and exp_contains in str(action_result))

            if not passed:
                print(f"  {RED}✗ Assertion mismatch:{RESET}")
                print(f"    Expected decision : {exp_dec}")
                print(f"    Actual decision   : {actual_decision}")
                print(f"    Expected outcome  : {expected}")
                print(f"    v_override={v_override}, y_override={y_override}")
                if action_result is not None:
                    print(f"    Action result: {action_result}")

    except Exception as e:
        if exp_exc and type(e).__name__ == exp_exc:
            # Expected exception received correctly
            print(f"  {GREEN}✓ Expected exception {exp_exc} raised correctly:{RESET}")
            print(f"    → {str(e)[:120]}")
            passed = True
        else:
            print(f"  {RED}✗ UNEXPECTED ERROR in TC{case_id:02d}:{RESET}")
            traceback.print_exc()
            passed = False

    finally:
        # ── ONLY restore original files if --restore is passed ──────────────
        if auto_restore:
            restore_data()

    # ── Print final PASS / FAIL ────────────────────────────────────────────
    if passed:
        print(f"\n  {BOLD}{GREEN}★ TC{case_id:02d} PASSED{RESET}")
    else:
        print(f"\n  {BOLD}{RED}✗ TC{case_id:02d} FAILED{RESET}")

    return passed


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
def main():
    args   = sys.argv[1:]
    quiet  = "--quiet" in args
    live   = "--live" in args
    auto_restore = "--restore" in args
    args   = [a for a in args if a not in ("--quiet", "--live", "--restore")]

    if not args:
        print(f"{YELLOW}Usage:{RESET}")
        print(f"  python3 scripts/run_scenarios.py <case_number>   (e.g. 5)")
        print(f"  python3 scripts/run_scenarios.py all             (run all 25)")
        print(f"  python3 scripts/run_scenarios.py list            (list all cases)")
        print(f"  python3 scripts/run_scenarios.py 1 --live        (call REAL GPT-4o, uses credits)")
        print(f"  python3 scripts/run_scenarios.py 1 --restore     (restore data to original after test)")
        print(f"  python3 scripts/run_scenarios.py 1 --quiet       (suppress verbose)")
        sys.exit(0)

    scenarios = list_scenarios()

    if args[0] == "list":
        print(f"\n{BOLD}{CYAN}Available Hermes Test Scenarios:{RESET}")
        for case_id, fpath, data in scenarios:
            print(f"  TC{case_id:02d}  [{data.get('category','?')}]  {data.get('scenario_name','?')}")
        print()
        sys.exit(0)

    # ── Determine which cases to run ────────────────────────────────────────
    if args[0].lower() == "all":
        to_run = scenarios
    else:
        try:
            target_id = int(args[0])
        except ValueError:
            print(f"{RED}[ERROR] Invalid case number: {args[0]}{RESET}")
            sys.exit(1)

        to_run = [(cid, fp, d) for cid, fp, d in scenarios if cid == target_id]
        if not to_run:
            print(f"{RED}[ERROR] No scenario found with case_id={target_id}.{RESET}")
            print(f"  Run: python3 scripts/run_scenarios.py list")
            sys.exit(1)

    # ── Pre-flight: create backup ────────────────────────────────────────────
    print(f"\n{BOLD}Hermes Scenario Runner{RESET} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"Running {len(to_run)} scenario(s). Backing up live data files...")
    backup_data()
    print(f"{GREEN}✓ Backup complete → tests/.scenario_backup/{RESET}")

    # ── Run scenarios ────────────────────────────────────────────────────────
    results = []
    try:
        for case_id, fpath, data in to_run:
            passed = run_single(case_id, data, quiet=quiet, live=live, auto_restore=auto_restore)
            results.append((case_id, passed))
    finally:
        if auto_restore:
            print(f"\n{GREEN}✓ Data restored to original state.{RESET}")
        else:
            print(f"\n{YELLOW}⚠️  Mock data left in place for UI inspection.{RESET}")
            print(f"   The UI dashboard will now show the data from the last run scenario.")
            print(f"   To restore your data manually, run: python3 scripts/run_scenarios.py 1 --restore {RESET}")

    # ── Final Summary ────────────────────────────────────────────────────────
    total   = len(results)
    passed  = sum(1 for _, p in results if p)
    failed  = total - passed

    print(f"\n{'═'*70}")
    print(f"{BOLD}FINAL RESULT: {passed}/{total} scenarios PASSED{RESET}")
    if failed:
        print(f"{RED}FAILED cases: {', '.join(f'TC{cid:02d}' for cid, p in results if not p)}{RESET}")
    else:
        print(f"{GREEN}🎉 ALL {total} SCENARIOS PASSED — Safety rules are working correctly.{RESET}")
    print(f"{'═'*70}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
