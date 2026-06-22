# 🏛️ Hermes — AAPL Wheel Strategy AI Trading Agent

> An institutional-grade, autonomous AI trading agent that executes the **Options Wheel Strategy** on AAPL. It uses **GPT-4o** as its decision brain, a **Local Mathematical Simulation Engine (yfinance + Black-Scholes)** as its execution arm, and a hardened **10-Token State Machine** with Hard Shields as its safety backbone.

---

## 📌 Table of Contents

- [The Tri-Force Architecture](#️-the-tri-force-architecture-trader--chatbot--dashboard)
- [How It Is Wired Together (The Data Flow)](#-how-it-is-wired-together-the-data-flow)
- [The 5-Page Institutional Dashboard](#-the-5-page-institutional-dashboard)
- [Project Structure](#-project-structure)
- [The Strategic Brain](#-the-strategic-brain)
- [The 10 Decision Tokens](#-the-10-decision-tokens)
- [The 4 Account States](#-the-4-account-states)
- [The Wheel Cycle](#-the-wheel-cycle)
- [The Hard Shields](#️-the-hard-shields)
- [Setup Instructions](#-setup-instructions)
- [Running the Bot](#️-running-the-bot)
- [Security](#-security)

---

Hermes is a fully autonomous AI trading agent that:

- Watches AAPL every pulse during US market hours.
- Reads live **Price, VIX, Implied Volatility, Delta, DTE, and News**.
- Sends all data to **GPT-4o** alongside its strategic rulebook.
- GPT-4o outputs **exactly one** of 10 allowed Decision Tokens.
- The bot organically simulates trades and calculates Options Greeks locally without needing a broker connection.
- Logs every decision permanently to `.hermes/MEMORY.md`.
- Sends a real-time alert to **Telegram**.

**This is NOT a simple script.** It is a state-machine-driven system where the AI is constrained by a "Constitution" of hard rules — it cannot make arbitrary decisions.

---

## ⚙️ The Tri-Force Architecture (Trader + Chatbot + Dashboard)

Hermes operates using three completely independent services that never interfere with each other, connected ONLY by an immutable SQLite database (`hermes_brain.db`) and secure JSON state files. The golden rule: Only the Trading Engine writes data; everything else is Read-Only.

### Service A: The Trading Engine (The Pulse)
Runs automatically every 30 minutes via Cron. Wakes up, executes the math, saves the history, sends a push alert, and dies to save RAM.

```text
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │  THE EYE    │───▶│  THE BRAIN  │───▶│  THE HAND   │───▶│ THE MEMORY  │
  │ Fetches:    │    │ GPT-4o      │    │ Validates   │    │ executes    │
  │ Price, VIX, │    │ reads rule- │    │ shields,    │    │ SQLite DB + │
  │ IV, News    │    │ books       │    │ executes    │    │ JSONs       │
  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Service B: The Interactive Assistant (The Chatbot)
Runs 24/7 in the background (`telegram_listener.py`). It does not trade. It acts as a RAG analyst, waiting for you to ask questions about your portfolio or past decisions.

```text
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │ THE LISTENER│───▶│ THE ANALYST │───▶│ THE DATA    │───▶│ THE REPLY   │
  │ Catches     │    │ assistant.py│    │ Reads JSONs │    │ Telegram    │
  │ User Query  │    │ formats     │    │ & SQLite DB │    │ texts back  │
  │ 24/7        │    │ strict RAG  │    │ History     │    │ instantly   │
  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Service C: The Web Dashboard (Vercel Frontend + VPS API)
A completely **stateless** 5-page Next.js dashboard hosted on Vercel. It connects to a FastAPI running on your VPS. It reads your VPS files and streams live execution data and Options Greeks directly to your browser without risking state corruption.

```text
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │ THE BROWSER │───▶│ VERCEL UI   │───▶│ VPS API     │───▶│ THE DATA    │
  │ Next.js UI  │    │ HTTP Request│    │ core/api.py │    │ Reads JSONs │
  │ Live Charts │    │ Port 8000   │    │ 24/7 PM2    │    │ & SQLite DB │
  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## 🔌 How It Is Wired Together (The Data Flow)

The genius of this system is its completely decoupled memory structure. It uses an asynchronous, file-based data pipeline.

```text
  [MARKET OPEN]                                               [USER DEVICE]
        │                                                          │
        ▼                                                          ▼
┌───────────────┐     WRITES TO      ┌──────────────────┐    ┌─────────────┐
│  CRON JOB     │ ─────────────────▶ │  THE BRAIN       │ ◀──│  VERCEL     │
│ (Bash Script) │                    │ (VPS Hard Drive) │    │  DASHBOARD  │
└───────────────┘                    │                  │    └─────────────┘
        │                            │ hermes_brain.db  │          │
        ▼                            │ portfolio.json   │          ▼
┌───────────────┐     READS FROM     │ trade_state.json │    ┌─────────────┐
│ TELEGRAM BOT  │ ◀───────────────── │ trades_log.csv   │ ◀──│  FAST API   │
│ (PM2 24/7)    │                    └──────────────────┘    │ (PM2 24/7)  │
└───────────────┘                                            └─────────────┘
```
**The Absolute Golden Rule:** The Cron Job (The Trader) is the ONLY process with permission to write or edit data. The Telegram Bot and the Vercel FastAPI are strictly **READ-ONLY**. This architectural separation guarantees that you will never accidentally corrupt your portfolio state or execute a rogue trade simply by opening the dashboard or asking the bot a question.

---

## 💻 The 5-Page Institutional Dashboard

The Next.js frontend (`frontend/`) automatically builds these 5 web pages on the fly based entirely on your VPS data feeds:

1. **Command Centre (`/`)**: Live HUD showing your Current Phase, Delta/VIX Guards, and the latest AI reasoning log.
2. **Income Tracker (`/income`)**: A dynamic graph mapping your true Account Balance Growth and premium collection jumps.
3. **Pulse History (`/history`)**: A terminal-style audit table of every historical AI decision, color-coded by action.
4. **Market View (`/market`)**: Dual-axis analytics charting macro forces (AAPL vs VIX) and Options Greeks (Delta & DTE).
5. **Bot Health (`/health`)**: System telemetry monitoring your Python server connection, SQLite row count, and Earnings Blackout shields.

---
## 📁 Project Structure

```text
hermes-trading-agent/
│
├── 📂 core/                               ← The "Internal Organs" (Python Engine)
│   ├── sim_executor.py                    ← Simulation executor (paper trading)
│   ├── executor.py                        ← Live executor (real IBKR trades)
│   ├── api.py                             ← FastAPI Bridge (Serves data to Vercel)
│   ├── get_ibkr_analysis.py               ← Market data fetcher (The Eye)
│   ├── database.py                        ← SQLite Manager (The Institutional Memory)
│   ├── assistant.py                       ← RAG Smart Analyst (The Voice)
│   └── telegram_listener.py               ← 24/7 Chatbot Poller (The Ears)
│
├── 📂 frontend/                           ← The Next.js Web Dashboard
│   ├── src/app/page.js                    ← Command Centre (Live HUD)
│   ├── src/app/income/page.js             ← Income Tracker (Balance Growth)
│   ├── src/app/history/page.js            ← Pulse History (Audit Table)
│   ├── src/app/market/page.js             ← Market View (AAPL vs VIX/Greeks)
│   └── src/app/health/page.js             ← Bot Health & Shield Telemetry
│
├── 📂 scripts/                            ← The "Hands" (Operational Tools)
│   ├── run_scenarios.py                   ← Edge-case safety testing suite
│   ├── run_pulse_sim.sh                   ← Manually run one simulation pulse
│   ├── run_pulse.sh                       ← Manually run one live pulse
│   ├── setup_cron.sh                      ← Enable 24/7 automated schedule
│   ├── stop_cron.sh                       ← Stop the automated schedule
│   └── assistant.sh                       ← Hardened shell wrapper for the AI Assistant
│
├── 📂 tests/                              ← The "Proving Grounds" (Mock Data)
│   ├── mock_payloads/                     ← 25 Edge-case scenario JSON files
│   └── .scenario_backup/                  ← Auto-generated backups during tests
│
├── 📂 data/                               ← The "Money Memory" (NOT on GitHub)
│   ├── portfolio.json                     ← Current cash, shares, P&L
│   ├── trade_state.json                   ← Current Wheel phase
│   ├── trades_log.csv                     ← Full history of every trade
│   └── archive/                           ← Pulse snapshots
│
├── 📂 docs/                               ← Strategy Documentation
│   ├── AAPL_WHEEL_AGENT_DOCUMENTATION.md  ← Master strategy document
│   ├── HERMES_AAPL_SYSTEM_DOCUMENTATION.md← System architecture overview
│   └── decision_tokens_infographic.png    ← Visual strategy map
│
├── 📂 logs/                               ← Execution History (NOT on GitHub)
│   └── pulse_cron.log                     ← Background cron output
│
├── 📂 .hermes/                            ← 🧠 THE STRATEGIC BRAIN (The Heart)
│   ├── AGENTS.md                          ← Master Constitution (Rules & Shields)
│   ├── MEMORY.md                          ← Persistent decision history
│   └── skills/
│       └── SKILL_AAPL.md                  ← AAPL-specific Wheel strategy logic
│
├── .gitignore                             ← Security shield
├── .env                                   ← API Keys (NEVER on GitHub)
├── requirements.txt                       ← Python dependencies
└── README.md                              ← This file
```

---

## 🧠 The Strategic Brain

> **The Python code is just the engine. These two files ARE the intelligence of Hermes.**

### `.hermes/AGENTS.md` — The Master Constitution

This is the **Law** of the entire system. Every pulse, GPT-4o reads this file completely before making any decision. It defines:

- The **4 Account States** the bot can be in.
- The **10 Decision Tokens** it is allowed to output.
- The **Hard Shields** that override ALL AI logic if triggered.
- The **output JSON schema** the AI must follow every single pulse.

### `.hermes/skills/SKILL_AAPL.md` — The AAPL Wheel Playbook

This file contains the **AAPL-specific parameters**:

- **Delta Targets:** 0.25 to 0.28 (Normal) | 0.18 to 0.22 (High IV).
- **DTE Window:** 30 to 45 days (nearest monthly expiry).
- **Profit Target Triggers:** Close at **50%** of max premium collected.
- **The 3-Bucket News Framework:** Categorizes headlines into *Black Swan, Negative Nudge, or Noise.*

---

## 🎯 The 10 Decision Tokens

The AI Brain outputs **exactly one** of these 10 tokens per pulse.

| # | Token | When It Fires |
|---|---|---|
| 1 | `SELL_NEW_PUT` | All conditions met — open a new Cash-Secured Put |
| 2 | `SELL_NEW_CALL` | Shares assigned — open a new Covered Call |
| 3 | `HOLD_PUT_POSITION` | CSP open, theta decaying — do nothing |
| 4 | `HOLD_CALL_POSITION` | CC open, theta decaying — do nothing |
| 5 | `HOLD_ASSIGNED_EQUITY` | Shares assigned, waiting to sell a Call |
| 6 | `CLOSE_FOR_PROFIT` | P&L reached **50%** of max premium (per Skill File) |
| 7 | `CLOSE_FOR_LOSS` | Buy back cheap Call to redeploy at lower strike |
| 8 | `ROLL_PUT` | Delta too high — close Put, open new one for net credit |
| 9 | `ROLL_CALL` | Stock rallying to strike — roll Call higher for net credit |
| 10 | `ABORT_DUE_TO_RISK` | Emergency — VIX > 40 or existential news event |

---

## 📊 The 4 Account States

Stored in `data/trade_state.json`:

1.  **CASH_ONLY:** No open positions. Find a Put to sell.
2.  **CSP_ACTIVE:** Cash-Secured Put is open. Theta burning.
3.  **SHARES_ASSIGNED:** 100 shares in account. No Call sold yet.
4.  **CC_ACTIVE:** Covered Call open against 100 shares.

---

## 🎡 The Wheel Cycle

```text
┌─────────────────────────────────────────────────────────────────┐
│                    THE INFINITE INCOME WHEEL                     │
└─────────────────────────────────────────────────────────────────┘

  Phase 1: SELL CASH-SECURED PUT
  ──────────────────────────────
  Target: Delta 0.20–0.25 | DTE 30–45 days | Strike 6%+ below spot
  Minimum premium: 1.0% of strike price
  Collect premium as income upfront

    If AAPL stays above strike:
      Put expires worthless → keep 100% premium → restart Phase 1 ♻️

    If AAPL drops below strike:
      100 shares assigned at strike price → move to Phase 2 ↓

  Phase 2: SELL COVERED CALL
  ──────────────────────────
  Target: Delta 0.30–0.35 | DTE 30–45 days
  Strike MUST be above Adjusted Cost Basis
  Adjusted Cost Basis = Assignment Strike − Total Put Premium Collected
  Collect premium as income upfront

    If AAPL stays below strike:
      Call expires worthless → keep premium → sell another Call ♻️

    If AAPL rises above strike:
      Shares called away at profit → restart Phase 1 ♻️
```

---

## 🛡️ The Hard Shields

### Shield 1 — VIX Zone Guard
*   **VIX < 13:** No new positions. Premium too cheap.
*   **VIX 13 to 29.9:** IDEAL zone. All decisions allowed.
*   **VIX 30 to 40:** SELL_NEW_PUT/CALL BLOCKED. Manage existing only.
*   **VIX > 40:** ABORT_DUE_TO_RISK fires immediately.

### Shield 2 — Earnings Blackout
*   **Earnings > 14 days away:** Normal operation.
*   **Earnings 7 to 14 days away:** No new opens.
*   **Earnings < 7 days away:** Evaluate all positions for early profit closure.

### Shield 3 — Non-Negotiable Hard Rules
1. Never sell a Call below Adjusted Cost Basis.
2. Never roll for a net debit — credit only.
3. Never close a losing Put (Price drop = Assignment coming).
4. Always include live numbers (Price, Delta, VIX) in the reason field.

---

## 🚀 Setup Instructions

### Prerequisites

```bash
# Python 3.11+
python3 --version
```

### Step 1 — Clone the Repository & Setup Virtual Environment

```bash
git clone https://github.com/SuriyaGB/hermes-trading-agent-.git
cd hermes-trading-agent-

# Create and activate virtual environment
python3 -m venv krc_venv
source krc_venv/bin/activate

# Install all required packages
pip install -r requirements.txt
```

### Step 2 — Create Your .env File

```bash
# Create the .env file (NEVER push this to GitHub)
touch .hermes/.env
```

Add these values to `.hermes/.env`:

```env
OPENAI_API_KEY=sk-your-openai-key-here
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id
# IBKR Keys not required for local testing
```

### Step 3 — Seed Your Portfolio (CRITICAL)

```bash
# Create your starting portfolio state
# This is the ONE-TIME manual setup
# After this, the VPS manages it forever

cat > data/portfolio.json << 'JSON'
{
  "cash_balance": 50000.00,
  "shares_held": 0,
  "avg_cost_basis": 0.00,
  "total_premium_collected": 0.00,
  "positions": []
}
JSON
```

### Step 4 — Seed Your Trade State

```bash
cat > data/trade_state.json << 'JSON'
{
  "current_phase": "CASH_ONLY",
  "last_action": null,
  "last_updated": null,
  "earnings_blackout_active": false
}
JSON
```

### Step 5 — Verify Setup

```bash
# Test one pulse manually before enabling cron
bash scripts/run_pulse_sim.sh
```

**How to verify it worked:**
1. **Telegram:** You should have received a real-time push notification from the bot.
2. **Database:** Open `data/trades_log.csv` and ensure a new row was added.
3. **Dashboard:** Open your Vercel Dashboard (or local `http://localhost:3000/history`). The pulse should appear instantly in the Pulse History audit log.

***

## 🧪 Testing & Auditing (Zero-Risk Local Testing)

When you clone this repository, you do **not** have access to the live VPS database. Your local `data/` folder will be empty. 

To prove that the Python safety guardrails work and to see the UI in action, we built a comprehensive test suite of 25 edge-case market scenarios.

**The Golden Rule of Testing:**
The test scripts automatically backup your local data, run the scenario, and then instantly restore your clean local data. They will **never** touch or break the live VPS trading environment.

### 1. Run Tests (Zero API Cost)
To run all 25 safety guardrail tests without calling the OpenAI API:
```bash
PYTHONPATH=. python3 scripts/run_scenarios.py all
```
*This uses pre-scripted mock AI decisions to prove that the Python Executor blocks dangerous trades.*

### 2. View a Test in the Local UI 
By default, the test script automatically populates your UI dashboard with the mock data from the test you just ran. You don't need any special flags.
```bash
# E.g., Run Test 5 (Emergency Exit)
PYTHONPATH=. python3 scripts/run_scenarios.py 5
```
Now, refresh your local UI (`http://localhost:3000`) and it will display exactly what happened in the test. If you want to clean up your data folder afterward and restore it to its previous state:
```bash
PYTHONPATH=. python3 scripts/run_scenarios.py 1 --restore
```

### 3. Test with the Real AI (`--live`)
If you want to see if GPT-4o actually makes the right decision on its own (costs API credits):
```bash
set -a; source .hermes/.env; set +a
PYTHONPATH=. python3 scripts/run_scenarios.py 4 --live
```
*The script is smart enough to handle situations where the real AI natively guesses the correct safe action!*

### 4. Live Market Testing
During US market hours, the eye data fetchers (`core/market_data.py`) can pull real-time AAPL prices and VIX from Yahoo Finance (free, no broker needed). You can run a manual simulation pulse (`scripts/run_pulse_sim.sh`) to see exactly what the AI would do right now based on original, live market data.

***

## ▶️ Running the Bot (Local vs VPS)

You have two entirely different ways to run this system depending on your current phase.

### 💻 1. Running Locally (On Your Laptop / PC)

When testing on your personal computer, you do NOT use PM2 or Cron. You must run the servers manually using two separate terminal windows.

**Terminal 1 (The Python API):**
```bash
# Activate virtual environment
source .venv/bin/activate
# Run the API in development mode
uvicorn core.api:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 (The Next.js Dashboard):**
```bash
cd frontend
# Install node modules if you haven't yet
npm install
# Start the React development server
npm run dev
```
*(You can now view your dashboard at http://localhost:3000)*

---

### ☁️ 2. Running on a VPS (Production Master Deployment)

When you move this code to your Virtual Private Server (VPS), you must use Process Managers (PM2) so the servers stay awake forever when you close the SSH terminal.

**Start the 24/7 FastAPI Server (For Vercel):**
```bash
# Start the FastAPI (Bridge for Vercel)
pm2 start "source .venv/bin/activate && uvicorn core.api:app --host 0.0.0.0 --port 8000" --name hermes-api
pm2 save

# Important: Make sure your VPS firewall allows port 8000!
sudo ufw allow 8000
```

**Start the 24/7 Interactive Telegram Chatbot:**
```bash
# Runs the RAG Telegram assistant permanently
pm2 start core/telegram_listener.py --interpreter .venv/bin/python --name hermes-telegram
pm2 save
```

**Deploying the Dashboard to Vercel:**
1. Push this repository to GitHub.
2. Log into [Vercel.com](https://vercel.com) and import the repository.
3. Set the **Root Directory** to `frontend/`.
4. Click Deploy. Vercel will build the 5-page React application and give you a live URL.

**Arm the Autonomous Cron Job Trader:**
```bash
# Sets up the cron jobs for market hours
bash scripts/setup_cron.sh

# Verify cron is running
crontab -l
```

> **Cron Timing Architecture (IST):** 
> The `setup_cron.sh` configures the trader to run exclusively during US Market hours (7:30 PM to 1:30 AM IST). 
> Because this spans past midnight, it is intelligently split into two separate cron jobs to avoid system date conflicts:
> - **Job 1:** Runs every 30 minutes from 7:30 PM up to 11:30 PM (Monday-Friday).
> - **Job 2:** Runs every 30 minutes from 12:00 AM up to 1:30 AM (Tuesday-Saturday). 
> *(Note: 12:00 AM is midnight, which technically marks the start of the next calendar day. That is why Job 2 runs on Tue-Sat to cover the Monday-Friday US market sessions).*

**Stop the Automated Schedule:**
```bash
bash scripts/stop_cron.sh
```

### Check Live Logs on VPS

```bash
# Watch the bot's cron execution in real time
tail -f logs/pulse_cron.log

# See last 50 decisions directly from the markdown memory
tail -50 .hermes/MEMORY.md
```

***

## 🛡️ Safety Shields

The bot has **5 hardened safety rules** that override the AI if it makes a dangerous decision:

```text
Shield 1 — Cost Basis Protection
  Never sell a Covered Call below your adjusted cost basis.
  Prevents locking in a guaranteed loss.

Shield 2 — Earnings Blackout (The 14/7 Rule)
  No new positions 14 days before earnings.
  Emergency evaluation 7 days before earnings.
  Prevents getting destroyed by earnings volatility.

Shield 3 — Illegal State Transition
  Cannot sell a Put while already holding a Put.
  Cannot sell a Call without owning 100 shares.
  Prevents overlapping positions.

Shield 4 — VIX Spike & Floor Guard
  No new positions when VIX < 13 (Premium too cheap).
  No new opens when VIX > 30 (Market too volatile).
  ABORT_DUE_TO_RISK fires immediately if VIX > 40.

Shield 5 — IV Rank Filter
  Only sell options when IV > 30%.
  Ensures you collect enough premium to be worthwhile.
```

***

## 🔐 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ Yes | Your OpenAI API key for GPT-4o |
| `TELEGRAM_BOT_TOKEN` | ✅ Yes | Your Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | ✅ Yes | Your Telegram chat ID |
| `IBKR_HOST` | Live only | IBKR TWS host (usually 127.0.0.1) |
| `IBKR_PORT` | Live only | IBKR TWS port (7497 paper, 7496 live) |
| `IBKR_CLIENT_ID` | Live only | IBKR client connection ID |

***

***

## 🔒 Security

These files are **permanently excluded from GitHub** to protect your money and security:

```text
data/portfolio.json      ← Your account balance
data/trade_state.json    ← Your open position state
data/trades_log.csv      ← Your trading history
data/hermes_brain.db     ← Your SQLite pulse and memory database
.hermes/.env             ← ALL API keys
.hermes/MEMORY.md        ← Your decision history
logs/                    ← All log files
__pycache__/             ← Python cache
*.pyc                    ← Compiled Python files
```

***

