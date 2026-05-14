import os
import sys
import json
import urllib.request
from pathlib import Path


def call_openai(eye_data):
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return {"error": "Missing API Key"}

    url = "https://api.openai.com/v1/chat/completions"

    # Load AGENTS + SYMBOL SKILL RULES
    try:
        root = Path(__file__).parent.parent

        # Load General Constitution
        with open(root / '.hermes' / 'AGENTS.md', "r") as f:
            agents_rules = f.read()

        # Load AAPL Specialist Rules
        with open(root / '.hermes' / 'skills' / 'SKILL_AAPL.md', "r") as f:
            skill_rules = f.read()

        combined_rules = (
            f"{agents_rules}\n\n"
            f"LOADED SYMBOL SKILL:\n"
            f"{skill_rules}"
        )

    except Exception as e:
        # BUG #4 FIX: Never silently continue with fallback rules.
        error_msg = (
            f"🚨 HERMES CRITICAL\n"
            f"SKILL_AAPL.md failed to load.\n"
            f"Error: {e}\n"
            f"Pulse aborted. Check VPS file paths."
        )
        print(f"[CRITICAL] {error_msg}", flush=True)
        # Attempt emergency Telegram
        try:
            import urllib.parse as urlparse
            token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            if token and chat_id and "your_" not in token:
                t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = urlparse.urlencode({"chat_id": chat_id, "text": error_msg}).encode("utf-8")
                req  = urllib.request.Request(t_url, data=payload)
                with urllib.request.urlopen(req, timeout=10):
                    pass
        except Exception:
            pass  # If Telegram also fails, we still abort
        sys.exit(1)

    prompt = f"""
MISSION: Run AAPL Wheel Pulse.

OBSERVATION DATA:
{eye_data}

RULES & STRATEGY:
{combined_rules}

DECIDE: Output ONLY the final JSON object. No other text.
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the WHEEL-AGENT. "
                    "You output strictly valid JSON."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(
                response.read().decode("utf-8")
            )

            return res_data['choices'][0]['message']['content']

    except Exception as e:
        # Concern 9 fix: Do NOT return a bare error string.
        # Exit with code 1 so run_pulse_sim.sh aborts the pulse cleanly.
        error_msg = (
            f"🚨 HERMES: OpenAI API failed.\n"
            f"Error: {e}\n"
            f"Pulse aborted. Check API key and billing."
        )
        print(f"[CRITICAL] {error_msg}", flush=True)

        # FIX 2: Send Telegram alert on OpenAI failure
        try:
            import urllib.parse as urlparse
            token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            if token and chat_id and "your_" not in token:
                t_url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = urlparse.urlencode({"chat_id": chat_id, "text": error_msg}).encode("utf-8")
                req  = urllib.request.Request(t_url, data=payload)
                with urllib.request.urlopen(req, timeout=10):
                    pass
        except Exception as t_err:
            print(f"[DEBUG] Telegram alert failure: {t_err}")

        sys.exit(1)


if __name__ == "__main__":
    eye_input = sys.stdin.read()

    decision = call_openai(eye_input)

    print(decision)
