import os
import sys
import json
import asyncio
import math
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Mocking load_portfolio for standalone eye check
def load_portfolio():
    from pathlib import Path
    portfolio_path = Path(__file__).parent.parent / 'data' / 'portfolio.json'
    try:
        with open(portfolio_path, 'r') as f: return json.load(f)
    except: return {"positions": []}

def get_vix() -> float:
    try: return round(float(yf.Ticker("^VIX").fast_info['lastPrice']), 2)
    except: return 17.5

def get_earnings_days(symbol: str = "AAPL") -> int:
    return 90

def get_recent_news(symbol: str = "AAPL") -> List[str]:
    return ["Apple (AAPL) shares gain after Wedbush raises target to $400 on AI optimism"]

def get_delta_fallback(price, strike, dte, vix):
    try:
        if dte <= 0: return 0.0
        t = dte / 365.0
        sigma = vix / 100.0
        d1 = (math.log(price / strike) + (0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
        delta = 0.5 * (1 + math.erf(d1 / math.sqrt(2))) - 1
        return round(delta, 4)
    except: return -0.25

def get_iv_current(symbol: str = "AAPL", spot_price: float = 0.0) -> float | str:
    try:
        ticker = yf.Ticker(symbol)
        exp = ticker.options[0]
        chain = ticker.option_chain(exp).puts
        atm = chain.iloc[(chain['strike'] - spot_price).abs().argsort()[:1]]
        return round(float(atm['impliedVolatility'].iloc[0]) * 100, 1)
    except: return "UNAVAILABLE"

async def get_yf_option_chain(spot: float, held_strike: float = None) -> Dict[str, Any]:
    result = {"option_chain": [], "chosen_expiry": None, "chosen_dte": None}
    ticker = yf.Ticker("AAPL")
    expiries = ticker.options
    today = datetime.now().date()
    
    # Selection logic
    target_expiry = None
    for exp in expiries:
        exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
        dte = (exp_date - today).days
        if 20 <= dte <= 50:
            target_expiry, target_dte = exp, dte
            break
    
    if not target_expiry: return result
    
    result["chosen_expiry"] = target_expiry.replace('-', '')
    result["chosen_dte"] = target_dte
    
    # FETCH CHAIN
    chain = ticker.option_chain(target_expiry).puts
    vix = get_vix()
    
    all_rows = []
    for _, row in chain.iterrows():
        strike = float(row['strike'])
        bid, ask = float(row['bid']), float(row['ask'])
        mid = round((bid + ask) / 2, 2)
        if mid == 0.0: mid = float(row['lastPrice']) # Fallback for illiquid strikes
        
        delta = get_delta_fallback(spot, strike, target_dte, vix)
        all_rows.append({
            "strike": strike, "bid": bid, "ask": ask, "mid": mid,
            "delta": delta, "iv": round(float(row['impliedVolatility'])*100, 1)
        })
    
    # ENSURE HELD STRIKE IS PRESENT
    filtered = []
    sorted_by_dist = sorted(all_rows, key=lambda x: abs(x['strike'] - spot))
    atm_strikes = [x['strike'] for x in sorted_by_dist[:20]] # Increased to 20 for wider coverage
    
    for row in all_rows:
        if row['strike'] in atm_strikes or (held_strike and abs(row['strike'] - held_strike) < 0.1):
            filtered.append(row)
            
    result["option_chain"] = sorted(filtered, key=lambda x: x['strike'], reverse=True)
    return result

async def fetch_ibkr_data() -> Dict[str, Any]:
    data = {"account_status": "CASH_ONLY", "price_seen": 0.0, "vix_seen": 17.0, "iv_current": "N/A", "option_chain": []}
    ticker = yf.Ticker('AAPL')
    data["price_seen"] = round(float(ticker.fast_info['lastPrice']), 2)
    data["vix_seen"] = get_vix()
    data["iv_current"] = get_iv_current("AAPL", data["price_seen"])
    data["recent_news"] = get_recent_news("AAPL")
    data["earnings_days"] = 90
    
    portfolio = load_portfolio()
    held_strike = None
    for p in portfolio.get("positions", []):
        if p.get("type") == "Option":
            held_strike = p.get("strike")
            data["account_status"] = "CSP_ACTIVE"
            data["strike_held"] = held_strike
            
    chain_result = await get_yf_option_chain(data["price_seen"], held_strike)
    data.update(chain_result)
    return data

if __name__ == "__main__":
    print(json.dumps(asyncio.run(fetch_ibkr_data()), indent=2))
