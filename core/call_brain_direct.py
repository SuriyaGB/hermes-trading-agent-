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
    
    # Read AGENTS.md for the rules
    try:
        rule_path = Path(__file__).parent.parent / '.hermes' / 'AGENTS.md'
        with open(rule_path, "r") as f:
            agents_rules = f.read()
    except:
        agents_rules = "Follow wheel strategy rules."

    prompt = f"""
MISSION: Run AAPL Wheel Pulse.
OBSERVATION DATA:
{eye_data}

RULES:
{agents_rules}

DECIDE: Output ONLY the final JSON object. No other text.
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You are the WHEEL-AGENT. You output strictly valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    eye_input = sys.stdin.read()
    decision = call_openai(eye_input)
    print(decision)
