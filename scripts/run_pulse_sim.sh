#!/bin/bash
# run_pulse_sim.sh — Hermes Institutional Execution Pulse (Hardened v2)
# ─────────────────────────────────────────────────────────────────────
# Fixes applied:
#   BUG #2 (A): Market hours gate — skip outside 13:30-20:00 UTC
#   BUG #4 (C): Skill file existence check before any Python runs
#   BUG #1:     Switched from sim_executor → executor (state-write version)
# ─────────────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# ─────────────────────────────────────────────
# GATE 1 — BUG #4 FIX: Critical File Check
# If required rule files are missing, abort NOW
# before wasting any API calls.
# ─────────────────────────────────────────────
if [ ! -f ".hermes/AGENTS.md" ]; then
    echo "[CRITICAL] .hermes/AGENTS.md is MISSING. Aborting pulse."
    exit 1
fi

if [ ! -f ".hermes/skills/SKILL_AAPL.md" ]; then
    echo "[CRITICAL] .hermes/skills/SKILL_AAPL.md is MISSING. Aborting pulse."
    exit 1
fi

# ─────────────────────────────────────────────
# GATE 2 — BUG #2 FIX: Market Hours Check (UTC)
# US Options Market: 13:30 to 20:00 UTC
# Outside this window → skip, don't waste API calls
# ─────────────────────────────────────────────
CURRENT_HOUR=$(date -u +%H)
CURRENT_MIN=$(date -u +%M)
CURRENT_TOTAL_MINS=$(( CURRENT_HOUR * 60 + CURRENT_MIN ))

MARKET_OPEN_MINS=$(( 13 * 60 + 30 ))   # 13:30 UTC
MARKET_CLOSE_MINS=$(( 20 * 60 + 0 ))   # 20:00 UTC

if [ "$CURRENT_TOTAL_MINS" -lt "$MARKET_OPEN_MINS" ] || [ "$CURRENT_TOTAL_MINS" -ge "$MARKET_CLOSE_MINS" ]; then
    CURRENT_UTC=$(date -u +"%H:%M UTC")
    echo "[HERMES] Market closed at ${CURRENT_UTC}. US options: 13:30-20:00 UTC. Skipping pulse."
    exit 0
fi

echo "[HERMES] Market open at $(date -u +'%H:%M UTC'). Running pulse..."

# ─────────────────────────────────────────────
# Environment & Authentication Injection
# ─────────────────────────────────────────────
source .venv/bin/activate
if [ -f ".hermes/.env" ]; then
    set -a
    source .hermes/.env
    set +a
fi

export SIM_MODE=1
export FORCE_PULSE=1

# ─────────────────────────────────────────────
# PHASE 1: The Eye (Market Data Fetching)
# ─────────────────────────────────────────────
echo "[SIM] Phase 1: Running Eye..."
EYE_DATA=$(python3 -m core.get_ibkr_analysis)

# Save Eye Data to shared cache (executor.py reads from here)
echo "$EYE_DATA" > .eye_cache.json
echo "[SIM] Eye data cached to .eye_cache.json"

# ─────────────────────────────────────────────
# PHASE 2: The Brain (AI Decision)
# ─────────────────────────────────────────────
echo "[SIM] Phase 2: Calling Brain..."
BRAIN_DECISION=$(echo "$EYE_DATA" | python3 -m core.call_brain_direct)
BRAIN_EXIT=$?

# If brain aborted (e.g. skill file failed in Python too), stop here
if [ $BRAIN_EXIT -ne 0 ]; then
    echo "[CRITICAL] Brain exited with code $BRAIN_EXIT. Pulse aborted."
    exit 1
fi

# ─────────────────────────────────────────────
# PHASE 3: The Executor (State Write + Reporting)
# BUG #1 FIX: Now calls executor.py (not sim_executor.py)
# executor.py handles: state-write, yield gate, Telegram
# ─────────────────────────────────────────────
echo "[SIM] Phase 3: Executing Decision..."
echo "$BRAIN_DECISION" | python3 -m core.executor

echo "[SIM] Pulse Complete."
