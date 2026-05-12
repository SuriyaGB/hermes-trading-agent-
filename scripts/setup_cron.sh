#!/bin/bash
# setup_cron.sh — Market Hours Automation (IST)
# ─────────────────────────────────────────────────────────────

# Automatically resolve the project directory relative to this script
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_PATH="$PROJECT_DIR/scripts/run_pulse_sim.sh"
LOG_PATH="$PROJECT_DIR/logs/pulse_cron.log"

# Clean existing cron
crontab -r 2>/dev/null

# 1. 19:30 IST (7:30 PM) — Market Open
(crontab -l 2>/dev/null; echo "30 19 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

# 2. 20:00 to 23:30 IST (8:00 PM to 11:30 PM) — Main Session (Mon-Fri)
(crontab -l 2>/dev/null; echo "0,30 20-23 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

# 3. 00:00 to 01:30 IST (12:00 AM to 1:30 AM) — Late Session (Tue-Sat)
# (This is the NEXT calendar day, so days are 2-6 instead of 1-5)
(crontab -l 2>/dev/null; echo "0,30 0-1 * * 2-6 $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

echo "[INSTITUTIONAL] Cron schedule activated. Pulses will fire every 30 mins from 7:30 PM to 1:30 AM (IST)."
