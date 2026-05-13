import sys
import json
import os
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.parse

from core.database import HermesDatabase

PROJECT_ROOT = Path(__file__).parent.parent

STATE_PATH = PROJECT_ROOT / "data" / "trade_state.json"
PORTFOLIO_PATH = PROJECT_ROOT / "data" / "portfolio.json"
EYE_CACHE_PATH = PROJECT_ROOT / ".eye_cache.json"
MEMORY_PATH = PROJECT_ROOT / ".hermes" / "MEMORY.md"


def sim_log(msg):
    print(f"[SIM] {msg}", flush=True)


def extract_decision(raw_input):
    try:
        # CLEAN MARKDOWN JSON WRAPPERS
        raw_input = raw_input.replace("```json", "")
        raw_input = raw_input.replace("```", "")
        raw_input = raw_input.strip()

        data = json.loads(raw_input)

        if isinstance(data, dict) and "decision" in data:
            sim_log(f"Found valid decision: {data['decision']}")
            return data

    except Exception as e:
        sim_log(f"Decision parse failed: {e}")

    return None


def build_memory_summary(decision):
    action = decision.get("decision", "UNKNOWN")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    reason = decision.get("reason", "No reason")

    return (
        f"AAPL Pulse: {action}\n"
        f"Time: {timestamp}\n"
        f"Reason: {reason}"
    )


def main():
    raw_brain_output = sys.stdin.read()

    decision_data = extract_decision(raw_brain_output)

    if not decision_data:
        return

    eye_data = {}

    if EYE_CACHE_PATH.exists():
        try:
            with open(EYE_CACHE_PATH, "r") as f:
                eye_data = json.load(f)

        except Exception:
            pass

    summary = build_memory_summary(decision_data)

    try:
        db = HermesDatabase()

        db.save_pulse(eye_data, decision_data)

        sim_log("Pulse saved to SQLite database.")

    except Exception as e:
        sim_log(f"Database save failed: {e}")

    try:
        with open(MEMORY_PATH, "a") as f:
            f.write(summary + "\n\n")

        sim_log("Memory storage successful.")

    except Exception as e:
        sim_log(f"Memory write failed: {e}")

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"

            data = urllib.parse.urlencode(
                {
                    "chat_id": chat_id,
                    "text": summary
                }
            ).encode("utf-8")

            req = urllib.request.Request(url, data=data)

            with urllib.request.urlopen(req, timeout=10):
                sim_log("Telegram alert sent.")

        except Exception as e:
            sim_log(f"Telegram send failed: {e}")

    sim_log("Pulse Complete.")


if __name__ == "__main__":
    main()
