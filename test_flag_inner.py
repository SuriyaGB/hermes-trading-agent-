import yfinance as yf
import requests_cache
session = requests_cache.CachedSession('hermes_cache', expire_after=300)
try:
    ticker = yf.Ticker("AAPL", session=session)
    news = ticker.news
    print(f"News length: {len(news) if news else 0}")
    # print([n for n in news[:1]])
    
    bad_words = ['sue', 'lawsuit', 'crash', 'down', 'miss', 'fail', 'fraud', 'investigation', 'resign', 'cut', 'ban', 'warning']
    titles = [(n.get('content') or {}).get('title', '').lower() for n in news[:5]]
    print(f"Titles: {titles}")
    
    bad_count = 0
    for title in titles:
        if any(word in title for word in bad_words): bad_count += 1
        
    print(f"Bad count: {bad_count}")
except Exception as e:
    import traceback
    traceback.print_exc()
