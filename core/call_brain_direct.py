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
        combined_rules = (
            f"Follow wheel strategy rules. "
            f"(Skill loading failed: {e})"
        )

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
        return f"Error: {e}"


if __name__ == "__main__":
    eye_input = sys.stdin.read()

    decision = call_openai(eye_input)

    print(decision)
