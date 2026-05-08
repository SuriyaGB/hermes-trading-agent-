import yfinance as yf
import json
from datetime import datetime

def debug_market_data():
    symbol = "AAPL"
    ticker = yf.Ticker(symbol)
    today = datetime.now().date()
    
    print(f"--- FORENSIC DATA AUDIT (MONTHLY): {datetime.now()} ---")
    
    expiries = ticker.options
    # Find the monthly (approx 35-45 days away)
    target_expiry = None
    for exp in expiries:
        exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
        dte = (exp_date - today).days
        if 30 <= dte <= 50:
            target_expiry = exp
            break
            
    if not target_expiry:
        print("ERROR: Could not find a monthly expiry (30-50 DTE).")
        return

    print(f"Targeting Monthly Expiry: {target_expiry} ({dte} days away)")
    chain = ticker.option_chain(target_expiry).puts
    
    # Look for the $280 Strike
    target_put = chain[chain['strike'] == 280.0]
    
    if not target_put.empty:
        put_data = target_put.iloc[0]
        print(f"--- $280 MONTHLY PUT RAW DATA ---")
        print(f"Bid: {put_data['bid']}")
        print(f"Ask: {put_data['ask']}")
        print(f"Mid: {(put_data['bid'] + put_data['ask'])/2}")
        print(f"Implied Volatility: {put_data['impliedVolatility']}")
        
        if put_data['bid'] == 0.0:
            print("STATUS: DATA IS STALE/ILLIQUID. This is why P&L shows 'Market Closed'.")
        else:
            print("STATUS: DATA IS LIVE. Bot should see this.")
    else:
        print(f"ERROR: $280 Put not found in {target_expiry} chain.")

if __name__ == "__main__":
    debug_market_data()
