import json
import os
import sys
import asyncio
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

# Setup project paths
PROJ = Path(__file__).parent
sys.path.append(str(PROJ))

import core.executor as ex
import core.call_brain_direct as cbd

def reset_state():
    """Ensure a clean CASH_ONLY baseline."""
    with open(PROJ / 'data/trade_state.json', 'w') as f:
        json.dump({'current_phase': 'CASH_ONLY'}, f)
    with open(PROJ / 'data/portfolio.json', 'w') as f:
        json.dump({'total_cash': 250000.0, 'realized_pnl': 0.0, 'positions': []}, f)
    if (PROJ / 'data/trades_log.csv').exists():
        os.remove(PROJ / 'data/trades_log.csv')
    print("✅ Baseline reset.")

# --- MOCKS ---
def broken_telegram(msg):
    """Simulates a hard network failure/timeout."""
    print(f"   [MOCK] Telegram Send Attempted: {msg[:50]}...")
    raise Exception("NETWORK_TIMEOUT: Simulated Telegram Failure")

async def run_resilience_tests():
    print("==================================================")
    print("RESILIENCE TEST SUITE: TELEGRAM & BRAIN FAILURES")
    print("==================================================")

    # --- TEST A: SELL_NEW_PUT with Telegram Failure ---
    print("\n--- TEST A: SELL_NEW_PUT with Telegram Failure ---")
    reset_state()
    ex.send_telegram = broken_telegram # Monkey-patch executor

    eye_data = {
        'account_status': 'CASH_ONLY', 'price_seen': 295.0, 'market_open': True,
        'option_chain': [{'strike': 280.0, 'mid': 3.10}], 'chosen_dte': 37
    }
    with open(PROJ / '.eye_cache.json', 'w') as f: json.dump(eye_data, f)

    sell_decision = {'decision': 'SELL_NEW_PUT', 'strike_to_trade': 280.0, 'premium_to_collect': 3.10}
    sys.stdin = io.StringIO(json.dumps(sell_decision))
    
    try:
        await ex.main_executor()
        print("✅ Executor finished execution despite Telegram crash.")
    except Exception as e:
        print(f"❌ CRITICAL FAILURE: Executor crashed: {e}")

    with open(PROJ / 'data/trade_state.json') as f: s = json.load(f)
    if s['current_phase'] == 'CSP_ACTIVE':
        print("✅ TEST A PASSED: State updated correctly.")
    else:
        print("❌ TEST A FAILED: State not updated.")


    # --- TEST B: CLOSE_FOR_PROFIT with Telegram Failure ---
    print("\n--- TEST B: CLOSE_FOR_PROFIT with Telegram Failure ---")
    close_decision = {'decision': 'CLOSE_FOR_PROFIT', 'strike_held': 280.0, 'premium_to_collect': 1.55}
    sys.stdin = io.StringIO(json.dumps(close_decision))
    
    try:
        await ex.main_executor()
        print("✅ Executor finished execution despite Telegram crash.")
    except Exception as e:
        print(f"❌ CRITICAL FAILURE: Executor crashed: {e}")

    with open(PROJ / 'data/trade_state.json') as f: s = json.load(f)
    if s['current_phase'] == 'CASH_ONLY':
        print("✅ TEST B PASSED: Position cleared correctly.")
    else:
        print("❌ TEST B FAILED.")


    # --- TEST C: OpenAI Failure Telegram Alert (CHECK 2) ---
    print("\n--- TEST C: OpenAI Failure Telegram Alert (CHECK 2) ---")
    # We monkey-patch urllib.request.urlopen INSIDE call_brain_direct
    # to simulate OpenAI failing, and then catch the Telegram call.
    
    # Setup env vars so it tries to send Telegram
    os.environ['TELEGRAM_BOT_TOKEN'] = '123:test'
    os.environ['TELEGRAM_CHAT_ID'] = '456'
    os.environ['OPENAI_API_KEY'] = 'sk-test'

    # We use a mock to track calls to urlopen
    with patch('urllib.request.urlopen') as mock_url:
        # First call (OpenAI) fails
        # Second call (Telegram) succeeds (or fails, we just want to see it called)
        mock_url.side_effect = [
            Exception("OpenAI API Quota Exceeded"), # 1st call: OpenAI
            MagicMock()                             # 2nd call: Telegram
        ]
        
        print("🚀 Calling cbd.call_openai()... (Should trigger Telegram alert)")
        try:
            cbd.call_openai({'test': 'data'})
        except SystemExit as e:
            print(f"✅ Caught expected sys.exit({e.code}) from call_brain_direct.")
        
        # Verify calls
        calls = mock_url.call_args_list
        print(f"   Total Network Calls: {len(calls)}")
        
        telegram_called = False
        for call in calls:
            req = call[0][0]
            if "api.telegram.org" in req.full_url:
                telegram_called = True
                print(f"   ✅ SUCCESS: Telegram Alert attempted to URL: {req.full_url[:35]}...")

        if telegram_called:
            print("✅ TEST C PASSED: OpenAI failure triggered Telegram alert.")
        else:
            print("❌ TEST C FAILED: No Telegram alert attempted.")

    print("\n==================================================")
    print("ALL RESILIENCE TESTS COMPLETE")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_resilience_tests())
