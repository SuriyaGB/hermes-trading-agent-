# SKILL_AAPL.md — AAPL Wheel Strategy Specialist File
# Version: 4.0 (Instruction-Based) | May 2026
# ─────────────────────────────────────────────────────────────────────────────
# ARCHITECTURE: This file uses PRINCIPLES and MATHEMATICAL INSTRUCTIONS.
#   Instead of hardcoded price floors (which go stale), it instructs the 
#   LLM to calculate safe levels at runtime using live market technicals.
#
# OVERRIDE DECLARATION:
#   WHERE THIS FILE CONFLICTS WITH AGENTS.MD, THIS FILE WINS. NO EXCEPTIONS.
# ─────────────────────────────────────────────────────────────────────────────

<symbol_declaration>
  SYMBOL:    AAPL (Apple Inc.)
  STRATEGY:  Cash Secured Put → Assignment → Covered Call (The Wheel)
  INDICATORS PROVIDED: ma_200, ma_50, fifty_two_week_low, fifty_two_week_high
</symbol_declaration>

# ═══════════════════════════════════════════════════════════════
# SECTION 1 — MATHEMATICAL SAFETY PRINCIPLES
# The LLM must calculate these values every pulse using Eye data.
# ═══════════════════════════════════════════════════════════════

<instruction_set_aapl>

  <instruction id="DYNAMIC_STRIKE_FLOOR">
    REASON: Never sell a Put into a falling knife or below institutional support levels.
    CALCULATION:
      - floor_A = fifty_two_week_low × 1.15 (15% cushion above yearly support)
      - floor_B = ma_200 × 0.95 (5% below institutional trend support)
      - min_strike = max(floor_A, floor_B)
    RULE:
      Never select a strike below min_strike. Both input values are provided live by the Eye.
      If all available strikes in the menu are below min_strike, output HOLD_PUT_POSITION.
  </instruction>

  <instruction id="FAIR_PREMIUM_YIELD">
    REASON: Ensure a minimum 1.0% return on the capital at risk per 30-day cycle.
    CALCULATION:
      min_premium = (strike × 100 × 0.01) / 100
    RULE:
      Minimum acceptable premium is 1.0% of the strike price.
      If the best mid price in the menu is below min_premium, output HOLD_PUT_POSITION.
      Example: Strike $270 requires $2.70 minimum premium ($270 per contract).
  </instruction>

  <instruction id="IV_RANK_ADJUSTMENT">
    REASON: Calibrate risk and delta targets based on the current volatility regime.
    RULES:
      - iv30_rank < 25%: Premiums too cheap. Output HOLD_PUT_POSITION (Reason: IV_TOO_LOW).
      - iv30_rank 25% to 60% (NORMAL): Target Delta 0.25 to 0.28.
      - iv30_rank 60% to 85% (ELEVATED): Target Delta 0.20 to 0.25 (Sell further OTM).
      - iv30_rank > 85% AND earnings_days < 21: DANGER. (Blocked by Python Gate).
      - iv30_rank > 85% AND earnings_days >= 21 (HARVEST): Target Delta 0.18 to 0.20.
  </instruction>

  <instruction id="EARNINGS_GAUNTLET">
    REASON: Never hold an option through a binary earnings event.
    RULES:
      - NEVER select an expiry that is AFTER the next earnings_days.
      - If earnings_days < DTE of the best strike: Skip that expiry.
      - If no safe expiry exists in the option_chain: Output HOLD.
  </instruction>

</instruction_set_aapl>

# ═══════════════════════════════════════════════════════════════
# SECTION A — NON-NEGOTIABLE RULES (The Iron Guard)
# These are immutable laws of math and risk. No exceptions.
# ═══════════════════════════════════════════════════════════════

<hard_limits_aapl>
  1. MAX_DELTA: 0.35 for any new position (Institutional safety limit).
  2. MIN_DTE: 21 Days (Time stop). Close any position if DTE < 21 to avoid Gamma.
  3. DIVIDEND_GATE: Never sell a Call within 7 days of ex-dividend date.
  4. EARNINGS_GATE: Expiry DTE must be < earnings_days (Never straddle earnings).
  5. STRIKE_FLOOR: Never select a strike below min_strike = max(floor_A, floor_B).
  6. COST_BASIS: Never sell a Call below Adjusted Cost Basis (Basis = Strike - Premium).
</hard_limits_aapl>

# ═══════════════════════════════════════════════════════════════
# SECTION B — PREFERRED TARGETS (The Strategy Engine)
# Brain should optimise decision within these strategic bands.
# ═══════════════════════════════════════════════════════════════

<brain_reference_aapl>
  1. PREFERRED DTE: Closest available to 35 days (start of theta decay).
  2. PREFERRED DELTA: 0.25 to 0.28 (Normal) | 0.18 to 0.22 (High IV).
  3. PROFIT TARGET: Close early at 50% max premium profit.
  4. ROLL TRIGGER: If Delta exceeds 0.35, evaluate ROLL for credit or Assignment.
  5. NEWS REACTION: If headline mentions 'Criminal probe' or 'Bankruptcy' → ABORT.
</brain_reference_aapl>

<!-- END OF SKILL_AAPL.md | Version 4.0 | TIMELLESS INSTRUCTIONS -->
