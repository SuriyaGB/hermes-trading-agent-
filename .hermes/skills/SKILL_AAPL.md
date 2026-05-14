<skill_file_metadata>
  symbol: AAPL
  strategy: Wheel
  version: 4.2
  last_hardened: 2026-05-14
</skill_file_metadata>

<instruction_set_aapl>

  <instruction id="IV_VOLATILITY_ANALYSIS">
    REASON: Live IV is the 'Fear Gauge'. Use it to price risk.
    RULES:
      - iv_current > 30%: Elevated fear. Good premium harvest zone. Sell puts with confidence at standard deltas.
      - iv_current 20-30%: Normal market. Proceed with standard wheel logic.
      - iv_current < 20%: Low fear. Cheap premium. Wait for better entry unless MA200 support is clear.
      - iv_current == 'UNAVAILABLE': Treat as Normal (20-30% zone).
      - CRITICAL: iv_current > 45% AND earnings_days < 14: DANGER. (Blocked by Python Gate).
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

  # ─────────────────────────────────────────────────────────────────────────
  # ELITE HYBRID NEWS FRAMEWORK
  # ─────────────────────────────────────────────────────────────────────────
  5. HISTORICAL GROUNDING: 
     Remember: AAPL has survived 40+ years of probes, fines, and crashes. 
     You are a calm professional. Do not overreact to speculative headlines.
     
  6. IV-FIRST FILTER:
     Check iv_current BEFORE reading headlines.
     - If iv_current is high (>30%), market fear is already priced in. 
     - High IV + Bad News = Opportunity to sell expensive fear at wider strikes.
     
  7. THE 3-BUCKET DECISION:
     Analyze the 6 raw headlines and categorize into one of three buckets:
     
     - BUCKET A: BLACK SWAN (Existential threat to AAPL itself)
       Criteria: Confirmed Bankruptcy, SEC Trading Halt, or Fraud Conviction.
       Action: Output ABORT_DUE_TO_RISK.
       
     - BUCKET B: NEGATIVE NUDGE (Risky but survivable)
       Criteria: DOJ probes, regulatory fines, misses, or product recalls.
       Action: RE-PRICE RISK. Widen strike selection (lower delta).
       CRITICAL CONSTRAINT: The new strike MUST still meet the 1.0% premium yield
       requirement (min_premium). If no such strike exists → WAIT_FOR_ENTRY.

     - BUCKET C: NOISE (Standard market activity)
       Criteria: Product launches, analyst upgrades, routine lawsuits.
       Action: IGNORE. Execute standard wheel strategy.
</brain_reference_aapl>

# ═══════════════════════════════════════════════════════════════
# SECTION C — MANDATORY YIELD GATE (The Iron Math Law)
# This is not a guideline. This is a mathematical checkpoint.
# Python will block you if you fail it. Do not even try to bypass.
# ═══════════════════════════════════════════════════════════════

<mandatory_yield_check>
  BEFORE outputting SELL_NEW_PUT, you MUST run this calculation:

  STEP 1 — Calculate premium yield:
    premium_yield_pct = (premium_to_collect / strike_to_trade) × 100

  STEP 2 — Compare to floor:
    If premium_yield_pct >= 1.0% → SELL is ALLOWED. Proceed.
    If premium_yield_pct <  1.0% → SELL is FORBIDDEN. Output WAIT_FOR_ENTRY.

  WORKED EXAMPLES (study these — they match yesterday's failures):

    ❌ WRONG (what you did yesterday — every single pulse):
       Strike $285, premium $2.40
       yield = (2.40 / 285) × 100 = 0.84%
       0.84% < 1.0% → MUST output WAIT_FOR_ENTRY, NOT SELL_NEW_PUT.

    ❌ WRONG:
       Strike $275, premium $1.47
       yield = (1.47 / 275) × 100 = 0.53%
       0.53% < 1.0% → WAIT_FOR_ENTRY required.

    ✅ CORRECT:
       Strike $285, premium $3.10
       yield = (3.10 / 285) × 100 = 1.09%
       1.09% >= 1.0% → SELL_NEW_PUT is permitted.

    ✅ CORRECT:
       Strike $275, premium $2.90
       yield = (2.90 / 275) × 100 = 1.05%
       1.05% >= 1.0% → SELL_NEW_PUT is permitted.

  INCLUDE in your reason field:
    "premium_yield = (X / Y) × 100 = Z%"
    This is required so the Python gate can audit your math.

  REMEMBER: Python will independently verify this calculation.
  If you output SELL_NEW_PUT with yield < 1.0%, Python will
  override your decision to WAIT_FOR_ENTRY and send a Telegram
  alert flagging your failure. Avoid triggering this gate.
</mandatory_yield_check>

<!-- END OF SKILL_AAPL.md | Version 4.1 | TIMELLESS INSTRUCTIONS -->
