#!/bin/bash
# setup_cron.sh — Schedule Hermes 30-minute pulse (Delayed Data Optimized)
PROJECT_ROOT=$(dirname "$(realpath "$0")")
SCRIPT_PATH="$PROJECT_ROOT/run_pulse_sim.sh"
LOG_PATH="$PROJECT_ROOT/pulse_cron.log"

# Cron Schedule (IST):
# Optimized for 15-minute delayed data (Starts at 19:30 instead of 19:00)
# Entry 1: 19:30 shift
CRON1="30 19 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1"
# Entry 2: 20:00 - 23:30 shift
CRON2="0,30 20-23 * * 1-5 $SCRIPT_PATH >> $LOG_PATH 2>&1"
# Entry 3: 00:00 - 01:30 shift (overflow)
CRON3="0,30 0-1 * * 2-6 $SCRIPT_PATH >> $LOG_PATH 2>&1"

# Create temp crontab
crontab -l > mycron 2>/dev/null
sed -i "/run_pulse_sim.sh/d" mycron

# Add new entries
echo "$CRON1" >> mycron
echo "$CRON2" >> mycron
echo "$CRON3" >> mycron

# Install new crontab
crontab mycron
rm mycron

echo "[SIM] Cron setup complete. Pulse scheduled for 19:30 - 01:30 IST (Delayed Data Buffer Active)."
echo "[SIM] Logs: $LOG_PATH"
