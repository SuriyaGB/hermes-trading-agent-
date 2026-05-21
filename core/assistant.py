import os
import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# CONFIG - Universal Pathing
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'data' / 'hermes_brain.db'
PORTFOLIO_PATH = PROJECT_ROOT / 'data' / 'portfolio.json'
STATE_FILE = PROJECT_ROOT / 'data' / 'trade_state.json'
ENV_FILE = PROJECT_ROOT / '.hermes' / '.env'

# Load Credentials
load_dotenv(ENV_FILE)

def get_current_context():
    """Fetches the 'Now' data from JSONs."""
    context = {}
    try:
        with open(PORTFOLIO_PATH, 'r') as f:
            context['portfolio'] = json.load(f)
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                context['state'] = json.load(f)
    except Exception as e:
        context['error'] = f"Context fetch error: {e}"
    return context

def query_memory(limit=5):
    """Fetches the 'Past' data from SQLite."""
    memory = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM pulse_history ORDER BY id DESC LIMIT {limit}").fetchall()
        for row in rows:
            memory.append(dict(row))
        conn.close()
    except Exception as e:
        print(f"[ERROR] Database access failed: {e}")
    return memory

def query_history_summary():
    """Queries aggregated database stats to give the AI full awareness of the inception date and lifetime metrics."""
    summary = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Calculate total pulses, start date, and last update date
        row = conn.execute("SELECT count(*) as total_pulses, min(timestamp) as start_date, max(timestamp) as end_date FROM pulse_history").fetchone()
        if row:
            summary = {
                "total_pulses": row["total_pulses"],
                "inception_date": row["start_date"],
                "last_pulse_date": row["end_date"]
            }
            
        # Count distinct decision types to show distribution of holds, rolls, sells
        decisions = conn.execute("SELECT ai_decision, count(*) as count FROM pulse_history GROUP BY ai_decision").fetchall()
        summary['decision_distribution'] = {r['ai_decision']: r['count'] for r in decisions}
        
        # Fetch details of the very first pulse (inception details)
        first_row = conn.execute("SELECT timestamp, aapl_price, vix_level, earnings_days, ai_decision, ai_reasoning, ai_override, override_reason FROM pulse_history ORDER BY id ASC LIMIT 1").fetchone()
        if first_row:
            summary['first_pulse_details'] = dict(first_row)
        
        conn.close()
    except Exception as e:
        print(f"[ERROR] Database summary access failed: {e}")
        summary = {"error": str(e)}
    return summary

def ask_hermes(query: str):
    """The main interface for the Interactive Assistant."""
    
    # 1. Gather Data
    current = get_current_context()
    history = query_memory(limit=10)             # Last 10 pulses for micro-context
    history_summary = query_history_summary()     # Full summary stats for macro-context
    
    # 2. Build the System Prompt (The Intelligence)
    prompt = f"""
    SYSTEM: You are the Hermes Trading Assistant, a highly intelligent financial AI.
    You have access to the bot's internal 'Database Memory' and 'Live Portfolio'.
    
    [CONTEXT: LIVE PORTFOLIO]
    {json.dumps(current, indent=2)}
    
    [CONTEXT: DATABASE HISTORY SUMMARY]
    {json.dumps(history_summary, indent=2)}
    
    [CONTEXT: RECENT DATABASE MEMORY (LAST 10 PULSES)]
    {json.dumps(history, indent=2)}
    
    USER QUESTION: {query}
    
    CRITICAL INSTRUCTIONS:
    1. NEVER output raw JSON, database IDs, or code blocks.
    2. Answer the user's question directly in a conversational, human-like manner.
    3. Use the [CONTEXT] purely as your internal memory to find the truth. 
    4. If the user asks about 'news', format the headlines clearly using bullet points. Do not cut them off.
    5. Be professional, concise, and insightful. 
    """
    
    # 3. Call the LLM
    try:
        result = subprocess.run(
            ['hermes', 'chat', '--query', prompt],
            capture_output=True,
            text=True,
            check=True,
            env=os.environ # Pass the API keys!
        )
        
        # 4. Parse the clean output (Strip out the echoed prompt and CLI UI)
        output = result.stdout.strip()
        if "╭─ ⚕ Hermes" in output and "╰─" in output:
            lines = output.split('\n')
            clean_lines = []
            in_hermes = False
            for line in lines:
                if "╭─ ⚕ Hermes" in line:
                    in_hermes = True
                    continue
                if "╰─" in line and in_hermes:
                    break
                if in_hermes and not line.startswith("DEBUG:"):
                    clean_lines.append(line.strip())
            return "\n".join(clean_lines).strip()
            
        return output
    except Exception as e:
        return f"❌ Assistant Brain Error: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 assistant.py 'Your Question'")
    else:
        user_query = sys.argv[1]
        print(ask_hermes(user_query))
