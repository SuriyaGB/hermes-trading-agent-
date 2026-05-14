import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

class HermesDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            # Root/data/hermes_brain.db
            self.db_path = Path(__file__).parent.parent / 'data' / 'hermes_brain.db'
        else:
            self.db_path = Path(db_path)
            
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the institutional-grade schema."""
        with self._get_connection() as conn:
            # 1. Pulse History (The Brain's Heartbeat)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pulse_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    aapl_price REAL,
                    vix_level REAL,
                    earnings_days INTEGER,
                    news_summary TEXT,
                    ai_decision TEXT,
                    ai_reasoning TEXT,
                    raw_input_json TEXT,
                    raw_output_json TEXT,
                    ai_override INTEGER DEFAULT 0,
                    override_reason TEXT
                )
            ''')

            # Migration: add columns if upgrading an existing DB
            try:
                conn.execute('ALTER TABLE pulse_history ADD COLUMN ai_override INTEGER DEFAULT 0')
            except Exception:
                pass  # column already exists
            try:
                conn.execute('ALTER TABLE pulse_history ADD COLUMN override_reason TEXT')
            except Exception:
                pass  # column already exists

            # 2. Option Chain Snapshots (The Micro-Data)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS option_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pulse_id INTEGER,
                    expiry_date TEXT,
                    chain_data_json TEXT,
                    FOREIGN KEY (pulse_id) REFERENCES pulse_history (id)
                )
            ''')

            # 3. Trade Ledger (The Accounting)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trade_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pulse_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT,
                    action TEXT,
                    strike REAL,
                    expiry TEXT,
                    price REAL,
                    commission REAL,
                    pnl_realized REAL,
                    FOREIGN KEY (pulse_id) REFERENCES pulse_history (id)
                )
            ''')
            
            # 4. Create Indexes for High-Speed Retrieval
            conn.execute('CREATE INDEX IF NOT EXISTS idx_pulse_time ON pulse_history(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trade_time ON trade_ledger(timestamp)')
            conn.commit()

    def save_pulse(self, eye_data, brain_decision, ai_override=False, override_reason=None):
        """
        Saves a full pulse event including the option chain.
        ai_override: True if Python gate overrode the AI's decision.
        override_reason: Human-readable string explaining why the gate fired.
        """
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO pulse_history (
                    aapl_price, vix_level, earnings_days, news_summary,
                    ai_decision, ai_reasoning, raw_input_json, raw_output_json,
                    ai_override, override_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                eye_data.get('price_seen'),
                eye_data.get('vix_seen'),
                eye_data.get('earnings_days'),
                json.dumps(eye_data.get('recent_news', [])),
                brain_decision.get('decision'),
                brain_decision.get('reason'),
                json.dumps(eye_data),
                json.dumps(brain_decision),
                1 if ai_override else 0,
                override_reason
            ))
            pulse_id = cursor.lastrowid

            # Insert Option Chain Snapshot
            if 'option_chain' in eye_data:
                conn.execute('''
                    INSERT INTO option_snapshots (pulse_id, expiry_date, chain_data_json)
                    VALUES (?, ?, ?)
                ''', (
                    pulse_id,
                    eye_data.get('chosen_expiry', 'N/A'),
                    json.dumps(eye_data.get('option_chain', []))
                ))

            conn.commit()
            return pulse_id

    def save_trade(self, pulse_id, trade_details):
        """
        Saves a trade action to the ledger.
        """
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO trade_ledger (
                    pulse_id, symbol, action, strike, expiry, price, commission, pnl_realized
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pulse_id,
                trade_details.get('symbol', 'AAPL'),
                trade_details.get('action'),
                trade_details.get('strike'),
                trade_details.get('expiry'),
                trade_details.get('price'),
                trade_details.get('commission', 0.0),
                trade_details.get('pnl', 0.0)
            ))
            conn.commit()

    def get_last_reasoning(self):
        """Helper for the Telegram Assistant to see the last thought."""
        with self._get_connection() as conn:
            row = conn.execute('SELECT ai_reasoning FROM pulse_history ORDER BY id DESC LIMIT 1').fetchone()
            return row['ai_reasoning'] if row else "No history found."
