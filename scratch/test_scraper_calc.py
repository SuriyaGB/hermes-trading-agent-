import asyncio
import json
import yfinance as yf
from core.get_ibkr_analysis import fetch_analysis_data, get_risk_free_rate, solve_iv, calculate_delta

async def test():
    ticker = yf.Ticker('AAPL')
    spot = round(float(ticker.fast_info['lastPrice']), 2)
    r = get_risk_free_rate()
    print(f"Spot Price: {spot}")
    print(f"Risk Free Rate: {r}")
    
    # Let's inspect multiple strikes in the option chain row for June 18 2026
    chain = ticker.option_chain("2026-06-18").puts
    subset = chain[(chain['strike'] >= 270.0) & (chain['strike'] <= 310.0)]
    print("\n--- June 18 2026 Option Chain (Puts subset) ---")
    print(subset[['strike', 'lastPrice', 'bid', 'ask', 'volume', 'impliedVolatility']])
    
    row = chain[chain['strike'] == 285.0].iloc[0]
    bid, ask = float(row['bid']), float(row['ask'])
    mid = round((bid + ask) / 2, 2)
    if mid <= 0.0: mid = float(row['lastPrice'])
    print(f"Resolved Mid Price: {mid}")
    
    dte = 30
    T = dte / 365.25
    iv_raw = float(row['impliedVolatility'])
    print(f"IV Raw: {iv_raw}")
    
    # Force solve IV using mid price
    iv_solved = solve_iv(mid, spot, 285.0, T, r, 'put')
    print(f"Solved IV: {iv_solved}")
    
    delta_solved = calculate_delta(spot, 285.0, T, r, iv_solved, 'put')
    print(f"Calculated Delta with Solved IV: {delta_solved}")

if __name__ == "__main__":
    asyncio.run(test())
