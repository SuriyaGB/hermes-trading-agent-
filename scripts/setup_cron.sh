#!/bin/bash
# setup_cron.sh — Final Automation Proof (IST)
# ─────────────────────────────────────────────────────────────

PROJECT_DIR="/home/gbrithp2/Documents/krc_Lab/Live_Trade"
SCRIPT_PATH="$PROJECT_DIR/run_pulse_sim.sh"
LOG_PATH="$PROJECT_DIR/pulse_cron.log"

# Clean existing cron
crontab -r 2>/dev/null

# 1. SPECIAL TRIGGER: 20:15 IST (8:15 PM) — THE FINAL PROOF
(crontab -l 2>/dev/null; echo "15 20 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

# 2. 20:30 IST (8:30 PM) — Regular Session
(crontab -l 2>/dev/null; echo "30 20 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

# 3. 21:00-23:30 IST — Main Session (Every 30 mins)
(crontab -l 2>/dev/null; echo "0,30 21-23 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

# 4. 00:00-01:00 IST — Late Session
(crontab -l 2>/dev/null; echo "0,30 0-1 * * 2-6 $SCRIPT_PATH >> $LOG_PATH 2>&1") | crontab -

echo "[INSTITUTIONAL] Final Proof Triggered for 20:15 IST (in 5 minutes). Watch the group."
