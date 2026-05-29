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
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
passed = sum(results)
total  = len(results)
print(f"  FINAL RESULT: {passed}/{total} tests passed.")
if passed == total:
    print(f"  🎉 ALL TESTS PASSED. Decision tree logic is working correctly.")
else:
    print(f"  ⚠️  {total - passed} test(s) FAILED. Review the logic above.")
print(f"{'='*70}\n")
