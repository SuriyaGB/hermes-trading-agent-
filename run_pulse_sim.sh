#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# run_pulse_sim.sh — Hermes AAPL Wheel Agent: SEQUENTIAL SIMULATION PULSE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# PHASES:
#   1. THE EYE:   Sense the world (get_ibkr_analysis.py)
#   2. THE GATE:  Circuit Breaker (Deterministic Safety)
#   3. THE MEMORY: Recall past experiences (hermes memory search)
#   4. THE BRAIN: Logical Decision (Hermes LLM)
#   5. THE ACT:   Execution & Audit (sim_executor.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT=$(dirname "$(realpath "$0")")
export HERMES_HOME=$PROJECT_ROOT/.hermes
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT/.hermes/plugins
# Absolute path to hermes binary — bypasses cron's stripped PATH entirely
HERMES_BIN=/home/gbrithp2/.local/bin/hermes

# ── Market Hours Safety Net (IST: 19:30 - 01:30) ─────────────────────────
CURRENT_TIME=$(date +%H%M)
CURRENT_DAY=$(date +%u) # 1=Mon, 7=Sun
IS_OPEN=0
if [[ "$CURRENT_DAY" -ge 1 && "$CURRENT_DAY" -le 5 && "$CURRENT_TIME" -ge 1930 ]]; then
    IS_OPEN=1
elif [[ "$CURRENT_DAY" -ge 2 && "$CURRENT_DAY" -le 6 && "$CURRENT_TIME" -lt 0130 ]]; then
    IS_OPEN=1
fi

if [[ "$IS_OPEN" -eq 0 ]]; then
    echo "[SIM] Market closed. Skipping pulse (IST: $CURRENT_TIME, Day: $CURRENT_DAY)."
    if [[ "$FORCE_PULSE" != "1" ]]; then
        exit 0
    fi
    echo "[SIM] FORCE_PULSE detected. Proceeding anyway."
fi

# ── Activate virtual environment ─────────────────────────────────────────
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source $PROJECT_ROOT/.venv/bin/activate
fi

# ── Load secrets from .hermes/.env ───────────────────────────────────────
set -a
if [ -f "$HERMES_HOME/.env" ]; then
    source $HERMES_HOME/.env
else
    echo "[SIM] ERROR: .hermes/.env not found."
    exit 1
fi
set +a

# ── BLOCK 1: THE EYE (Sense the World) ───────────────────────────────────
export SIM_MODE=1
echo "[SIM] Phase 1: Running Eye (get_ibkr_analysis.py)..."
EYE_JSON=$(python3 $PROJECT_ROOT/get_ibkr_analysis.py)
if [ -z "$EYE_JSON" ]; then
    echo "[FATAL] Eye returned empty data. Pulse aborted."
    exit 1
fi

# ── BLOCK 2: THE CIRCUIT BREAKER (Deterministic Safety) ─────────────────
echo "[SIM] Phase 2: Evaluating Circuit Breaker thresholds..."
DECISION=$(echo "$EYE_JSON" | python3 -c "
import json, sys

data = json.load(sys.stdin)
phase = data.get('account_status', 'CASH_ONLY')
is_opening = phase in ['CASH_ONLY', 'SHARES_ASSIGNED']

price = data.get('price_seen', 0)
vix   = data.get('vix_seen', -1)
earn  = data.get('earnings_days', None)

# ── DATA INTEGRITY
if not price or price <= 0:
    print('HOLD_PUT_POSITION (Price Null)')
    sys.exit(0)

if vix < 0:
    print('HOLD_PUT_POSITION (VIX Null)')
    sys.exit(0)

# ── FULL CRISIS (VIX > 45)
if vix > 45:
    print('HOLD_PUT_POSITION (VIX Crisis)')
    sys.exit(0)

# ── NEW ENTRY GATES
if is_opening:
    # VIX elevated
    if vix > 35:
        print('HOLD_PUT_POSITION (VIX Elevated)')
        sys.exit(0)

    # Earnings blackout window
    if earn is not None and earn <= 7:
        print('HOLD_PUT_POSITION (Earnings Blackout)')
        sys.exit(0)

    # Earnings data missing
    if earn is None:
        print('HOLD_PUT_POSITION (Earnings Missing)')
        sys.exit(0)

# ── EYE PRE-FILLED DECISION (IV Gate)
eye_decision = data.get('decision')
if eye_decision and eye_decision != 'PROCEED':
    print(eye_decision)
    sys.exit(0)

print('PROCEED')
")

if [ "$DECISION" != "PROCEED" ]; then
    echo "[CIRCUIT BREAKER] $DECISION — skipping Brain."
    # Build a minimal Brain-format JSON when CB fires
    CB_OUTPUT=$(echo "$EYE_JSON" | python3 -c "
import json, sys
eye = json.load(sys.stdin)
output = {
  'decision': '$DECISION',
  'reason': 'circuit_breaker',
  'strike_held': None,
  'chosen_expiry': None,
  'delta_seen': None,
  'chosen_dte': None,
  'mid': None,
  'iv30_rank': eye.get('iv30_rank'),
  'vix_seen': eye.get('vix_seen'),
  'earnings_days': eye.get('earnings_days'),
  'price_seen': eye.get('price_seen')
}
print(json.dumps(output))
")
    echo "$CB_OUTPUT" | python3 $PROJECT_ROOT/sim_executor.py 2>/dev/null
    exit 0
fi

# ── BLOCK 3: THE MEMORY (Adaptive Context) ──────────────────────────────
echo "[SIM] Phase 3: Retrieving past memories from MEMORY.md..."
MEMORY_CONTEXT=$(tail -n 50 $HERMES_HOME/MEMORY.md 2>/dev/null || echo "No prior memory found.")
export HERMES_MEMORY_CONTEXT="$MEMORY_CONTEXT"

# ── BLOCK 4: THE BRAIN (Logical Decision) ────────────────────────────────
echo "[SIM] Phase 4: Calling Brain (Hermes LLM)..."
TMP_OUTPUT=$PROJECT_ROOT/.hermes_sim_output.log
echo "[SIM] $(date '+%Y-%m-%d %H:%M:%S')" > $TMP_OUTPUT

$HERMES_BIN chat --skills SKILL_AAPL --query "MISSION: Run AAPL Wheel Pulse.
ADAPTIVE CONTEXT (Past Lessons):
$HERMES_MEMORY_CONTEXT

CURRENT DATA (The Eye):
$EYE_JSON

INSTRUCTIONS:
1. THINK: Apply AGENTS.md and SKILL_AAPL.md rules to the CURRENT DATA.
2. REFLECT: Compare live data to Past Lessons.
3. DECIDE: Output the final required JSON. Output NOTHING ELSE." \
>> $TMP_OUTPUT 2>&1

# ── BLOCK 5: THE ACT (Execution & Audit) ────────────────────────────────
echo "[SIM] Phase 5: Executing Decision..."
echo "[SIM] Extracting decision JSON from Brain output..."
cat $TMP_OUTPUT | python3 -u $PROJECT_ROOT/sim_executor.py
