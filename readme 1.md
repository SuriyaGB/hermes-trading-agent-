# 🏛️ Hermes — AAPL Wheel Strategy AI Trading Agent

> An institutional-grade, autonomous AI trading agent that executes the **Options Wheel Strategy** on AAPL. It uses **GPT-4o** as its decision brain, a **Local Mathematical Simulation Engine (yfinance + Black-Scholes)** as its execution arm, and a hardened **10-Token State Machine** with Hard Shields as its safety backbone.

---

## 📌 Table of Contents

- [What Is This?](#what-is-this)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [The Strategic Brain](#the-strategic-brain)
- [The 10 Decision Tokens](#the-10-decision-tokens)
- [The 4 Account States](#the-4-account-states)
- [The Hard Shields](#the-hard-shields)
- [The Wheel Cycle](#the-wheel-cycle)
- [Setup Instructions](#setup-instructions)
- [Running the Bot](#running-the-bot)
- [Security](#security)

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

## ⚙️ The Dual-Microservice Architecture

Hermes operates using two completely independent services that never interfere with each other, connected only by an immutable SQLite database (`hermes_brain.db`).

### Service A: The Trading Engine (The Pulse)
Runs automatically every 30 minutes via Cron. Wakes up, executes the math, saves the history, sends a push alert, and dies to save RAM.

```text
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │  THE EYE    │───▶│  THE BRAIN  │───▶│  THE HAND   │───▶│ THE MEMORY  │
  │ Fetches:    │    │ GPT-4o      │    │ Validates   │    │ Writes to   │
  │ Price, VIX, │    │ reads rule- │    │ shields,    │    │ SQLite DB + │
  │ IV, News    │    │ books       │    │ executes    │    │ JSONs       │
  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Service B: The Interactive Assistant (The Chatbot)
Runs 24/7 in the background (`telegram_listener.py`). It does not trade. It acts as a RAG (Retrieval-Augmented Generation) analyst, waiting for you to ask questions about your portfolio or past decisions.

```text
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │ THE LISTENER│───▶│ THE ANALYST │───▶│ THE DATA    │───▶│ THE REPLY   │
  │ Catches     │    │ assistant.py│    │ Reads JSONs │    │ Telegram    │
  │ User Query  │    │ formats     │    │ & SQLite DB │    │ texts back  │
  │ 24/7        │    │ strict RAG  │    │ History     │    │ instantly   │
  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## 📁 Project Structure

```text
hermes-trading-agent/
│
├── 📂 core/                               ← The "Internal Organs" (Python Engine)
│   ├── sim_executor.py                    ← Simulation executor (paper trading)
│   ├── executor.py                        ← Live executor (real IBKR trades)
│   ├── get_ibkr_analysis.py               ← Market data fetcher (The Eye)
│   ├── database.py                        ← SQLite Manager (The Institutional Memory)
│   ├── assistant.py                       ← RAG Smart Analyst (The Voice)
│   └── telegram_listener.py               ← 24/7 Chatbot Poller (The Ears)
│
├── 📂 scripts/                            ← The "Hands" (Operational Tools)
│   ├── run_pulse_sim.sh                   ← Manually run one simulation pulse
│   ├── run_pulse.sh                       ← Manually run one live pulse
│   ├── setup_cron.sh                      ← Enable 24/7 automated schedule
│   ├── stop_cron.sh                       ← Stop the automated schedule
│   └── assistant.sh                       ← Hardened shell wrapper for the AI Assistant
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

# Required packages
pip install openai yfinance pandas python-dotenv requests ib_insync
```

### Step 1 — Clone the Repository

```bash
git clone https://github.com/ravichandranai712-droid/hermes-trading-agent.git
cd hermes-trading-agent
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
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
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

***

## ▶️ Running the Bot

### Manual Single Pulse (Simulation)

```bash
bash scripts/run_pulse_sim.sh
```

### Manual Single Pulse (Live Trading)

```bash
bash scripts/run_pulse.sh
```

### Enable 24/7 Automated Schedule

```bash
# Sets up cron jobs for market hours
bash scripts/setup_cron.sh

# Verify cron is running
crontab -l
```

### Stop the Automated Schedule

```bash
bash scripts/stop_cron.sh
```

### Enable the Interactive Telegram Chatbot

To enable 24/7 two-way communication with your bot, run the listener in the background using PM2 or Nohup:

```bash
# Using standard Python background process
nohup bash -c "source .venv/bin/activate && python3 core/telegram_listener.py" &

# Or using PM2 (Recommended for VPS)
pm2 start core/telegram_listener.py --interpreter .venv/bin/python --name hermes-listener
pm2 save
```

### Check Live Logs

```bash
# Watch the bot in real time
tail -f logs/pulse_cron.log

# See last 50 decisions
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

