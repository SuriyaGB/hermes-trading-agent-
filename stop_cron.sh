#!/bin/bash
# stop_cron.sh — Remove Hermes pulse schedule
crontab -l > mycron 2>/dev/null
sed -i "/run_pulse_sim.sh/d" mycron
crontab mycron
rm mycron
echo "[SIM] Cron job removed. Autonomous pulse stopped."
