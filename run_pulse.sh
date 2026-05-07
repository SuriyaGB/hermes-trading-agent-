#!/bin/bash
# Master Pulse Script - AAPL Wheel Trading
# Root Cause Fix Applied: Buffered Pipe Extermination

PROJECT_ROOT=$(dirname "$(realpath "$0")")
export HERMES_HOME=$PROJECT_ROOT/.hermes
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT/.hermes/plugins

# Dependency Injection
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source $PROJECT_ROOT/.venv/bin/activate
fi

# Secret Environment Loading
set -a
if [ -f "$HERMES_HOME/.env" ]; then
    source $HERMES_HOME/.env
else
    echo "ERROR: .hermes/.env not found."
    exit 1
fi
set +a

# The Pulse Execution (Solid Tube Version)
TMP_OUTPUT=$PROJECT_ROOT/.hermes_output.log
echo "[LOG] Starting Pulse..." > $TMP_OUTPUT

hermes chat --query "MISSION: Run AAPL Wheel Pulse.
1. OBSERVE: Run 'python3 get_ibkr_analysis.py' (in current dir) and capture the JSON output.
2. THINK: Apply AGENTS.md rules strictly.
3. DECIDE: Output the final required JSON object. Output NOTHING ELSE." \
>> $TMP_OUTPUT 2>&1

# Extract and Execute
echo "[LOG] Extracting JSON from $TMP_OUTPUT..."
cat $TMP_OUTPUT | python3 -u $PROJECT_ROOT/executor.py
