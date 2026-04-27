import os
import asyncio
import math
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from ib_insync import IB, Stock, Option, Index, util
import yfinance as yf
from datetime import datetime
import requests_cache
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

def get_risk_free_rate():
    try:
        ticker = yf.Ticker('^IRX')
        price = ticker.fast_info.last_price
        if price and price > 0: return price / 100
    except: pass
    return 0.053

def get_vix_sigma():
    try:
        ticker = yf.Ticker('^VIX')
        price = ticker.fast_info.last_price
        if price and price > 0: return price / 100
    except: pass
    return 0.22

# --- LOCAL MATH ENGINE ---
def black_scholes_price(S, K, T, r, sigma, option_type='put'):
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == 'call':
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def calculate_implied_vol(market_price, S, K, T, r, option_type='put'):
    sigma_fallback = get_vix_sigma()
    if market_price <= 0 or T <= 0: return sigma_fallback
    def objective(sigma):
        return black_scholes_price(S, K, T, r, sigma, option_type) - market_price
    try:
        return brentq(objective, 1e-6, 5.0)
    except:
        return sigma_fallback

def calculate_local_delta(S, K, T, r, iv, option_type='put'):
    if iv <= 0 or T <= 0: return 0.0
    d1 = (np.log(S / K) + (r + 0.5 * iv ** 2) * T) / (iv * np.sqrt(T))
    if option_type == 'call':
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1

# Path Management (Root Relative)
BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / 'trade_state.json'
session = requests_cache.CachedSession('hermes_cache', expire_after=300)

def load_financial_state() -> Dict[str, Any]:
    default_state = {
        "current_phase": "CASH_ONLY",
        "current_cycle_put_premium": None,
        "assignment_strike": None,
        "adjusted_cost_basis": None,
        "current_option_strike": None,
        "current_option_expiry": None
    }
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return default_state
    except:
        return default_state

def save_financial_state(state: Dict[str, Any]):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

async def fetch_ibkr_data() -> Dict[str, Any]:
    state = load_financial_state()
    ib = IB()
    data = {
        "account_status": state.get("current_phase", "CASH_ONLY"),
        "price_seen": 0.0,
        "delta_seen": None,
        "dte_seen": None,
        "vix_seen": 0.0,
        "pnl_pct": None,
        "strike_held": state.get("current_option_strike"),
        "cost_basis": state.get("adjusted_cost_basis"),
        "earnings_days": 30,
        "error": None
    }

    try:
        host = os.getenv("IBKR_HOST", "127.0.0.1")
        port = int(os.getenv("IBKR_PORT", 7497))
        clientId = int(os.getenv("IBKR_CLIENT_ID", 11))

        await ib.connectAsync(host, port, clientId=clientId)
        ib.reqMarketDataType(3) 
        
        aapl = Stock('AAPL', 'SMART', 'USD')
        await ib.qualifyContractsAsync(aapl)
        [ticker] = await ib.reqTickersAsync(aapl)
        price = ticker.marketPrice() or ticker.close
        data["price_seen"] = round(price, 2) if math.isfinite(price) and price > 0 else 0.0
        
        if data["price_seen"] == 0.0:
            ticker_yf = yf.Ticker('AAPL')
            data["price_seen"] = round(ticker_yf.fast_info.last_price, 2)
        
        pos_list = ib.positions()
        share_pos = [p for p in pos_list if isinstance(p.contract, Stock) and p.contract.symbol == 'AAPL']
        
        target_strike = state.get("current_option_strike")
        opt_pos = [p for p in pos_list if isinstance(p.contract, Option) and p.contract.symbol == 'AAPL']
        
        pos = None
        if target_strike:
            selected = [p for p in opt_pos if p.contract.strike == target_strike]
            if selected: pos = selected[0]
        
        if pos is None and opt_pos:
            pos = opt_pos[0]

        if share_pos:
            data["account_status"] = "SHARES_ASSIGNED"

        if pos:
            contract = pos.contract
            data["strike_held"] = contract.strike
            data["account_status"] = "CSP_ACTIVE" if contract.right == 'P' else "CC_ACTIVE"
            
            if not contract.exchange: contract.exchange = 'SMART'
            await ib.qualifyContractsAsync(contract)
            [opt_ticker] = await ib.reqTickersAsync(contract)
            
            mkt_price = opt_ticker.marketPrice()
            data["delta_source"] = "ibkr_realtime"
            
            if opt_ticker.modelGreeks and opt_ticker.modelGreeks.delta is not None:
                data["delta_seen"] = round(abs(opt_ticker.modelGreeks.delta), 4)
            else:
                try:
                    S = data["price_seen"] if data["price_seen"] > 0 else 0.0
                    if S > 0 and mkt_price > 0:
                        T = data["dte_seen"] / 365.25 if data["dte_seen"] else 0.1
                        r = get_risk_free_rate()
                        opt_type = 'put' if contract.right == 'P' else 'call'
                        iv = calculate_implied_vol(mkt_price, S, contract.strike, T, r, opt_type)
                        local_delta = calculate_local_delta(S, contract.strike, T, r, iv, opt_type)
                        data["delta_seen"] = round(abs(local_delta), 4)
                        data["delta_source"] = "local_math"
                except: pass

            if data["delta_seen"] is None:
                data["delta_seen"] = 0.20
                data["delta_source"] = "emergency_fallback"

            expiry = datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d')
            data["dte_seen"] = (expiry - datetime.now()).days
            
            if math.isfinite(mkt_price) and pos.avgCost != 0 and mkt_price > 0:
                data["pnl_pct"] = round(((pos.avgCost - mkt_price) / pos.avgCost) * 100, 2)

    except Exception as e:
        data["error"] = str(e)
    finally:
        ib.disconnect()
    return data

def get_ibkr_analysis() -> Dict[str, Any]:
    state = load_financial_state()
    try:
        final_data = asyncio.run(fetch_ibkr_data())
    except:
        loop = asyncio.get_event_loop()
        final_data = loop.run_until_complete(fetch_ibkr_data())

    if final_data["account_status"] == "SHARES_ASSIGNED" and state.get("current_phase") == "CSP_ACTIVE":
        strike = state.get("assignment_strike")
        premium = state.get("current_cycle_put_premium")
        if strike and premium is not None:
            adj_basis = round(strike - premium, 2)
            state["current_phase"] = "SHARES_ASSIGNED"
            state["adjusted_cost_basis"] = adj_basis
            save_financial_state(state)
            final_data["cost_basis"] = adj_basis

    try:
        ticker = yf.Ticker("AAPL", session=session)
        cal = ticker.calendar
        earn_date = cal.get('Earnings Date', [datetime.now()])[0] if isinstance(cal, dict) else cal.iloc[0, 0]
        if hasattr(earn_date, 'to_pydatetime'):
            earn_date = earn_date.to_pydatetime()
        days = (earn_date.replace(tzinfo=None) - datetime.now()).days
        final_data["earnings_days"] = max(0, days)
    except:
        final_data["earnings_days"] = 14
        
    return final_data

if __name__ == "__main__":
    # The Megaphone: Print the JSON for the agent to capture
    print(json.dumps(get_ibkr_analysis()))
