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
TRACKER_PATH = DATA_DIR / 'intraday_tracker.json'

# Global Warning Tracker
WARNINGS = []

def add_warning(msg: str):
    print(f"[WARNING] {msg}", file=sys.stderr)
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
        return {"total_cash": 250000.0, "realized_pnl": 0.0, "positions": []}

def get_intraday_tracker() -> Dict[str, Any]:
    try:
        if TRACKER_PATH.exists():
            with open(TRACKER_PATH, 'r') as f:
                return json.load(f)
    except Exception as e:
        add_warning(f"Error loading intraday tracker: {e}")
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    return {
        "date": today_str,
        "contracts_written_today": 0,
        "first_strike": None,
        "first_premium": None
    }

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

def get_sma_200(symbol: str = "AAPL", spot_fallback: float = 0.0) -> float:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        if len(hist) >= 200:
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            return round(float(sma_200), 2)
        elif len(hist) > 0:
            sma_200 = hist['Close'].mean()
            return round(float(sma_200), 2)
    except Exception as e:
        add_warning(f"Error calculating 200 SMA: {e}")
    return round(spot_fallback * 0.90, 2)

def get_sma_50(symbol: str = "AAPL", spot_fallback: float = 0.0) -> float:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo")
        if len(hist) >= 50:
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            return round(float(sma_50), 2)
        elif len(hist) > 0:
            sma_50 = hist['Close'].mean()
            return round(float(sma_50), 2)
    except Exception as e:
        add_warning(f"Error calculating 50 SMA: {e}")
    return round(spot_fallback * 0.95, 2)


def get_daily_change(ticker: yf.Ticker, last_price: float) -> float:
    try:
        prev_close = ticker.info.get('previousClose')
        if not prev_close:
            hist = ticker.history(period='2d')
            if len(hist) >= 2:
                prev_close = float(hist['Close'].iloc[-2])
        if prev_close and prev_close > 0:
            change = ((last_price - prev_close) / prev_close) * 100
            return round(change, 2)
    except Exception as e:
        add_warning(f"Error calculating daily price change: {e}")
    return 0.0

async def get_yf_option_chain(spot: float, held_strike: float = None) -> Dict[str, Any]:
    result = {"option_chain": [], "chosen_expiry": None, "chosen_dte": None}
    ticker = yf.Ticker("AAPL")
    expiries = ticker.options
    today = datetime.now().date()
    
    # ── MULTI-EXPIRY COLLECTION (30 to 50 DTE window) ──────────────────────
    # Collect ALL valid expiry dates in the 30-50 DTE window.
    # This gives the AI the full picture to choose both Strike AND Expiry.
    valid_expiries = []
    for exp in expiries:
        exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
        dte = (exp_date - today).days
        if 30 <= dte <= 50:
            valid_expiries.append((exp, dte))

    if not valid_expiries:
        return result

    # Use shortest valid expiry as the reference for chosen_expiry/chosen_dte
    # (kept for backwards-compat; executor now uses AI's expiry_to_trade instead)
    result["chosen_expiry"] = valid_expiries[0][0].replace('-', '')
    result["chosen_dte"]    = valid_expiries[0][1]
    result["valid_expiries"] = [
        {"expiry": e.replace('-', ''), "dte": d} for e, d in valid_expiries
    ]

    try:
        vix = get_vix()
        r   = get_risk_free_rate()

        all_rows = []
        for target_expiry, target_dte in valid_expiries:
            try:
                chain = ticker.option_chain(target_expiry).puts
            except Exception:
                continue  # skip any expiry that yfinance cannot fetch

            T = target_dte / 365.25

            expiry_rows = []
            for _, row in chain.iterrows():
                strike = float(row['strike'])
                bid, ask = float(row['bid']), float(row['ask'])
                mid = round((bid + ask) / 2, 2)
                if mid <= 0.0: mid = float(row['lastPrice'])

                # IMPROVED IV DETECTION
                iv_raw = float(row['impliedVolatility'])
                if iv_raw < 0.01 or abs(iv_raw - 0.500005) < 0.0001 or (bid == 0.0 and ask == 0.0):
                    iv = solve_iv(mid, spot, strike, T, r, 'put')
                else:
                    iv = iv_raw

                delta = calculate_delta(spot, strike, T, r, iv, 'put')

                expiry_rows.append({
                    "expiry": target_expiry.replace('-', ''),  # YYYYMMDD — AI must echo this back
                    "dte":    target_dte,
                    "strike": strike,
                    "bid":    bid,
                    "ask":    ask,
                    "mid":    mid,
                    "delta":  round(delta, 4),
                    "iv":     round(iv * 100, 1)
                })

            # Keep only the 20 strikes closest to spot for this expiry
            expiry_rows_sorted = sorted(expiry_rows, key=lambda x: abs(x['strike'] - spot))
            atm_strikes = {x['strike'] for x in expiry_rows_sorted[:20]}

            for row in expiry_rows:
                if row['strike'] in atm_strikes or (held_strike and abs(row['strike'] - held_strike) < 0.1):
                    all_rows.append(row)

        # Final combined list: sorted by expiry then strike descending
        result["option_chain"] = sorted(
            all_rows,
            key=lambda x: (x['dte'], -x['strike'])
        )

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

def enrich_option_position(p: Dict[str, Any], spot: float, ticker: yf.Ticker) -> Dict[str, Any]:
    strike = float(p.get("strike"))
    expiry = p.get("expiry")
    opt_type_str = p.get("option_type", "PUT").lower()
    
    expiry_formatted = expiry
    if expiry and '-' not in expiry and len(expiry) == 8:
        expiry_formatted = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:]}"
        
    dte = 99
    delta = -0.5 if opt_type_str == 'put' else 0.5
    current_premium = float(p.get("avg_cost", 1.0))
    
    if expiry_formatted:
        try:
            today = datetime.now().date()
            exp_date = datetime.strptime(expiry_formatted, '%Y-%m-%d').date()
            dte = (exp_date - today).days
            
            chain_obj = ticker.option_chain(expiry_formatted)
            chain_table = chain_obj.calls if opt_type_str == 'call' else chain_obj.puts
            match_row = chain_table[chain_table['strike'] == strike]
            
            iv = 0.18
            if not match_row.empty:
                row = match_row.iloc[0]
                bid, ask = float(row['bid']), float(row['ask'])
                mid = round((bid + ask) / 2, 2)
                if mid <= 0.0: mid = float(row['lastPrice'])
                if mid > 0.0: current_premium = mid
                
                r = get_risk_free_rate()
                T = dte / 365.25
                iv_raw = float(row['impliedVolatility'])
                if iv_raw < 0.01 or abs(iv_raw - 0.500005) < 0.0001 or (bid == 0.0 and ask == 0.0):
                    iv = solve_iv(current_premium, spot, strike, T, r, opt_type_str)
                else:
                    iv = iv_raw
            else:
                r = get_risk_free_rate()
                T = dte / 365.25
                iv = get_vix_sigma()
                current_premium = black_scholes_price(spot, strike, T, r, iv, opt_type_str)
                
            delta_raw = calculate_delta(spot, strike, dte / 365.25, get_risk_free_rate(), iv, opt_type_str)
            delta = round(delta_raw, 4)
        except Exception as e:
            add_warning(f"Error enriching option {opt_type_str.upper()}_{strike}_{expiry}: {e}")
            
    avg_cost = float(p.get("avg_cost", 1.0))
    profit_pct = 0.0
    if avg_cost > 0:
        profit_pct = ((avg_cost - current_premium) / avg_cost) * 100
        
    position_key = f"{opt_type_str.upper()}_{int(strike)}_{expiry.replace('-', '') if expiry else 'N/A'}"
    
    return {
        "position_key": position_key,
        "type": "Option",
        "option_type": opt_type_str.upper(),
        "strike": strike,
        "expiry": expiry.replace('-', '') if expiry else 'N/A',
        "avg_cost": avg_cost,
        "current_premium": round(current_premium, 2),
        "profit_pct": round(profit_pct, 1),
        "dte": dte,
        "delta": delta
    }

async def fetch_analysis_data() -> Dict[str, Any]:
    ticker = yf.Ticker('AAPL')
    price_seen = round(float(ticker.fast_info['lastPrice']), 2)
    vix = get_vix()
    earnings_days = get_earnings_days("AAPL")
    recent_news = get_recent_news("AAPL")
    
    sma_200 = get_sma_200("AAPL", price_seen)
    sma_50 = get_sma_50("AAPL", price_seen)
    if os.getenv("SIM_MODE") == "1":
        sma_200 = float(os.getenv("FORCE_SMA", sma_200))
        sma_50 = float(os.getenv("FORCE_SMA_50", sma_50))
    daily_change_pct = get_daily_change(ticker, price_seen)
    
    portfolio = load_portfolio()
    intraday_tracker = get_intraday_tracker()
    
    active_positions = []
    has_shares = False
    has_put = False
    has_call = False
    first_held_strike = None
    first_held_expiry = None
    first_held_option_type = None
    first_held_delta = 0.0
    first_held_dte = 99
    
    shares_count = 0
    for p in portfolio.get("positions", []):
        if p.get("type") == "Stock" and p.get("symbol") == "AAPL":
            qty = p.get("quantity", 0)
            if qty >= 100:
                has_shares = True
                shares_count += qty
            active_positions.append({
                "position_key": f"STOCK_{p.get('symbol')}",
                "type": "Stock",
                "symbol": p.get("symbol"),
                "quantity": qty,
                "avg_cost": p.get("avg_cost")
            })
        elif p.get("type") == "Option":
            enriched = enrich_option_position(p, price_seen, ticker)
            active_positions.append(enriched)
            if enriched["option_type"] == "PUT":
                has_put = True
            elif enriched["option_type"] == "CALL":
                has_call = True
                
            if not first_held_strike:
                first_held_strike = enriched["strike"]
                first_held_expiry = enriched["expiry"]
                first_held_option_type = enriched["option_type"]
                first_held_delta = enriched["delta"]
                first_held_dte = enriched["dte"]

    risk_units = int(shares_count // 100) + sum(1 for p in active_positions if p.get("type") == "Option")
    
    net_liq = float(portfolio.get("total_cash", 250000.0))
    stock_value = shares_count * price_seen
    net_liq += stock_value
    
    buying_power_limit = net_liq * 0.50
    remaining_buying_power = max(0.0, buying_power_limit - sum(100 * p.get("strike", price_seen) for p in active_positions if p.get("type") == "Option" and p.get("option_type") == "PUT") - stock_value)
    
    if has_shares and has_call:
        account_status = "CC_ACTIVE"
    elif has_shares:
        account_status = "SHARES_ASSIGNED"
    elif has_put:
        account_status = "CSP_ACTIVE"
    else:
        account_status = "CASH_ONLY"
        
    chain_result = await get_yf_option_chain(price_seen, first_held_strike)
    
    iv_current = 18.0
    if chain_result["option_chain"]:
        atm = sorted(chain_result["option_chain"], key=lambda x: abs(x['strike'] - price_seen))[0]
        iv_current = atm['iv']
        
    if price_seen < sma_200:
        day_classification = "BEARISH_DAY"
    elif iv_current > 30.0 or daily_change_pct <= -2.0:
        day_classification = "GOOD_DAY"
    elif 15.0 <= iv_current <= 30.0 and daily_change_pct > -2.0:
        day_classification = "NORMAL_DAY"
    else:
        day_classification = "QUIET_DAY"

    # ── SCAN CAPACITY: Python computes all entry gates with hard math ─────────
    # This replaces the old patchwork fake-position injection.
    # Python decides CAN we open a new put. LLM decides WHICH strike to pick.
    # active_positions stays clean — only real broker positions.
    max_allowed_units    = 1 if day_classification == "BEARISH_DAY" else 4
    daily_cap            = 1 if day_classification in ["QUIET_DAY", "BEARISH_DAY"] else 2
    contracts_written_today = intraday_tracker.get("contracts_written_today", 0)

    earnings_safe    = (earnings_days > 7) if earnings_days else True
    buying_power_ok  = remaining_buying_power >= (price_seen * 100 * 0.20)
    vix_ok           = 13.0 <= vix <= 29.9
    risk_ok          = risk_units < max_allowed_units
    pacing_ok        = contracts_written_today < daily_cap

    can_open = earnings_safe and buying_power_ok and vix_ok and risk_ok and pacing_ok

    if not can_open:
        if not earnings_safe:   scan_block_reason = f"Earnings in {min(earnings_days) if earnings_days else 'N/A'} days (<= 7). Gate: earnings_safe."
        elif not buying_power_ok: scan_block_reason = f"Buying power ${remaining_buying_power:.0f} below min required. Gate: buying_power_ok."
        elif not vix_ok:        scan_block_reason = f"VIX={vix} outside 13-29.9 range. Gate: vix_ok."
        elif not risk_ok:       scan_block_reason = f"risk_units={risk_units} >= max {max_allowed_units} for {day_classification}. Gate: risk_ok."
        else:                   scan_block_reason = f"contracts_written_today={contracts_written_today} >= daily_cap={daily_cap}. Gate: pacing_ok."
    else:
        scan_block_reason = "All gates passed."

    scan_capacity = {
        "can_open_new_put"   : can_open,
        "slots_available"    : max(0, max_allowed_units - risk_units),
        "daily_cap_remaining": max(0, daily_cap - contracts_written_today),
        "earnings_safe"      : earnings_safe,
        "buying_power_ok"    : buying_power_ok,
        "vix_ok"             : vix_ok,
        "reason"             : scan_block_reason
    }
    # ── END SCAN CAPACITY ─────────────────────────────────────────────────────

    data = {
        "account_status": account_status,
        "price_seen": price_seen,
        "vix_seen": vix,
        "iv_current": iv_current,
        "option_chain": chain_result["option_chain"],
        "chosen_expiry": chain_result["chosen_expiry"],
        "chosen_dte": chain_result["chosen_dte"],
        "warnings": WARNINGS,
        "earnings_days": earnings_days,
        "recent_news": recent_news,
        "scan_capacity": scan_capacity,

        "portfolio_summary": {
            "net_liquidation_value": round(net_liq, 2),
            "buying_power_limit": round(buying_power_limit, 2),
            "remaining_buying_power": round(remaining_buying_power, 2),
            "dynamic_max_contracts": 4,
            "current_risk_units": risk_units,
            "account_status": account_status
        },
        "active_positions": active_positions,
        "intraday_state": intraday_tracker,
        "market_regime": {
            "price_seen": price_seen,
            "daily_change_pct": daily_change_pct,
            "vix": vix,
            "200_sma": sma_200,
            "50_sma": sma_50,
            "iv_current": iv_current,
            "day_classification": day_classification
        }
    }

    
    if first_held_strike:
        data["strike_held"] = first_held_strike
        data["expiry_held"] = first_held_expiry
        data["delta_current"] = first_held_delta
        data["dte_current"] = first_held_dte
    else:
        data["strike_held"] = None
        data["expiry_held"] = None
        data["delta_current"] = 0.0
        data["dte_current"] = 99
        
    return data

if __name__ == "__main__":
    print(json.dumps(asyncio.run(fetch_analysis_data()), indent=2))
