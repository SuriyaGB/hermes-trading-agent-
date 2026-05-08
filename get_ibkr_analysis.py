import os
import math
import json
import asyncio
import numpy as np
import yfinance as yf
from datetime import datetime
from typing import Dict, Any, List
from scipy.stats import norm
from scipy.optimize import brentq
import requests_cache

import sys
from ib_insync import IB, Stock, Option, util

session = requests_cache.CachedSession('hermes_cache', expire_after=300)


# ═══════════════════════════════════════════════════════════════
# 1. RELIABLE YAHOO FINANCE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_risk_free_rate() -> float:
    """Fetch 13-week T-Bill rate. Returns 0.05 on failure."""
    try:
        p = yf.Ticker('^IRX').fast_info.last_price
        if p and p > 0:
            return p / 100
    except:
        pass
    return 0.05


def get_vix() -> float:
    """Fetch VIX as raw index value (e.g. 17.4). Returns -1.0 on failure."""
    try:
        p = yf.Ticker('^VIX').fast_info.last_price
        if p and p > 0:
            return round(p, 2)
    except:
        pass
    return -1.0


def get_recent_news(symbol: str = "AAPL") -> List[str]:
    """
    Fetch raw headlines for the LLM to analyze.
    Removes Python-level keyword filtering to allow LLM to use its own context.
    """
    try:
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news
        if not raw_news:
            return []
            
        headlines = []
        for item in raw_news:
            # yfinance structure update: title is now inside 'content'
            content = item.get("content", {})
            title = content.get("title")
            if title:
                headlines.append(title)
            
            if len(headlines) >= 6:
                break
                
        return headlines
    except Exception as e:
        sys.stderr.write(f"[NEWS_ERROR] Failed to fetch raw news: {e}\n")
        return []


def get_iv30_rank(symbol: str = "AAPL") -> float | None:
    """
    Calculate IV30 Rank from 1-year history.
    Uses rolling 30-day realised vol as a proxy for IV30.
    Returns a percentile 0-100. Returns None on failure.
    """
    try:
        hist = yf.Ticker(symbol).history(period="1y")
        if hist.empty:
            return None
        returns = hist['Close'].pct_change()
        vol = returns.rolling(window=30).std() * np.sqrt(252)
        vol = vol.dropna()
        if vol.empty or vol.max() == vol.min():
            return None
        rank = (vol.iloc[-1] - vol.min()) / (vol.max() - vol.min()) * 100
        return round(float(rank), 2)
    except:
        return None


def get_earnings_days(symbol: str = "AAPL") -> int:
    """
    3-layer earnings engine. Returns days to next earnings.
    Layer 1: Live yfinance get_earnings_dates()
    Layer 2: ticker.calendar
    Layer 3: AAPL quarterly proxy (Jan/Apr/Jul/Oct)
    """
    ticker = yf.Ticker(symbol)
    today = datetime.now().date()

    # Layer 1
    try:
        df = ticker.get_earnings_dates(limit=8)
        if df is not None and not df.empty:
            future = [d.date() for d in df.index
                      if hasattr(d, 'date') and d.date() > today]
            if future:
                return (min(future) - today).days
    except:
        pass

    # Layer 2
    try:
        cal = ticker.calendar
        if isinstance(cal, dict):
            dates = cal.get('Earnings Date', [])
            if dates:
                d = dates[0]
                if hasattr(d, 'date'):
                    d = d.date()
                if d > today:
                    return (d - today).days
    except:
        pass

    # Layer 3: AAPL quarterly proxy
    year = today.year
    schedule = [
        datetime(year, 1, 30).date(),
        datetime(year, 4, 30).date(),
        datetime(year, 7, 31).date(),
        datetime(year, 10, 30).date(),
        datetime(year + 1, 1, 30).date(),
    ]
    future = [d for d in schedule if d > today]
    return (min(future) - today).days if future else 90


def get_days_to_exdiv(symbol: str = "AAPL") -> int | None:
    """Fetch days to next ex-dividend date from ticker.info."""
    try:
        info = yf.Ticker(symbol).info
        ts = info.get('exDividendDate')
        if ts:
            exdiv = datetime.fromtimestamp(ts).date()
            days = (exdiv - datetime.now().date()).days
            return max(0, days) if days >= 0 else None
    except:
        pass
    return None


def get_yf_option_chain(symbol: str, spot: float, chosen_lower: float, upper_bound: float, earnings_days: int) -> dict:
    """
    Bulletproof Fallback: Fetches option chain from yfinance if IBKR is blind.
    Ensures the Brain always has tradeable strikes to evaluate.
    """
    try:
        tk = yf.Ticker(symbol)
        expiries = tk.options
        if not expiries:
            return {"option_chain": [], "chosen_expiry": None, "chosen_dte": None}

        today = datetime.now()
        best_expiry = None
        best_dte = None
        best_diff = 999
        
        # Select target expiry (Monthly window 21-45 days, before earnings)
        for exp in expiries:
            try:
                d = datetime.strptime(exp, '%Y-%m-%d')
                dte = (d - today).days
                if 21 <= dte <= 45 and dte < earnings_days:
                    diff = abs(dte - 35)
                    if diff < best_diff:
                        best_diff = diff
                        best_expiry = exp
                        best_dte = dte
            except: continue
        
        if not best_expiry:
            return {"option_chain": [], "chosen_expiry": None, "chosen_dte": None}

        # Fetch chain from Yahoo
        chain = tk.option_chain(best_expiry)
        puts = chain.puts
        
        r = get_risk_free_rate()
        T = best_dte / 365.0
        menu = []

        for _, row in puts.iterrows():
            strike = float(row['strike'])
            if chosen_lower <= strike <= upper_bound:
                bid = float(row['bid'])
                ask = float(row['ask'])
                mid = (bid + ask) / 2.0
                if mid <= 0: mid = float(row['lastPrice'])
                
                # Quality gate: 1% return min
                if mid < strike * 0.01: continue
                
                # Black-Scholes Delta calculation (Yahoo delta is unreliable)
                iv = float(row['impliedVolatility'])
                if iv <= 0: iv = 0.30 
                
                delta = calculate_local_delta(spot, strike, T, r, iv, 'put')
                abs_delta = round(abs(delta), 4)
                
                # Delta band: 0.10 to 0.35
                if 0.10 <= abs_delta <= 0.35:
                    menu.append({
                        "strike": strike,
                        "expiry": best_expiry.replace('-', ''),
                        "dte": best_dte,
                        "bid": round(bid, 2),
                        "ask": round(ask, 2),
                        "mid": round(mid, 2),
                        "delta": abs_delta,
                        "premium_per_contract": round(mid * 100, 2),
                        "source": "yfinance_fallback"
                    })
        
        return {
            "option_chain": sorted(menu, key=lambda x: x['strike']),
            "chosen_expiry": best_expiry.replace('-', ''),
            "chosen_dte": best_dte
        }
    except Exception as e:
        sys.stderr.write(f"[EYE] Yahoo Fallback Failed: {e}\n")
        return {"option_chain": [], "chosen_expiry": None, "chosen_dte": None}


# ═══════════════════════════════════════════════════════════════
# 2. BLACK-SCHOLES MATH ENGINE (Greeks fallback)
# ═══════════════════════════════════════════════════════════════

def black_scholes_price(S, K, T, r, sigma, option_type='put') -> float:
    if any(x is None for x in [r, sigma]) or T <= 0 or sigma <= 0:
        return 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == 'call':
        return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
    return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))


def calculate_local_delta(S, K, T, r, sigma, option_type='put') -> float:
    if any(x is None for x in [r, sigma]) or T <= 0 or sigma <= 0:
        return 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return float(norm.cdf(d1) if option_type == 'call' else norm.cdf(d1) - 1)


def calculate_implied_vol(market_price, S, K, T, r, option_type='put') -> float:
    """Solve for IV using Brent's method. Returns 0.30 (AAPL typical) on failure."""
    if r is None or market_price <= 0 or T <= 0:
        return 0.30
    try:
        return brentq(
            lambda sigma: black_scholes_price(S, K, T, r, sigma, option_type) - market_price,
            1e-6, 5.0
        )
    except:
        return 0.30


# ═══════════════════════════════════════════════════════════════
# 3. SMART OPTION CHAIN FETCHER (Fix 2)
# ═══════════════════════════════════════════════════════════════

async def get_option_chain(ib, symbol: str = "AAPL",
                           ma_200: float = 0.0,
                           earnings_days: int = 90) -> dict:
    """
    Fetches a smart-filtered Put option menu for the Brain.

    Returns dict with keys:
      option_chain    – list of filtered strike dicts
      chosen_expiry   – selected expiry string (YYYYMMDD)
      chosen_dte      – DTE of selected expiry
      iv_caution      – True if IV rank in caution band 75-85%
      filter_debug    – transparency dict showing bounds used

    All Python-level filters applied BEFORE the LLM sees any data:
      - VIX-dynamic lower bound (12/18/25% below spot)
      - MA-200 floor guard (never below MA × 0.95)
      - Closest-to-35-DTE expiry (21-45 DTE window)
      - Earnings safety: expiry DTE must be < earnings_days
      - Delta band: 0.10 ≤ |delta| ≤ 0.35
      - Premium quality: mid ≥ strike × 0.01 (1% return minimum)
    """
    _empty = {
        "option_chain": [], "chosen_expiry": None,
        "chosen_dte": None, "iv_caution": False, "filter_debug": {}
    }

    try:
        # ── Spot Price ────────────────────────────────────────────────────
        contract = Stock(symbol, 'SMART', 'USD')
        await ib.qualifyContractsAsync(contract)
        [tkr] = await ib.reqTickersAsync(contract)

        spot = tkr.marketPrice()
        if not math.isfinite(spot) or spot <= 0:
            spot = getattr(tkr, 'last', 0.0)
        if not math.isfinite(spot) or spot <= 0:
            return _empty

        # ── ROOT CAUSE FIX (Error 321) ────────────────────────────────────
        # Read the real IBKR conId from the qualified contract.
        # Passing conId=0 to reqSecDefOptParamsAsync is the cause of Error 321.
        # IBKR cannot validate the option chain request without a real contract ID.
        underlying_con_id = contract.conId
        if not underlying_con_id:
            sys.stderr.write(f"[EYE] WARNING: Could not get conId for {symbol}. Option chain unavailable.\n")
            return _empty

        # ── VIX-Dynamic Lower Bound ───────────────────────────────────────
        vix = get_vix()
        if vix < 20:
            vix_pct = 0.88     # Normal: 12% below spot
        elif vix < 30:
            vix_pct = 0.82     # Caution: 18% below spot
        else:
            vix_pct = 0.75     # Crisis: 25% below spot

        vix_lower   = round(spot * vix_pct, 2)
        upper_bound = round(spot * 1.05, 2)

        # ── MA-200 Floor Guard ────────────────────────────────────────────
        # Never set the lower bound above the MA floor (institutional support)
        ma_floor     = round(ma_200 * 0.95, 2) if ma_200 > 0 else 0.0
        chosen_lower = max(vix_lower, ma_floor)

        filter_debug = {
            "vix":          vix,
            "vix_lower":    vix_lower,
            "ma_floor":     ma_floor,
            "chosen_lower": chosen_lower,
            "upper_bound":  upper_bound
        }

        # ── Fetch IBKR Option Params (using real conId) ───────────────────
        chains = await ib.reqSecDefOptParamsAsync(symbol, '', 'STK', underlying_con_id)
        chain  = next((c for c in chains if c.exchange == 'SMART'), None)
        if chain is None:
            chain = chains[0] if chains else None
        if chain is None:
            return {**_empty, "filter_debug": filter_debug}

        today = datetime.now()

        # ── Expiry Selection: Closest to 35 DTE, Earnings-Safe ───────────
        TARGET_DTE  = 35
        best_expiry = None
        best_dte    = None
        best_diff   = 9999

        for exp_str in sorted(chain.expirations):
            exp_date = datetime.strptime(exp_str, '%Y%m%d')
            dte = (exp_date - today).days
            if dte < 21 or dte > 45:
                continue
            if dte >= earnings_days:        # Expiry straddles earnings → skip
                continue
            diff = abs(dte - TARGET_DTE)
            if diff < best_diff:
                best_diff   = diff
                best_expiry = exp_str
                best_dte    = dte

        if best_expiry is None:
            return {**_empty, "filter_debug": filter_debug}

        T = best_dte / 365.0

        # ── Strike Filtering ──────────────────────────────────────────────
        valid_strikes = [s for s in chain.strikes if chosen_lower <= s <= upper_bound]
        if not valid_strikes:
            return {**_empty, "chosen_expiry": best_expiry,
                    "chosen_dte": best_dte, "filter_debug": filter_debug}

        contracts = [Option(symbol, best_expiry, s, 'P', 'SMART') for s in valid_strikes]
        qualified  = await ib.qualifyContractsAsync(*contracts)
        # Filter out any contracts that failed qualification (conId == 0)
        # to prevent secondary Error 321s when requesting tickers.
        qualified  = [c for c in qualified if c.conId and c.conId != 0]
        if not qualified:
            return {**_empty, "chosen_expiry": best_expiry,
                    "chosen_dte": best_dte, "filter_debug": filter_debug}
        tickers    = await ib.reqTickersAsync(*qualified)

        # ── Build Quality-Filtered Menu ───────────────────────────────────
        r    = get_risk_free_rate()
        menu = []

        for t in tickers:
            strike = t.contract.strike

            # Premium
            if t.bid > 0 and t.ask > 0:
                mid = (t.bid + t.ask) / 2.0
            else:
                mid = t.marketPrice()
            if not math.isfinite(mid) or mid <= 0:
                continue

            # Fix 2D: Premium quality gate — 1% return on capital minimum
            # min_premium = strike × 100 × 0.01 / 100 = strike × 0.01
            if mid < strike * 0.01:
                continue

            # Delta: IBKR Greeks preferred, Black-Scholes fallback
            delta = None
            if t.modelGreeks and t.modelGreeks.delta is not None:
                delta = t.modelGreeks.delta
            if delta is None:
                iv    = calculate_implied_vol(mid, spot, strike, T, r, 'put')
                delta = calculate_local_delta(spot, strike, T, r, iv, 'put')

            abs_delta = round(abs(delta), 4) if delta is not None else None

            # Fix 2 — Delta band: 0.10 ≤ |delta| ≤ 0.35
            if abs_delta is None or abs_delta < 0.10 or abs_delta > 0.35:
                continue

            menu.append({
                "strike":               strike,
                "expiry":               best_expiry,
                "dte":                  best_dte,
                "bid":                  round(t.bid, 2),
                "ask":                  round(t.ask, 2),
                "mid":                  round(mid, 2),
                "delta":                abs_delta,
                "premium_per_contract": round(mid * 100, 2)
            })

        # ── IV Caution Flag ───────────────────────────────────────────────
        iv30 = get_iv30_rank(symbol)
        iv_caution = iv30 is not None and 75.0 <= iv30 <= 85.0

        # ── FINAL FALLBACK: If IBKR menu is empty, trigger Yahoo ──────────
        if not menu:
            sys.stderr.write(f"[EYE] IBKR returned 0 qualified strikes. Engaging Yahoo Fallback...\n")
            yf_res = get_yf_option_chain(symbol, spot, chosen_lower, upper_bound, earnings_days)
            menu = yf_res["option_chain"]
            if menu:
                best_expiry = yf_res["chosen_expiry"]
                best_dte = yf_res["chosen_dte"]

        return {
            "option_chain":  sorted(menu, key=lambda x: x['strike']),
            "chosen_expiry": best_expiry,
            "chosen_dte":    best_dte,
            "iv_caution":    iv_caution,
            "filter_debug":  filter_debug
        }

    except Exception as e:
        sys.stderr.write(f"ERROR in get_option_chain: {e}\n")
        return _empty


# ═══════════════════════════════════════════════════════════════
# 4. MAIN DATA ASSEMBLY (Safety-First)
# ═══════════════════════════════════════════════════════════════

async def fetch_ibkr_data() -> Dict[str, Any]:
    """
    Two-phase data assembly:
      Phase 1 — Yahoo Foundation (always runs, no IBKR dependency)
      Phase 2 — IBKR Execution Layer (option chain + precise price)

    If Phase 2 fails, Phase 1 data still reaches the Brain.
    The bot is never 'blind' due to an IBKR connection issue.
    """
    data: Dict[str, Any] = {
        "account_status":    "CASH_ONLY",
        "price_seen":        0.0,
        "vix_seen":          -1.0,
        "ma_200":            0.0,
        "ma_50":             0.0,
        "fifty_two_week_low":  0.0,
        "fifty_two_week_high": 0.0,
        "iv30_rank":         None,
        "earnings_days":     90,
        "days_to_exdiv":     None,
        "recent_news":       [],
        # Chain output fields (populated in Phase 2)
        "option_chain":      [],
        "chosen_expiry":     None,
        "chosen_dte":        None,
        "iv_caution":        False,
        "filter_debug":      {},
        "error":             None,
    }

    # ── PHASE 1: Yahoo Foundation ─────────────────────────────────────────
    try:
        hist = yf.Ticker('AAPL').history(period='1y')
        if not hist.empty:
            closes = hist['Close']
            data["price_seen"]           = round(float(closes.iloc[-1]), 2)
            data["ma_200"]               = round(float(closes.tail(200).mean()), 2)
            data["ma_50"]                = round(float(closes.tail(50).mean()), 2)
            data["fifty_two_week_low"]   = round(float(closes.min()), 2)
            data["fifty_two_week_high"]  = round(float(closes.max()), 2)
    except Exception as e:
        data["error"] = f"Yahoo history failed: {e}"

    data["vix_seen"]      = get_vix()
    data["earnings_days"] = get_earnings_days("AAPL")
    data["iv30_rank"]     = get_iv30_rank("AAPL")
    data["days_to_exdiv"] = get_days_to_exdiv("AAPL")
    data["recent_news"]   = get_recent_news("AAPL")

    # ── FIX 3: Python IV Gate — runs BEFORE option chain fetch ───────────
    # If IV is at extreme high AND earnings are close, inject HOLD immediately.
    # The option chain is never fetched in this condition.
    # This prevents the LLM from being tempted by inflated premiums.
    iv30 = data["iv30_rank"]
    earn = data["earnings_days"]
    if iv30 is not None and iv30 > 85 and earn < 21:
        data["decision"] = "HOLD_PUT_POSITION"
        data["reason"]   = (
            f"[IV GATE TRIGGERED] IV30 rank {iv30}% is in the danger zone (>85%) "
            f"and earnings are only {earn} days away (<21). "
            f"Option chain NOT fetched. No new positions until IV normalises or "
            f"earnings pass. This is a Python-enforced gate — not an LLM decision."
        )
        return data   # ← Early return: Brain gets HOLD, never sees the chain

    # ── PHASE 2: IBKR Execution Layer ────────────────────────────────────
    ib = IB()
    try:
        host = os.getenv("IBKR_HOST", "127.0.0.1")
        port = int(os.getenv("IBKR_PORT", 7497))
        await asyncio.wait_for(ib.connectAsync(host, port, clientId=11), timeout=10)
        ib.reqMarketDataType(3)  # Allow delayed data

        # IBKR precise price (overwrites Yahoo close if available)
        aapl = Stock('AAPL', 'SMART', 'USD')
        await ib.qualifyContractsAsync(aapl)
        [tkr] = await ib.reqTickersAsync(aapl)
        ib_price = tkr.marketPrice()
        if not math.isfinite(ib_price) or ib_price <= 0:
            ib_price = getattr(tkr, 'last', 0.0)
        if math.isfinite(ib_price) and ib_price > 0:
            data["price_seen"] = round(ib_price, 2)

        # Smart option chain (with all Fix-2 filters applied)
        chain_result = await asyncio.wait_for(
            get_option_chain(
                ib, "AAPL",
                ma_200=data["ma_200"],
                earnings_days=data["earnings_days"]
            ),
            timeout=45
        )
        data["option_chain"]  = chain_result["option_chain"]
        data["chosen_expiry"] = chain_result["chosen_expiry"]
        data["chosen_dte"]    = chain_result["chosen_dte"]
        data["iv_caution"]    = chain_result["iv_caution"]
        data["filter_debug"]  = chain_result["filter_debug"]

        # Account / portfolio status
        if os.getenv("SIM_MODE") == "1":
            from sim_executor import load_portfolio, load_state
            portfolio = load_portfolio()
            state = load_state()
            pos_list = portfolio.get("positions", [])
            
            if any(x.get("type") == "Stock" for x in pos_list):
                data["account_status"] = "SHARES_ASSIGNED"
                if any(x.get("type") == "Option" for x in pos_list):
                    data["account_status"] = "CC_ACTIVE"
            elif any(x.get("type") == "Option" for x in pos_list):
                data["account_status"] = "CSP_ACTIVE"
            
            # Populate position details for the Brain
            if data["account_status"] in ["CSP_ACTIVE", "CC_ACTIVE"]:
                # Find the option position
                opt = next((x for x in pos_list if x.get("type") == "Option"), None)
                if opt:
                    data["strike_held"] = opt.get("strike")
                    # Calculate DTE from expiry string (YYYYMMDD)
                    try:
                        exp_str = opt.get("expiry")
                        if exp_str:
                            exp_date = datetime.strptime(exp_str, '%Y%m%d').date()
                            data["dte_seen"] = (exp_date - datetime.now().date()).days
                    except: pass
                    
                    # Calculate P&L %
                    # (Current Mid - Cost) / Cost
                    # Note: For Short Puts, P&L is (Credit - Current Price) / Credit
                    # But for simplicity, the Brain looks at (Strike - Current Price) or just Theta.
                    # We'll provide the raw cost basis for the Brain to calculate.
                    data["cost_basis"] = state.get("adjusted_cost_basis")
                    avg_cost = opt.get("avg_cost", 0)
                    if avg_cost > 0:
                        # Estimate current mid from Yahoo for P&L
                        # For now, we'll let the Brain see the spot vs strike.
                        pass
        # LIVE IBKR account status logic would go here

    except Exception as e:
        ibkr_err = f"IBKR Error: {e}"
        data["error"] = ibkr_err if not data["error"] else data["error"] + " | " + ibkr_err
    finally:
        ib.disconnect()

    return data


# ═══════════════════════════════════════════════════════════════
# 5. PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def get_ibkr_analysis() -> Dict[str, Any]:
    """
    Main function called by run_pulse_sim.sh.
    Assembles the full JSON payload for the Brain.
    """
    data = asyncio.run(fetch_ibkr_data())

    # Circuit Breaker: if Yahoo Foundation also failed, force HOLD
    if data["price_seen"] == 0.0 or data["vix_seen"] == -1.0:
        data["decision"] = "HOLD_PUT_POSITION"
        data["reason"]   = (
            f"[FATAL DATA ERROR] Eye is blind. "
            f"price_seen={data['price_seen']}, vix_seen={data['vix_seen']}. "
            f"Check internet connectivity. No trades until data restored."
        )

    return data


if __name__ == "__main__":
    print(json.dumps(get_ibkr_analysis(), default=str))
