#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# run_pulse_sim.sh — Hermes AAPL Wheel Agent: SIMULATION PULSE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# THIS IS THE SIMULATION LANE. It differs from run_pulse.sh in only 2 ways:
#
#   DIFFERENCE 1: Sets SIM_MODE=1
#     → Tells get_ibkr_analysis.py to read portfolio from portfolio.json
#       instead of fetching positions from IBKR TWS.
#     → AAPL price, VIX, Greeks, DTE still fetched from IBKR TWS (real data).
#
#   DIFFERENCE 2: Pipes Brain output to sim_executor.py instead of executor.py
#     → sim_executor.py handles all trades locally (no IBKR orders placed).
#     → Writes results to portfolio.json, trade_state.json, trade_log.csv.
#
# DO NOT TOUCH run_pulse.sh or executor.py — they are the live lane.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT=$(dirname "$(realpath "$0")")
export HERMES_HOME=$PROJECT_ROOT/.hermes
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT/.hermes/plugins

# ── Market Hours Safety Net (IST: 19:00 - 01:30) ─────────────────────────
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
    # For testing: if FORCE_PULSE=1 is set, bypass this check
    if [[ "$FORCE_PULSE" != "1" ]]; then
        exit 0
    fi
    echo "[SIM] FORCE_PULSE detected. Proceeding anyway."
fi

# ── SIMULATION FLAG — the only new line vs run_pulse.sh ─────────────────
export SIM_MODE=1

echo "[SIM] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[SIM] Hermes AAPL Wheel Agent — SIMULATION MODE"
echo "[SIM] Portfolio source: portfolio.json (local)"
echo "[SIM] Market data source: IBKR TWS (real live data)"
echo "[SIM] Order execution: sim_executor.py (local, no IBKR orders)"
echo "[SIM] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Activate virtual environment ─────────────────────────────────────────
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source $PROJECT_ROOT/.venv/bin/activate
fi

# ── Load secrets from .hermes/.env ───────────────────────────────────────
set -a
if [ -f "$HERMES_HOME/.env" ]; then
    source $HERMES_HOME/.env
else
    echo "[SIM] ERROR: .hermes/.env not found. IBKR market data connection will fail."
    exit 1
fi
set +a

# ── The Pulse Execution (Solid Tube Version) ─────────────────────────────
# Saves Brain output to a SEPARATE log file so it never overwrites the
# live lane's .hermes_output.log — both lanes can run independently.
TMP_OUTPUT=$PROJECT_ROOT/.hermes_sim_output.log
echo "[SIM] Starting pulse — saving Brain output to .hermes_sim_output.log"
echo "[SIM] $(date '+%Y-%m-%d %H:%M:%S')" > $TMP_OUTPUT

hermes chat --query "MISSION: Run AAPL Wheel Pulse.
1. OBSERVE: Run 'python3 get_ibkr_analysis.py' (in current dir) and capture the JSON output.
2. THINK: Apply AGENTS.md rules. If CASH_ONLY, look at 'option_chain'. 
   Select a Put strike where Delta is ~0.25 and DTE is 21-45 days. 
3. DECIDE: Output the final required JSON. Output NOTHING ELSE.
   Include 'strike_held', 'delta_seen', and 'dte_seen' in your output for the selected strike." \
>> $TMP_OUTPUT 2>&1

# ── Extract JSON and pipe to sim_executor.py ─────────────────────────────
# Note: grep "{" (without ^ anchor) is intentional — Hermes indents the JSON
# inside a styled box with leading spaces, so "^{" would miss it entirely.
echo "[SIM] Extracting decision JSON from Brain output..."
cat $TMP_OUTPUT | python3 -u $PROJECT_ROOT/sim_executor.py
