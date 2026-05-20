#!/bin/bash
# setup_cron.sh — Market Hours Automation (IST)
# ─────────────────────────────────────────────────────────────

# Automatically resolve the project directory relative to this script
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_PATH="$PROJECT_DIR/scripts/run_pulse_sim.sh"
LOG_PATH="$PROJECT_DIR/logs/pulse_cron.log"

# 1. Get existing crontab entries, filtering out only the lines containing our scripts
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -v -E "run_pulse_sim.sh|run_pulse.sh" || true)

# 2. Write back the existing cron jobs + our updated Hermes market schedule
(
  if [ -n "$EXISTING_CRON" ]; then
    echo "$EXISTING_CRON"
  fi
  echo "30 19 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1"
  echo "0,30 20-23 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1"
  echo "0,30 0-1 * * 2-6 $SCRIPT_PATH >> $LOG_PATH 2>&1"
) | crontab -

echo "[INSTITUTIONAL] Cron schedule updated. Pulses will fire every 30 mins from 7:30 PM to 1:30 AM (IST)."
