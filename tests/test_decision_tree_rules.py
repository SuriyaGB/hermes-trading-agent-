"""
Simulation Test: SKILL_AAPL.md Decision Tree Rules
Tests the 7-rule put decision tree logic we implemented.
Each test simulates a specific scenario and verifies the correct rule fires.
"""

# ─────────────────────────────────────────────────────────────────────────────
# The Decision Tree Logic (mirrors exactly what we wrote into SKILL_AAPL.md)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_put_position(dte, profit_pct, current_premium, delta):
    """
    Mirrors the SKILL_AAPL.md decision_tree_puts logic exactly.
    Returns (rule_number, decision, reason).
    """
    # RULE 1 — Emergency Close (DTE < 1)
    if dte < 1:
        if profit_pct > 0:
            return (1, "CLOSE_FOR_PROFIT",
                    f"RULE 1 EMERGENCY CLOSE: DTE={dte} < 1. Option expires today. "
                    f"Profit={profit_pct:.1f}%. Closing to avoid auto-assignment risk.")
        else:
            return (1, "CLOSE_FOR_LOSS",
                    f"RULE 1 EMERGENCY CLOSE: DTE={dte} < 1. Option expires today. "
                    f"Profit={profit_pct:.1f}% (loss). Closing to prevent forced assignment at a loss.")

    # RULE 2 — Worthless Option Exit (current_premium <= $0.10)
    if current_premium <= 0.10:
        return (2, "CLOSE_FOR_PROFIT",
                f"RULE 2 WORTHLESS EXIT: current_premium=${current_premium:.2f} <= $0.10. "
                f"Profit={profit_pct:.1f}%. Locking in gains, freeing $29,000+ margin for new trade.")

    # RULE 3 — Standard Profit Target (profit_pct >= 75%)
    if profit_pct >= 75.0:
        return (3, "CLOSE_FOR_PROFIT",
                f"RULE 3 STANDARD PROFIT: profit_pct={profit_pct:.1f}% >= 75.0%. "
                f"DTE={dte}. Captured target. Closing and redeploying capital.")

    # RULE 4 — Gamma Safety Exit (DTE <= 15 and profit_pct >= 50%)
    if dte <= 15 and profit_pct >= 50.0:
        return (4, "CLOSE_FOR_PROFIT",
                f"RULE 4 GAMMA SAFETY: DTE={dte} <= 15 AND profit_pct={profit_pct:.1f}% >= 50.0%. "
                f"Rising gamma risk. Locking in profits now.")

    # RULE 5 — Roll Put (DTE <= 15, OTM, profit_pct < 50%)
    if dte <= 15 and delta > -0.30 and profit_pct < 50.0:
        return (5, "ROLL_PUT",
                f"RULE 5 ROLL PUT: DTE={dte} <= 15, still OTM (delta={delta:.2f} > -0.30), "
                f"profit_pct={profit_pct:.1f}% < 50%. Extending to next expiry for net credit.")

    # RULE 6 — Accept Assignment (DTE <= 15 and ITM)
    if dte <= 15 and delta <= -0.30:
        return (6, "HOLD_PUT_POSITION",
                f"RULE 6 ACCEPT ASSIGNMENT: DTE={dte} <= 15, Put is ITM (delta={delta:.2f} <= -0.30). "
                f"profit_pct={profit_pct:.1f}%. Accepting assignment. Preparing for Covered Call phase.")

    # RULE 7 — Hold (default)
    return (7, "HOLD_PUT_POSITION",
            f"RULE 7 HOLD: DTE={dte}, profit_pct={profit_pct:.1f}%, "
            f"premium=${current_premium:.2f}, delta={delta:.2f}. "
            f"Time decay working in our favour. No exit condition met.")


# ─────────────────────────────────────────────────────────────────────────────
# Test Runner
# ─────────────────────────────────────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"

def run_test(test_name, dte, profit_pct, current_premium, delta, expected_rule, expected_decision):
    rule, decision, reason = evaluate_put_position(dte, profit_pct, current_premium, delta)
    status = PASS if (rule == expected_rule and decision == expected_decision) else FAIL
    print(f"\n{'='*70}")
    print(f"  {status}  {test_name}")
    print(f"{'='*70}")
    print(f"  Inputs  → DTE={dte}, Profit={profit_pct}%, Premium=${current_premium}, Delta={delta}")
    print(f"  Expected → Rule {expected_rule}: {expected_decision}")
    print(f"  Got      → Rule {rule}: {decision}")
    print(f"  Reason   → {reason}")
    if status == FAIL:
        print(f"  ⚠️  MISMATCH! Rule {rule} fired but expected Rule {expected_rule}.")
    return status == PASS

results = []

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 1: The "Classic Scenario" from Yesterday
# → Active put has 25.2% profit, 28 DTE — the OLD bot was confused.
# → EXPECTED: HOLD (Rule 7) — nothing has triggered yet.
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_test(
    test_name   = "TC1: 28 DTE, 25.2% profit — Should HOLD (no exit rule triggered)",
    dte         = 28,
    profit_pct  = 25.2,
    current_premium = 2.95,
    delta       = -0.1826,
    expected_rule     = 7,
    expected_decision = "HOLD_PUT_POSITION"
))

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 2: The "Gamma Safety" scenario
# → 12 DTE, 55% profit — OLD bot had NO rule for this. It would have tried to ROLL.
# → EXPECTED: CLOSE_FOR_PROFIT (Rule 4 — Gamma Safety Exit)
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_test(
    test_name   = "TC2: 12 DTE, 55% profit — Should CLOSE (Gamma Safety, Rule 4)",
    dte         = 12,
    profit_pct  = 55.0,
    current_premium = 1.80,
    delta       = -0.18,
    expected_rule     = 4,
    expected_decision = "CLOSE_FOR_PROFIT"
))

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 3: The "Worthless" scenario
# → 8 DTE, option is trading at $0.08 (worthless), 97% profit.
# → EXPECTED: CLOSE_FOR_PROFIT (Rule 2 — Worthless Exit, fires BEFORE Rule 3)
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_test(
    test_name   = "TC3: 8 DTE, $0.08 premium, 97% profit — Should CLOSE (Worthless Rule 2)",
    dte         = 8,
    profit_pct  = 97.0,
    current_premium = 0.08,
    delta       = -0.04,
    expected_rule     = 2,
    expected_decision = "CLOSE_FOR_PROFIT"
))

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 4: The "Standard Profit" scenario
# → 22 DTE (not near expiry), profit hit 78% — well above 75% target.
# → EXPECTED: CLOSE_FOR_PROFIT (Rule 3 — Standard Profit Target)
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_test(
    test_name   = "TC4: 22 DTE, 78% profit — Should CLOSE (Standard Profit Rule 3)",
    dte         = 22,
    profit_pct  = 78.0,
    current_premium = 0.88,
    delta       = -0.09,
    expected_rule     = 3,
    expected_decision = "CLOSE_FOR_PROFIT"
))

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 5: The "Roll" scenario — low profit near expiry, still OTM
# → 10 DTE, only 30% profit, still OTM (delta -0.15)
# → EXPECTED: ROLL_PUT (Rule 5)
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_test(
    test_name   = "TC5: 10 DTE, 30% profit, OTM (delta -0.15) — Should ROLL_PUT (Rule 5)",
    dte         = 10,
    profit_pct  = 30.0,
    current_premium = 2.80,
    delta       = -0.15,
    expected_rule     = 5,
    expected_decision = "ROLL_PUT"
))

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 6: The "Accept Assignment" scenario — ITM near expiry
# → 8 DTE, -15% loss, delta -0.55 (deep ITM, stock crashed below strike)
# → EXPECTED: HOLD_PUT_POSITION (Rule 6 — Accept Assignment)
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_test(
    test_name   = "TC6: 8 DTE, -15% loss, Deep ITM (delta -0.55) — Should HOLD/Accept Assignment (Rule 6)",
    dte         = 8,
    profit_pct  = -15.0,
    current_premium = 4.60,
    delta       = -0.55,
    expected_rule     = 6,
    expected_decision = "HOLD_PUT_POSITION"
))

# ─────────────────────────────────────────────────────────────────────────────
# SCAN CAPACITY GATE TESTS (NEW — replaces fake-position pacing tests)
# These test the scan_capacity Python calculation that now lives in
# get_ibkr_analysis.py. This is the exact logic that determines
# can_open_new_put = True or False.
# ─────────────────────────────────────────────────────────────────────────────

def compute_scan_capacity(risk_units, contracts_written_today, day_classification,
                           vix, earnings_days, remaining_buying_power, price_seen):
    """
    Mirrors the scan_capacity calculation in get_ibkr_analysis.py exactly.
    Returns the scan_capacity dict with can_open_new_put True or False.
    """
    max_allowed_units = 1 if day_classification == "BEARISH_DAY" else 4
    daily_cap         = 1 if day_classification in ["QUIET_DAY", "BEARISH_DAY"] else 2

    earnings_safe    = (earnings_days > 7) if earnings_days else True
    buying_power_ok  = remaining_buying_power >= (price_seen * 100 * 0.20)
    vix_ok           = 13.0 <= vix <= 29.9
    risk_ok          = risk_units < max_allowed_units
    pacing_ok        = contracts_written_today < daily_cap

    can_open = earnings_safe and buying_power_ok and vix_ok and risk_ok and pacing_ok

    if not can_open:
        if not earnings_safe:     reason = f"Earnings gate failed."
        elif not buying_power_ok: reason = f"Buying power gate failed."
        elif not vix_ok:          reason = f"VIX gate failed."
        elif not risk_ok:         reason = f"Risk units gate failed."
        else:                     reason = f"Pacing gate failed."
    else:
        reason = "All gates passed."

    return {
        "can_open_new_put"   : can_open,
        "slots_available"    : max(0, max_allowed_units - risk_units),
        "daily_cap_remaining": max(0, daily_cap - contracts_written_today),
        "earnings_safe"      : earnings_safe,
        "buying_power_ok"    : buying_power_ok,
        "vix_ok"             : vix_ok,
        "reason"             : reason
    }


def run_capacity_test(test_name, expected_can_open, **kwargs):
    result = compute_scan_capacity(**kwargs)
    status = PASS if result["can_open_new_put"] == expected_can_open else FAIL
    print(f"\n{'='*70}")
    print(f"  {status}  {test_name}")
    print(f"{'='*70}")
    print(f"  Expected can_open_new_put = {expected_can_open}")
    print(f"  Got      can_open_new_put = {result['can_open_new_put']}")
    print(f"  Gates: earnings_safe={result['earnings_safe']}, "
          f"buying_power_ok={result['buying_power_ok']}, "
          f"vix_ok={result['vix_ok']}")
    print(f"  Reason: {result['reason']}")
    if status == FAIL:
        print(f"  ⚠️  MISMATCH!")
    return status == PASS


# TC7: Yesterday's exact situation — 1 open put, free capacity, normal day
results.append(run_capacity_test(
    "TC7: NORMAL_DAY, 1 open, written=0, earnings safe — can_open=True",
    expected_can_open    = True,
    risk_units           = 1,
    contracts_written_today = 0,
    day_classification   = "NORMAL_DAY",
    vix                  = 18.5,
    earnings_days        = 45,
    remaining_buying_power = 125000,
    price_seen           = 311.41
))

# TC8: Daily cap already reached (NORMAL_DAY allows 2, written=2)
results.append(run_capacity_test(
    "TC8: NORMAL_DAY, written=2 — can_open=False (pacing gate blocks)",
    expected_can_open    = False,
    risk_units           = 2,
    contracts_written_today = 2,
    day_classification   = "NORMAL_DAY",
    vix                  = 18.5,
    earnings_days        = 45,
    remaining_buying_power = 125000,
    price_seen           = 311.41
))

# TC9: BEARISH_DAY with 1 contract — cap is 1 on bearish days
results.append(run_capacity_test(
    "TC9: BEARISH_DAY, 1 open, written=0 — can_open=False (risk gate blocks)",
    expected_can_open    = False,
    risk_units           = 1,
    contracts_written_today = 0,
    day_classification   = "BEARISH_DAY",
    vix                  = 22.0,
    earnings_days        = 45,
    remaining_buying_power = 125000,
    price_seen           = 311.41
))

# TC10: Earnings too close — earnings_safe gate blocks
results.append(run_capacity_test(
    "TC10: Earnings in 3 days — can_open=False (earnings_safe gate blocks)",
    expected_can_open    = False,
    risk_units           = 1,
    contracts_written_today = 0,
    day_classification   = "NORMAL_DAY",
    vix                  = 18.5,
    earnings_days        = 3,
    remaining_buying_power = 125000,
    price_seen           = 311.41
))

# TC11: VIX too high (fear spike) — vix gate blocks
results.append(run_capacity_test(
    "TC11: VIX=35 (fear spike) — can_open=False (vix_ok gate blocks)",
    expected_can_open    = False,
    risk_units           = 0,
    contracts_written_today = 0,
    day_classification   = "GOOD_DAY",
    vix                  = 35.0,
    earnings_days        = 45,
    remaining_buying_power = 125000,
    price_seen           = 311.41
))

# TC12: CASH_ONLY — no positions, no writes today, normal conditions
# CRITICAL: This must allow opening because Phase 1 handles CASH_ONLY
results.append(run_capacity_test(
    "TC12: CASH_ONLY (risk_units=0), all gates clear — can_open=True",
    expected_can_open    = True,
    risk_units           = 0,
    contracts_written_today = 0,
    day_classification   = "NORMAL_DAY",
    vix                  = 18.5,
    earnings_days        = 45,
    remaining_buying_power = 250000,
    price_seen           = 311.41
))

# These test the Python-level pacing rules that control when NEW_PUT_SCAN
# results in SELL_NEW_PUT vs HOLD_PUT_POSITION.
# Previously UNTESTED — root cause of the multi-contract failure.
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_new_put_scan(risk_units, contracts_written_today, day_classification,
                           best_delta, best_premium, vix):
    """
    Mirrors the pacing_rules logic from SKILL_AAPL.md for NEW_PUT_SCAN.
    Returns (decision, reason).
    """
    # Gate 1: VIX check
    if vix < 13:
        return "HOLD_PUT_POSITION", f"VIX={vix} < 13. Premiums too cheap. No new puts."
    if vix >= 30:
        return "HOLD_PUT_POSITION", f"VIX={vix} >= 30. Market too fearful. No new opens."

    # Gate 2: Risk unit capacity
    max_units = 1 if day_classification == "BEARISH_DAY" else 4
    if risk_units >= max_units:
        return "HOLD_PUT_POSITION", f"Risk units {risk_units} >= max {max_units} for {day_classification}."

    # Gate 3: Daily pacing
    if contracts_written_today >= 2:
        return "HOLD_PUT_POSITION", f"Daily cap (2) reached. contracts_written_today={contracts_written_today}."
    if contracts_written_today == 1 and day_classification in ["QUIET_DAY", "NORMAL_DAY"]:
        return "HOLD_PUT_POSITION", f"Daily cap (1) for {day_classification}. Already wrote 1 contract today."

    # Gate 4: Delta qualification
    delta_ranges = {
        "GOOD_DAY":    (-0.30, -0.25),
        "NORMAL_DAY":  (-0.25, -0.20),
        "QUIET_DAY":   (-0.20, -0.15),
        "BEARISH_DAY": (-0.15, -0.10),
    }
    lo, hi = delta_ranges.get(day_classification, (-0.30, -0.15))
    if not (lo <= best_delta <= hi):
        return "HOLD_PUT_POSITION", f"Delta {best_delta} outside range [{lo}, {hi}] for {day_classification}."

    # Gate 5: Premium floor
    if best_premium < 0.50:
        return "HOLD_PUT_POSITION", f"Premium ${best_premium} < $0.50 floor."

    return "SELL_NEW_PUT", (
        f"All gates passed. risk_units={risk_units}/{max_units}. "
        f"written_today={contracts_written_today}. {day_classification}. "
        f"Delta={best_delta} in range. Premium=${best_premium} >= $0.50."
    )


def run_scan_test(test_name, risk_units, contracts_written_today, day_classification,
                  best_delta, best_premium, vix, expected_decision):
    decision, reason = evaluate_new_put_scan(
        risk_units, contracts_written_today, day_classification,
        best_delta, best_premium, vix
    )
    status = PASS if decision == expected_decision else FAIL
    print(f"\n{'='*70}")
    print(f"  {status}  {test_name}")
    print(f"{'='*70}")
    print(f"  Inputs   → risk_units={risk_units}, written_today={contracts_written_today}, "
          f"day={day_classification}, delta={best_delta}, premium=${best_premium}, VIX={vix}")
    print(f"  Expected → {expected_decision}")
    print(f"  Got      → {decision}")
    print(f"  Reason   → {reason}")
    if status == FAIL:
        print(f"  ⚠️  MISMATCH! Got {decision} but expected {expected_decision}.")
    return status == PASS


# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 7: Normal day, 1 contract open, capacity available
# → Yesterday's exact situation. Should write a new put.
# → EXPECTED: SELL_NEW_PUT
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_scan_test(
    test_name             = "TC7: Normal day, 1 open, capacity free — Should SELL_NEW_PUT",
    risk_units            = 1,
    contracts_written_today = 0,
    day_classification    = "NORMAL_DAY",
    best_delta            = -0.22,
    best_premium          = 3.01,
    vix                   = 18.5,
    expected_decision     = "SELL_NEW_PUT"
))

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 8: Daily cap already reached (2 contracts written today)
# → Should NOT write another contract even though slots are free.
# → EXPECTED: HOLD_PUT_POSITION
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_scan_test(
    test_name             = "TC8: 2 contracts already written today — Should HOLD (daily cap)",
    risk_units            = 2,
    contracts_written_today = 2,
    day_classification    = "NORMAL_DAY",
    best_delta            = -0.22,
    best_premium          = 3.01,
    vix                   = 18.5,
    expected_decision     = "HOLD_PUT_POSITION"
))

# ─────────────────────────────────────────────────────────────────────────────
# TEST CASE 9: BEARISH_DAY with 1 contract already open
# → Max allowed is 1 on bearish days. Cap already reached.
# → EXPECTED: HOLD_PUT_POSITION
# ─────────────────────────────────────────────────────────────────────────────
results.append(run_scan_test(
    test_name             = "TC9: BEARISH_DAY, 1 contract open — Should HOLD (bearish cap=1)",
    risk_units            = 1,
    contracts_written_today = 0,
    day_classification    = "BEARISH_DAY",
    best_delta            = -0.12,
    best_premium          = 1.50,
    vix                   = 22.0,
    expected_decision     = "HOLD_PUT_POSITION"
))

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
passed = sum(results)
total  = len(results)
print(f"  FINAL RESULT: {passed}/{total} tests passed.")
if passed == total:
    print(f"  🎉 ALL TESTS PASSED. Exit logic + Entry/Scan pacing logic both correct.")
else:
    print(f"  ⚠️  {total - passed} test(s) FAILED. Review the logic above.")
print(f"{'='*70}\n")
