#!/bin/bash
# Hermes Master Pulse - Pure YFinance Mode
# This script runs the Eye -> Brain -> Hand pipeline without IBKR.

PROJECT_ROOT=$(dirname "$(dirname "$(realpath "$0")")")
export HERMES_HOME=$PROJECT_ROOT/.hermes
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT

# 1. Environment & Dependencies
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source $PROJECT_ROOT/.venv/bin/activate
fi

set -a
if [ -f "$HERMES_HOME/.env" ]; then
    source $HERMES_HOME/.env
else
    echo "ERROR: .hermes/.env not found."
    exit 1
fi
set +a

# 2. THE EYE: Fetch Market Data
EYE_DATA=$PROJECT_ROOT/data/.last_eye_data.json
echo "[LOG] 1. The Eye: Fetching AAPL data from YFinance..."
python3 $PROJECT_ROOT/core/get_ibkr_analysis.py > $EYE_DATA

# 3. THE BRAIN: AI Decision
TMP_LOG=$PROJECT_ROOT/.hermes_output.log
EYE_CONTENT=$(cat $EYE_DATA)
echo "[LOG] 2. The Brain: Thinking..."

hermes chat --query "MISSION: Run AAPL Wheel Pulse.
1. CONTEXT: Here is the raw market data JSON: $EYE_CONTENT
2. THINK: Apply AGENTS.md rules strictly to this data.
3. DECIDE: Output a JSON object with EXACTLY two keys:
   - 'decision': (The required action based on AGENTS.md logic)
   - 'reason': (A clear, one-sentence technical explanation of why you made that decision).
Output NOTHING ELSE." \
>> $TMP_LOG 2>&1

# 4. THE HAND: Telegram & Database
echo "[LOG] 3. The Hand: Sending Alerts and Archiving Memory..."
cat $TMP_LOG | python3 -u $PROJECT_ROOT/core/executor.py

echo "[LOG] Pulse Sequence Complete."
