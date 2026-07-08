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
  5. MINIMUM_PREMIUM_FLOOR: Minimum premium collected must be >= $0.50 per contract.
     If no strike satisfies both Delta and $0.50 min, output HOLD_PUT_POSITION with reason stating
     "No qualifying strike found. Premium floor not met. Holding and waiting for better conditions."
  6. TIME_STOP (MIN_DTE): If DTE < 15 and position is still OTM:
      - If profit_pct >= 50%: Execute CLOSE_FOR_PROFIT (lock in gains, escape gamma risk).
      - If profit_pct < 50%: Execute ROLL_PUT or ROLL_CALL to next monthly expiry for net credit.
      - If position is ITM: Hold and accept assignment. Do NOT roll an ITM put.
      IMPORTANT: Refer to decision_tree_puts and decision_tree_calls below for exact rule order.
  8. EMERGENCY_CLOSE: If DTE < 1 for any open contract, execute an EMERGENCY CLOSE immediately.
  9. COST_BASIS_RULE: Never sell a Call below Adjusted Cost Basis (Adjusted Basis = Assignment Strike - Total Net Premium Collected).
</hard_limits_aapl>

# ═══════════════════════════════════════════════════════════════
# SECTION B — THE MULTI-CONTRACT DECISION TREE
# Brain must loop over and evaluate each active position.
# ═══════════════════════════════════════════════════════════════

<decision_tree_puts>
  FOR EACH active PUT position (check "active_positions" list). Evaluate rules in this exact order — stop at the first match:

  RULE 1 — EMERGENCY CLOSE (DTE < 1):
    If dte < 1:
    → Execute CLOSE_FOR_PROFIT (if profit_pct > 0) or CLOSE_FOR_LOSS (if profit_pct <= 0).
    REASON: Option expires today. Broker auto-assignment risk is critical. Exit immediately.

  RULE 2 — WORTHLESS OPTION EXIT (current_premium <= $0.10):
    If current_premium <= 0.10:
    → Execute CLOSE_FOR_PROFIT.
    REASON: Option is nearly worthless (current value = current_premium from live data).
             Holding it locks up the full remaining_buying_power shown in portfolio_summary
             just to capture a few more cents. Free the capital and write a fresh contract.

  RULE 3 — STANDARD PROFIT TARGET (profit_pct >= 75%):
    If profit_pct >= 75.0:
    → Execute CLOSE_FOR_PROFIT.
    REASON: Captured 75% of maximum premium. The remaining 25% takes disproportionately long
             to decay and is not worth the continuing risk exposure.

  RULE 4 — GAMMA SAFETY EXIT (DTE <= 15 and profit_pct >= 50%):
    If dte <= 15 AND profit_pct >= 50.0:
    → Execute CLOSE_FOR_PROFIT.
    REASON: Under 15 days left and already profitable. Gamma risk rises sharply near expiry.
             A sudden stock move can erase gains. Lock in profits now and redeploy capital.

  RULE 5 — ROLL PUT (DTE <= 15 and OTM and profit_pct < 50%):
    If dte <= 15 AND delta > -0.30 (Still OTM) AND profit_pct < 50.0:
    → Execute ROLL_PUT (buy to close current, sell next monthly expiry for net credit).
    REASON: Approaching expiry with insufficient profit. Extend to next cycle for more premium.
             Only roll if net credit is achievable. Never roll for a debit.
    IMPORTANT CONSTRAINT: The new expiry MUST be selected from the valid_expiries list (between 30 and 50 DTE). Never select an expiry > 50 DTE or an unlisted date. If no valid expiry offers a net credit >= $0.25 per contract ($25 total), output HOLD_PUT_POSITION instead of rolling beyond 50 DTE or locking capital for pennies.

  RULE 6 — ACCEPT ASSIGNMENT (DTE <= 15 and ITM):
    If dte <= 15 AND delta <= -0.30 (ITM/ATM):
    → Execute HOLD_PUT_POSITION.
    Reason must explicitly state: "Put is ITM with DTE <= 15 — accepting assignment. Preparing for Covered Call phase."
    REASON: Stock moved below strike. Rolling ITM puts is too expensive. Accept 100 AAPL shares
             at the strike price (below market cost basis) and proceed to Phase 3 (sell Covered Call).

  RULE 7 — HOLD (Default, all other conditions):
    → Execute HOLD_PUT_POSITION.
    REASON: None of the above conditions met. Time decay is working in our favour. Hold.
</decision_tree_puts>

<decision_tree_calls>
  FOR EACH active CALL position (check "active_positions" list). Evaluate rules in this exact order — stop at the first match:

  RULE 1 — EMERGENCY CLOSE (DTE < 1):
    If dte < 1:
    → Execute CLOSE_FOR_PROFIT (if profit_pct > 0) or CLOSE_FOR_LOSS (if profit_pct <= 0).
    REASON: Call expires today. Exit immediately to avoid surprise assignment of shares.

  RULE 2 — WORTHLESS OPTION EXIT (current_premium <= $0.10):
    If current_premium <= 0.10:
    → Execute CLOSE_FOR_PROFIT.
    REASON: Call is nearly worthless. Free the shares from the covered call obligation.
             This allows selling a new Call at a fresh, higher premium.

  RULE 3 — STANDARD PROFIT TARGET (profit_pct >= 75%):
    If profit_pct >= 75.0:
    → Execute CLOSE_FOR_PROFIT.
    REASON: Captured 75% of maximum Call premium. Close and re-sell a new Covered Call.

  RULE 4 — GAMMA SAFETY EXIT (DTE <= 15 and profit_pct >= 50%):
    If dte <= 15 AND profit_pct >= 50.0:
    → Execute CLOSE_FOR_PROFIT.
    REASON: Under 15 days left and already profitable at 50%+. Close to avoid gamma risk.

  RULE 5 — ROLL CALL (DTE <= 15 and ITM/ATM and profit_pct < 50%):
    If dte <= 15 AND stock price approaching or above Call strike (delta >= 0.30) AND profit_pct < 50.0:
    → Execute ROLL_CALL (buy to close current Call, sell new Call at higher strike, next monthly expiry, for net credit).
    REASON: Stock rallying toward strike with little time left. Roll up and out to defend shares
             and collect more premium. Only roll if net credit. Never roll for a debit.
    IMPORTANT CONSTRAINT: The new expiry MUST be selected from the valid_expiries list (between 30 and 50 DTE). Never select an expiry > 50 DTE or an unlisted date. If no valid expiry offers a net credit >= $0.25 per contract ($25 total), output HOLD_CALL_POSITION instead of rolling beyond 50 DTE or locking shares for pennies.

  RULE 6 — HOLD (Default, all other conditions):
    → Execute HOLD_CALL_POSITION.
    REASON: None of the above conditions met. Time decay working in our favour. Hold.
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
  - "option_chain": A combined list of puts across ALL valid expiries (30-50 DTE).
    Each row contains: expiry (YYYYMMDD), dte, strike, bid, ask, mid, delta, iv.
    You MUST compare across expiry rows and choose the single best strike+expiry combination.

  DTE SELECTION RULE (NEW SELLS — SELL_NEW_PUT / SELL_NEW_CALL):
  - You have full visibility of all available expiries in the 30-50 DTE window.
  - Default preference: select the expiry CLOSEST to 45 DTE from the valid_expiries list.
  - Exception: If VIX >= 25 (high fear), prefer a longer DTE (45-50) for maximum premium and safety buffer.
  - Exception: If day_classification == QUIET_DAY and VIX < 15, a shorter DTE (30-36) is acceptable to cycle faster.
  - EARNINGS RULE: NEVER select an expiry that falls AFTER the next earnings date.
    If the closest-to-45 expiry is after earnings, step back to the last safe expiry before earnings.

  DTE SELECTION RULE (ROLLS — ROLL_PUT / ROLL_CALL):
  - MANDATORY: You MUST select from valid_expiries list ONLY (between 30 and 50 DTE). No other dates.
  - Select the expiry with the LOWEST DTE in valid_expiries that still allows a net credit >= $0.25.
  - This is almost always the nearest available monthly expiry (30-36 DTE range).
  - If NO expiry in valid_expiries allows net credit >= $0.25 -> Output HOLD instead of rolling.
  - NEVER select DTE > 50 for any roll under any circumstance.
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
        "expiry_to_trade": "string — REQUIRED when decision is SELL_NEW_PUT or SELL_NEW_CALL. Must be the EXACT 'expiry' value (YYYYMMDD format, no dashes) copied from the option_chain row you selected. Example: '20260711'",
        "dte_seen": "integer or null",
        "premium_to_collect": "float or null",
        "reason": "string (precise reason containing specific numbers, must state the chosen DTE and expiry)"
      }
    ]
  }
</output_schema_override>
