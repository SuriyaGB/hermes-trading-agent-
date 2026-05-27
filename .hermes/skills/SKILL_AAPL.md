<skill_file_metadata>
  symbol: AAPL
  strategy: Wheel
  version: 6.0
  last_hardened: 2026-05-25
</skill_file_metadata>

<instruction_set_aapl>

  <instruction id="IV_VOLATILITY_ANALYSIS">
    REASON: Volatility dictates entry sizing. Sell more contracts when fear is high.
    RULES:
    - GOOD_DAY (iv_current > 30% OR daily_change_pct <= -2.0%): Volatility spike or stock drop. You are permitted to write up to **2 contracts** today.
    - NORMAL_DAY (iv_current 15-30% AND daily_change_pct > -2.0%): Normal market. Proceed with standard pacing (max **1 contract** today).
    - QUIET_DAY (iv_current < 15%): Low fear. Cheap premium. Write max **1 contract** today and only at highly secure strikes.
  </instruction>

  <instruction id="EARNINGS_GAUNTLET">
    REASON: Never hold an option through a binary earnings event.
    RULES:
    - NEVER select an expiry that is AFTER the next earnings_days.
    - If earnings_days < 7: DANGER. (Blocked by Python Blackout Gate).
    - If no safe expiry exists in the option_chain: Output HOLD.
  </instruction>

</instruction_set_aapl>

# ═══════════════════════════════════════════════════════════════
# SECTION A — NON-NEGOTIABLE RULES (The Iron Guard)
# These are immutable laws of math and risk. No exceptions.
# ═══════════════════════════════════════════════════════════════

<hard_limits_aapl>
  1. MAX_RISK_UNITS: Capped at 4. Risk Units = (AAPL Shares / 100) + Active Put Contracts + Active Call Contracts.
  2. BUYING_POWER_ALLOCATION: Max allocated buying power is 50% of Net Liquidation Value (NLV).
  3. TREND_GATE_SCALING: If AAPL spot price < 200 SMA, the market is a BEARISH_DAY.
  4. STRIKE_DELTA_PACING: Select strike based on Delta:
     - GOOD_DAY = -0.25 to -0.30
     - NORMAL_DAY = -0.20 to -0.25
     - QUIET_DAY = -0.15 to -0.20
     - BEARISH_DAY = -0.10 to -0.15 (Max Risk Units = 1)
  5. MINIMUM_PREMIUM_FLOOR: Minimum premium collected must be >= $0.50 per contract. If no strike satisfies both Delta and $0.50 min, output WAIT_FOR_ENTRY.
  6. TIME_STOP (MIN_DTE): Close any Put or Call if DTE < 15 and it is still Out-of-The-Money (OTM) to avoid tail/gamma risk.
  8. EMERGENCY_CLOSE: If DTE < 1 for any open contract, execute an EMERGENCY CLOSE immediately.
  9. COST_BASIS_RULE: Never sell a Call below Adjusted Cost Basis (Adjusted Basis = Assignment Strike - Total Net Premium Collected).
</hard_limits_aapl>

# ═══════════════════════════════════════════════════════════════
# SECTION B — THE MULTI-CONTRACT DECISION TREE
# Brain must loop over and evaluate each active position.
# ═══════════════════════════════════════════════════════════════

<decision_tree_puts>
  FOR EACH active PUT position (check "active_positions" list):
  1. DTE < 1? ─────────────────────────────────► Execute CLOSE_FOR_PROFIT or CLOSE_FOR_LOSS (Emergency Close).
  2. Profit >= 80%? ───────────────────────────► Execute CLOSE_FOR_PROFIT.
  3. DTE <= 15 and Still OTM (Delta < 0.30)? ──► Execute ROLL_PUT (widen/extend for net credit).
  4. DTE <= 15 and ITM/ATM (Delta >= 0.30)? ───► Output HOLD_PUT_POSITION. Reasoning must explicitly state: "Put is ITM and DTE <= 15 — accept assignment, do not roll."
  5. Delta > 0.45 and DTE > 15? ───────────────► HOLD and monitor closely. Do not roll yet.
  6. None of the above? ──────────────────────► Execute HOLD_PUT_POSITION.
</decision_tree_puts>

<decision_tree_calls>
  FOR EACH active CALL position (check "active_positions" list):
  1. DTE < 1? ─────────────────────────────────► Execute CLOSE_FOR_PROFIT or CLOSE_FOR_LOSS (Emergency Close).
  2. Profit >= 80%? ───────────────────────────► Execute CLOSE_FOR_PROFIT.
  3. DTE <= 15 and ITM/ATM? ───────────────────► Execute ROLL_CALL (move strike up/out for net credit) to defend shares.
  4. None of the above? ──────────────────────► Execute HOLD_CALL_POSITION.
</decision_tree_calls>

# ═══════════════════════════════════════════════════════════════
# SECTION C — PACING & INTRADAY WRITE RULES
# ═══════════════════════════════════════════════════════════════

<pacing_rules>
  When scanning for NEW Put positions to sell (position_key = "NEW_PUT_SCAN"):
  1. Check risk capacity: Only proceed if current_risk_units < 4.
  2. Check trend pacing: If day_classification == BEARISH_DAY, Max Risk Units is capped at 1.
  3. Select strike by Delta bounds:
     - On GOOD_DAY: Target Delta range -0.25 to -0.30.
     - On NORMAL_DAY: Target Delta range -0.20 to -0.25.
     - On QUIET_DAY: Target Delta range -0.15 to -0.20.
     - On BEARISH_DAY: Target Delta range -0.10 to -0.15.
     If multiple strikes fit, prefer the one closest to the center of the range.
  5. Enforce Premium Floor: Collected premium must be >= $0.50.
  6. Check intraday_state:
     - If contracts_written_today >= 2: STOP. No new put trades allowed today.
     - If contracts_written_today == 1 AND day_classification is NORMAL_DAY/QUIET_DAY: STOP.
     - If contracts_written_today == 1 AND day_classification is GOOD_DAY:
       You may write a 2nd contract ONLY if:
       - Candidate Put Strike < first_strike (Safer)
       - Candidate Put Premium >= first_premium (Equal/Better premium)
       Otherwise, do not write a 2nd contract.
</pacing_rules>

# ═══════════════════════════════════════════════════════════════
# SECTION D — INPUT & OUTPUT SCHEMA
# ═══════════════════════════════════════════════════════════════

<input_schema_payload>
  You will receive a unified portfolio payload structure:
  - "portfolio_summary": Tracks NLV, allowed limits, and current risk units.
  - "active_positions": A list of active options and stock blocks.
  - "intraday_state": Tracker of trades executed today.
  - "market_regime": Live stock parameters, VIX, 200 SMA, and day classification.
</input_schema_payload>

<output_schema_override>
  You MUST output a strictly valid JSON object containing an array of decisions:

  {
    "decisions": [
      {
        "position_key": "string (matches 'position_key' of active position, or 'NEW_PUT_SCAN')",
        "decision": "string (SELL_NEW_PUT | SELL_NEW_CALL | HOLD_PUT_POSITION | HOLD_CALL_POSITION | HOLD_ASSIGNED_EQUITY | CLOSE_FOR_PROFIT | CLOSE_FOR_LOSS | ROLL_PUT | ROLL_CALL | ABORT_DUE_TO_RISK)",
        "close_strike": "float or null",
        "close_expiry": "string or null (format YYYYMMDD)",
        "strike_to_trade": "float or null",
        "dte_seen": "integer or null",
        "premium_to_collect": "float or null",
        "reason": "string (precise reason containing specific numbers)"
      }
    ]
  }
</output_schema_override>
