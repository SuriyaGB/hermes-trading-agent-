#!/bin/bash
PROJECT_ROOT=$(dirname "$(dirname "$(realpath "$0")")")
export HERMES_HOME=$PROJECT_ROOT/.hermes
export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT

# 1. Load Environment (The Magic Sauce)
set -a
[ -f "$HERMES_HOME/.env" ] && source $HERMES_HOME/.env
set +a

# 2. Activate Venv
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source $PROJECT_ROOT/.venv/bin/activate
fi

# 3. Run Assistant
python3 $PROJECT_ROOT/core/assistant.py "$@"
