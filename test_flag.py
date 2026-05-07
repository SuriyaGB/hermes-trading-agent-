import get_ibkr_analysis as g
import traceback
try:
    print(g.get_recent_news_flag())
except Exception as e:
    traceback.print_exc()
