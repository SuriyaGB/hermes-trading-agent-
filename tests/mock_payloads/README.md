# 🏛️ Hermes Mock Scenario Payloads — README

This directory contains **25 fixed JSON mock payloads** used to test every safety
rule and decision gate in the Hermes Options Wheel AI Trading Agent — **without
needing live market hours, a live LLM call, or real capital**.

---

## ▶️ How to Run

```bash
# From the project root directory, with venv active:
source .hermes/.env  # Required for --live mode
source krc_venv/bin/activate

# 1️⃣ ZERO API COST MODE (Local Python Rules Check)
PYTHONPATH=. python3 scripts/run_scenarios.py 1      # TC01: Normal Hold
PYTHONPATH=. python3 scripts/run_scenarios.py 2      # TC02: Gamma Safety Close

# 2️⃣ LIVE AI MODE (Uses Real GPT-4o)
PYTHONPATH=. python3 scripts/run_scenarios.py 1 --live

# 3️⃣ BATCH RUNNING
PYTHONPATH=. python3 scripts/run_scenarios.py list   # See all test names
PYTHONPATH=. python3 scripts/run_scenarios.py all    # Run all 25 local cases
```

### 🧠 The Two Testing Modes

| Mode | Command | Modifies Live Files? | LLM Called? | Cost | What it Proves |
|---|---|---|---|---|---|
| **Zero-Cost** | `run_scenarios.py 1` | Temporarily (Auto-restores) | ❌ No (Mock string) | **$0.00** | Python logic correctly handles states. |
| **Live AI** | `run_scenarios.py 1 --live` | Temporarily (Auto-restores) | ✅ Yes (GPT-4o) | ~$0.02 | Python Smart Guard catches real AI mistakes. |

> **Live File Safety**: Both modes backup `data/*.json`, run the test, and immediately restore the live data. Your actual portfolio is safe.



---

## 📁 Scenario File Map

| File | TC# | Category | Rule Tested | Expected |
|---|---|---|---|---|
| `tc01_normal_hold.json` | 01 | Decision Tree | Rule 7 – Default Hold | HOLD (no override) |
| `tc02_gamma_safety_close.json` | 02 | Decision Tree | Rule 4 – Gamma Safety (DTE≤15, profit≥50%) | CLOSE_FOR_PROFIT |
| `tc03_worthless_exit.json` | 03 | Decision Tree | Rule 3 – Standard Profit ≥75% | CLOSE_FOR_PROFIT |
| `tc04_target_profit_hit.json` | 04 | Decision Tree | Rule 3 – 78% profit | CLOSE_FOR_PROFIT |
| `tc05_emergency_close_dte0.json` | 05 | Decision Tree | Rule 1 – DTE=0 Emergency Close | CLOSE_FOR_PROFIT |
| `tc06_boundary_75pct_exact.json` | 06 | Decision Tree | Rule 3 – Exactly at 75.0% (boundary test) | CLOSE_FOR_PROFIT |
| `tc07_below_75pct_no_override.json` | 07 | Decision Tree | Rule 3 – 74.9% just below threshold | HOLD (no override) |
| `tc08_otm_roll_allowed.json` | 08 | Decision Tree | Roll Gate – OTM delta=-0.15 < 0.30 | ROLL_PUT allowed |
| `tc09_itm_roll_blocked.json` | 09 | Decision Tree | Roll Gate – ITM delta=-0.35 ≥ 0.30 | PolicyBlockError |
| `tc10_normal_entry_all_gates_clear.json` | 10 | Safety Gates | All gates pass – CASH_ONLY, VIX normal | SELL_NEW_PUT |
| `tc11_bearish_day_cap_block.json` | 11 | Safety Gates | BEARISH_DAY cap=1, already at cap | PolicyBlockError |
| `tc12_max_risk_units_block.json` | 12 | Safety Gates | Max 4 units reached – any new sell blocked | PolicyBlockError |
| `tc13_normal_day_pacing_cap.json` | 13 | Pacing Rules | NORMAL_DAY, contracts_written=1 (cap=1) | HOLD (soft override) |
| `tc14_hard_daily_cap_2.json` | 14 | Pacing Rules | Hard cap: contracts_written=2 any day | HOLD (soft override) |
| `tc15_good_day_better_option_passes.json` | 15 | Pacing Rules | GOOD_DAY: lower strike + higher premium | SELL allowed |
| `tc16_good_day_better_option_rejected_strike.json` | 16 | Pacing Rules | GOOD_DAY: new strike NOT lower | HOLD (soft override) |
| `tc17_good_day_better_option_rejected_premium.json` | 17 | Pacing Rules | GOOD_DAY: new premium NOT higher | HOLD (soft override) |
| `tc18_yield_gate_too_cheap.json` | 18 | Yield Gate | (premium/strike)*100 = 0.45% < 1.0% floor | HOLD (yield override) |
| `tc19_yield_gate_exact_floor.json` | 19 | Yield Gate | yield = 1.0% exactly (boundary inclusion) | SELL allowed |
| `tc20_yield_gate_good_premium.json` | 20 | Yield Gate | yield = 1.58% well above floor | SELL allowed |
| `tc21_sell_new_call_allowed.json` | 21 | Decision Tree | Covered Call entry – ASSIGNED phase | SELL_NEW_CALL |
| `tc22_hold_call_profit_override.json` | 22 | Decision Tree | Rule 3 on CALL – 80% profit → close | CLOSE_FOR_PROFIT |
| `tc23_gamma_safety_call.json` | 23 | Decision Tree | Rule 4 on CALL – DTE=11, profit=52% | CLOSE_FOR_PROFIT |
| `tc24_close_for_profit_execution.json` | 24 | Execution Test | CLOSE_FOR_PROFIT with matching position | Execution success |
| `tc25_close_no_matching_position.json` | 25 | Execution Test | CLOSE_FOR_PROFIT with NO matching position | Safe no-op |

---

## 🧠 How Each JSON File is Structured

Every scenario file has these fixed sections:

```json
{
  "case_id": 1,
  "scenario_name": "TC01 – Normal Hold",
  "category": "Decision Tree Rules",
  "description": "Human-readable explanation of what this test proves.",
  "rule_tested": "Exact rule name and condition.",
  "expected_decision": "HOLD_PUT_POSITION",
  "expected_outcome": "NO_OVERRIDE",

  "ai_decision": { ... },      ← Simulated LLM decision input
  "mock_portfolio": { ... },   ← Seeded into data/portfolio.json
  "mock_trade_state": { ... }, ← Seeded into data/trade_state.json
  "mock_tracker": { ... },     ← Seeded into data/intraday_tracker.json
  "mock_eye_data": { ... }     ← Seeded into .eye_cache.json
}
```

The runner script:
1. Backs up all 4 live data files
2. Seeds mock data from the JSON
3. Calls `validate_single_decision()` and `apply_single_yield_gate()` directly
4. Checks the result vs `expected_outcome`
5. Restores all 4 live files (even if the test crashes)

---

## 🎯 What the Expected Outcomes Mean

| `expected_outcome` | Meaning |
|---|---|
| `NO_OVERRIDE` | Python validation passes unchanged. AI decision stands. |
| `PYTHON_OVERRIDE` | Python rule fires. Decision changed (e.g. HOLD → CLOSE). |
| `SOFT_HOLD_OVERRIDE` | Pacing/cap block caught. Soft-overrides to HOLD_PUT_POSITION. |
| `YIELD_GATE_OVERRIDE` | Yield Gate fires. SELL overridden to HOLD. |
| `POLICY_BLOCK_ERROR` | Hard gate raises PolicyBlockError. Execution halts this decision. |
| `EXECUTION_SUCCESS` | execute_decision runs and returns a success string. |
| `EXECUTION_NO_ACTION` | execute_decision finds no matching position. Returns 'No Action'. |
