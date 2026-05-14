import os
import sys
import json
import asyncio
import math
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# CONFIG - Universal Pathing
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
PORTFOLIO_PATH = DATA_DIR / 'portfolio.json'

# Global Warning Tracker
WARNINGS = []

def add_warning(msg: str):
    print(f"[WARNING] {msg}")
    WARNINGS.append(msg)

# ─────────────────────────────────────────────
# ADVANCED MATH ENGINE (Institutional)
# ─────────────────────────────────────────────
def get_risk_free_rate():
    try:
        ticker = yf.Ticker('^IRX')
        price = ticker.fast_info.last_price
        if price and price > 0: return price / 100
    except: pass
    return 0.053 # Fallback 5.3%

def get_vix_sigma():
    try:
        ticker = yf.Ticker('^VIX')
        price = ticker.fast_info.last_price
        if price and price > 0: return price / 100
    except: pass
    return 0.18 # Fallback 18%

def black_scholes_price(S, K, T, r, sigma, option_type='put'):
    if T <= 0: return max(0, K - S) if option_type == 'put' else max(0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == 'call':
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def solve_iv(market_price, S, K, T, r, option_type='put'):
    sigma_fallback = get_vix_sigma()
    if market_price <= 0.01 or T <= 0: return sigma_fallback
    def objective(sigma):
        return black_scholes_price(S, K, T, r, sigma, option_type) - market_price
    try:
        # Search for IV between 1% and 500%
        return brentq(objective, 1e-6, 5.0)
    except:
        return sigma_fallback

def calculate_delta(S, K, T, r, iv, option_type='put'):
    if iv <= 0 or T <= 0: return -0.5 if option_type == 'put' else 0.5
    d1 = (np.log(S / K) + (r + 0.5 * iv ** 2) * T) / (iv * np.sqrt(T))
    if option_type == 'call':
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1

# ─────────────────────────────────────────────
# DATA FETCHING
# ─────────────────────────────────────────────
def load_portfolio():
    try:
        with open(PORTFOLIO_PATH, 'r') as f: return json.load(f)
    except: 
        add_warning("Portfolio file missing.")
        return {"cash": 250000.0, "positions": []}

def get_vix() -> float:
    try: 
        vix = yf.Ticker("^VIX").fast_info['lastPrice']
        return round(float(vix), 2)
    except:
        add_warning("VIX fetch failed. Using fallback 17.5")
        return 17.5

def get_earnings_days(symbol: str = "AAPL") -> int:
    try:
        ticker = yf.Ticker(symbol)
        calendar = ticker.calendar
        if calendar is not None and 'Earnings Date' in calendar:
            next_earnings = calendar['Earnings Date'][0]
            if hasattr(next_earnings, 'date'): next_earnings = next_earnings.date()
            days = (next_earnings - datetime.now().date()).days
            return max(0, days)
        return 45
    except:
        return 45

def get_recent_news(symbol: str = "AAPL") -> List[str]:
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        headlines = []
        for n in news[:3]:
            if 'content' in n and 'title' in n['content']:
                headlines.append(n['content']['title'])
        return headlines if headlines else ["No recent news headlines."]
    except:
        return ["News fetch failed."]

async def get_yf_option_chain(spot: float, held_strike: float = None) -> Dict[str, Any]:
    result = {"option_chain": [], "chosen_expiry": None, "chosen_dte": None}
    ticker = yf.Ticker("AAPL")
    expiries = ticker.options
    today = datetime.now().date()
    
    target_expiry = None
    for exp in expiries:
        exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
        dte = (exp_date - today).days
        # BUG #7 FIX: MIN_DTE for new entry = 30 days (aligned with SKILL_AAPL.md).
        # SKILL_AAPL PREFERRED DTE = 35 days. MIN_DTE rule = 21 (close trigger).
        # We must never OPEN a new position at 22-28 DTE — that's too close to Gamma zone.
        # Floor set to 30 to ensure we always open with at least 1 month of theta.
        if 30 <= dte <= 50:
            target_expiry, target_dte = exp, dte
            break
    
    if not target_expiry: return result
    
    result["chosen_expiry"] = target_expiry.replace('-', '')
    result["chosen_dte"] = target_dte
    
    try:
        chain = ticker.option_chain(target_expiry).puts
        vix = get_vix()
        r = get_risk_free_rate()
        T = target_dte / 365.25
        
        all_rows = []
        for _, row in chain.iterrows():
            strike = float(row['strike'])
            bid, ask = float(row['bid']), float(row['ask'])
            mid = round((bid + ask) / 2, 2)
            if mid <= 0.0: mid = float(row['lastPrice'])
            
            # IMPROVED IV DETECTION
            iv_raw = float(row['impliedVolatility'])
            if iv_raw < 0.01 or abs(iv_raw - 0.500005) < 0.0001:
                # Use Math Engine to solve for real IV
                iv = solve_iv(mid, spot, strike, T, r, 'put')
            else:
                iv = iv_raw

            delta = calculate_delta(spot, strike, T, r, iv, 'put')
            
            all_rows.append({
                "strike": strike, "bid": bid, "ask": ask, "mid": mid,
                "delta": round(delta, 4), "iv": round(iv * 100, 1)
            })
        
        sorted_by_dist = sorted(all_rows, key=lambda x: abs(x['strike'] - spot))
        atm_strikes = [x['strike'] for x in sorted_by_dist[:20]]

        filtered = []
        for row in all_rows:
            if row['strike'] in atm_strikes or (held_strike and abs(row['strike'] - held_strike) < 0.1):
                filtered.append(row)
        result["option_chain"] = sorted(filtered, key=lambda x: x['strike'], reverse=True)

        # ── BUG #2 FIX: Detect closed market via all-zero bids ──────────────
        zero_bid_count = sum(1 for row in all_rows if row.get('bid', 0) == 0.0)
        if zero_bid_count == len(all_rows) and len(all_rows) > 0:
            result["market_open"]          = False
            result["market_closed_reason"] = "all_bids_zero"
            add_warning(
                f"MARKET CLOSED: all {zero_bid_count} options have bid=0.0. "
                f"Using stale lastPrice. No orders can be placed."
            )
        else:
            result["market_open"] = True

    except Exception as e:
        add_warning(f"Chain error: {e}")

    return result

async def fetch_analysis_data() -> Dict[str, Any]:
    data = {"account_status": "CASH_ONLY", "price_seen": 0.0, "vix_seen": 17.0, "iv_current": "N/A", "option_chain": [], "warnings": []}
    ticker = yf.Ticker('AAPL')
    data["price_seen"] = round(float(ticker.fast_info['lastPrice']), 2)
    data["vix_seen"] = get_vix()
    data["earnings_days"] = get_earnings_days("AAPL")
    data["recent_news"] = get_recent_news("AAPL")
    
    portfolio = load_portfolio()
    held_strike = None
    for p in portfolio.get("positions", []):
        if p.get("type") == "Option":
            held_strike = p.get("strike")
            data["account_status"] = "CSP_ACTIVE"
            data["strike_held"] = held_strike
            
    chain_result = await get_yf_option_chain(data["price_seen"], held_strike)
    data.update(chain_result)
    
    # Final IV enrichment from ATM
    if data["option_chain"]:
        atm = sorted(data["option_chain"], key=lambda x: abs(x['strike'] - data["price_seen"]))[0]
        data["iv_current"] = atm['iv']
    
    data["warnings"] = WARNINGS
    return data

if __name__ == "__main__":
    print(json.dumps(asyncio.run(fetch_analysis_data()), indent=2))
