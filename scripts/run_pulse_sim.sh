#!/bin/bash
# run_pulse_sim.sh — The Institutional Execution Pulse (Authenticated & Hardened)
# ─────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 1. Environment & Authentication Injection
source .venv/bin/activate
if [ -f ".hermes/.env" ]; then
    set -a
    source .hermes/.env
    set +a
fi

export SIM_MODE=1
export FORCE_PULSE=1

# 2. PHASE 1: The Eye (Data Fetching)
echo "[SIM] Phase 1: Running Eye..."
EYE_DATA=$(python3 -m core.get_ibkr_analysis)

# NEW: Save Eye Data to cache for the Executor (Unbreakable Reporting)
echo "$EYE_DATA" > .eye_cache.json

# 3. PHASE 2: The Brain (Direct Private Line)
echo "[SIM] Phase 4: Calling Brain..."
# Using the direct private line to ensure 100% authentication and zero noise
BRAIN_DECISION=$(echo "$EYE_DATA" | python3 -m core.call_brain_direct)

# 4. PHASE 3: The Executor (Action & Reporting)
echo "[SIM] Phase 5: Executing Decision..."
echo "$BRAIN_DECISION" | python3 -m core.sim_executor
