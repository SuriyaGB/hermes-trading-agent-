import sys
import json
import os
import asyncio
import time
from pathlib import Path
from datetime import datetime
import csv
import math
from ib_insync import IB, Stock, Option, LimitOrder, MarketOrder, util

util.patchAsyncio() # The Hammer: Allow nested loops

# CONFIG
PROJECT_ROOT = Path(__file__).parent.parent
STATE_PATH = PROJECT_ROOT / 'data' / 'trade_state.json'
LOG_PATH = PROJECT_ROOT / 'data' / 'trades_log.csv'
LOCK_FILE = PROJECT_ROOT / 'logs' / 'executor.lock'

IB_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IBKR_PORT", 7497))
CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", 10))

def extract_decision(raw_input: str) -> dict | None:
    """
    Professional Stack-Based JSON Extractor.
    Finds balanced { } pairs to handle multi-line and log interference.
    """
    candidates = []
    depth = 0
    start = -1
    
    for i, char in enumerate(raw_input):
        if char == '{':
            if depth == 0:
                start = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start != -1:
                # We found a complete balanced block
                candidate = raw_input[start:i+1].strip()
                candidates.append(candidate)
                start = -1
                
    # Scan candidates from LAST to FIRST (Decision is always last)
    for candidate in reversed(candidates):
        try:
            data = json.loads(candidate)
            # Validation: Must be a dict and have the 'decision' key
            if isinstance(data, dict) and 'decision' in data:
                return data
        except json.JSONDecodeError:
            continue
            
    return None

def load_state():
    default_state = {"current_phase": "CASH_ONLY", "current_cycle_put_premium": None}
    try:
        if STATE_PATH.exists():
            with open(STATE_PATH, 'r') as f:
                return json.load(f)
        return default_state
    except:
        return default_state

def save_state(state):
    state['last_pulse_timestamp'] = datetime.now().isoformat()
    # Save the current state
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)
    # Append to History Log (The "Time Machine")
    HISTORY_PATH = PROJECT_ROOT / 'data' / 'trade_state_history.jsonl'
    with open(HISTORY_PATH, 'a') as f:
        f.write(json.dumps(state) + '\n')

def append_to_log(action, symbol, strike, price, premium):
    header = ['timestamp', 'action', 'symbol', 'strike', 'price', 'premium_collected']
    file_exists = LOG_PATH.exists()
    with open(LOG_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow([datetime.now().isoformat(), action, symbol, strike, price, premium])

async def wait_for_fill(ib, trade, timeout_sec=120):
    start_time = datetime.now()
    while (datetime.now() - start_time).total_seconds() < timeout_sec:
        await ib.sleep(2)
        if trade.orderStatus.status == 'Filled':
            return True
        if trade.orderStatus.status in ['Cancelled', 'Inactive', 'Rejected']:
            print(f"[EXECUTOR] Order terminated with status: {trade.orderStatus.status}")
            return False
    return False

async def get_valid_expiry(ib, symbol, target_dte):
    stock = Stock(symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(stock)
    chains = await ib.reqSecDefOptParamsAsync(stock.symbol, '', stock.secType, stock.conId)
    chain = next((c for c in chains if c.exchange == 'SMART'), None)
    if not chain: return None

    expiries = sorted(chain.expirations)
    today = datetime.now()
    best_exp = None
    min_diff = 999
    
    for e in expiries:
        exp_dt = datetime.strptime(e, '%Y%m%d')
        actual_dte = (exp_dt - today).days
        if 30 <= actual_dte <= 50: 
             diff = abs(actual_dte - target_dte)
             if diff < min_diff:
                 min_diff = diff
                 best_exp = e
    return best_exp

async def execute_decision(decision_data: dict):
    # --- FIX 1: STALE LOCK DETECTION ---
    if LOCK_FILE.exists():
        lock_age = time.time() - LOCK_FILE.stat().st_mtime
        if lock_age > 600: # 10 minute threshold
            print("[EXECUTOR] WARNING: Removing stale lock from a previous crashed run.")
            LOCK_FILE.unlink()
        else:
            print("[EXECUTOR] ABORT: Another process is already running. Skipping pulse.")
            return
    LOCK_FILE.touch()

    decision = decision_data.get("decision")
    print(f"\n[EXECUTOR] Process Starting: {decision}")
    ib = IB()
    try:
        await ib.connectAsync(IB_HOST, IB_PORT, clientId=CLIENT_ID)
        ib.reqMarketDataType(3) # Enable free delayed data
        state = load_state()

        if decision == "ABORT_DUE_TO_RISK":
            # --- FIX 4: ASYNC ABORT ---
            print("[EXECUTOR] CRITICAL: Liquidating AAPL positions.")
            pos_list = await ib.reqPositionsAsync()
            aapl_positions = [p for p in pos_list if p.contract.symbol == 'AAPL']
            for p in aapl_positions:
                side = 'SELL' if p.position > 0 else 'BUY'
                ib.placeOrder(p.contract, MarketOrder(side, abs(p.position)))
            state['current_phase'] = "CASH_ONLY"
            save_state(state)
            return

        if decision in ["SELL_NEW_PUT", "SELL_NEW_CALL"]:
            strike = decision_data.get("strike_held")
            target_dte = decision_data.get("dte_seen") or 45
            if not strike: return
            expiry = await get_valid_expiry(ib, 'AAPL', target_dte)
            if expiry is None:
                print("[EXECUTOR] ABORT: No valid monthly expiry found (30-50 DTE).")
                return

            right = 'P' if decision == "SELL_NEW_PUT" else 'C'
            contract = Option('AAPL', expiry, strike, right, 'SMART')
            await ib.qualifyContractsAsync(contract)
            [ticker] = await ib.reqTickersAsync(contract)
            
            # --- FIX 2: PRICE GUARDS ---
            if ticker.bid > 0 and ticker.ask > 0:
                mid_price = round((ticker.bid + ticker.ask) / 2, 2)
            elif ticker.ask > 0:
                mid_price = round(ticker.ask * 0.98, 2)
            else:
                print("[EXECUTOR] ABORT: No valid market data for new position.")
                return

            trade = ib.placeOrder(contract, LimitOrder('SELL', 1, mid_price))
            if await wait_for_fill(ib, trade):
                fill_p = trade.orderStatus.avgFillPrice
                try:
                    if right == 'P': 
                        state['current_cycle_put_premium'] = fill_p
                        state['assignment_strike'] = strike
                    state['current_option_strike'] = strike
                    state['current_option_expiry'] = expiry
                    state['current_phase'] = "CSP_ACTIVE" if right == 'P' else "CC_ACTIVE"
                    append_to_log(decision, 'AAPL', strike, fill_p, fill_p if right == 'P' else 0)
                finally:
                    save_state(state)
                    print("[EXECUTOR] State saved safely after fill.")
            else:
                ib.cancelOrder(trade.order)
            return

        if decision in ["CLOSE_FOR_PROFIT", "CLOSE_FOR_LOSS"]:
            pos_list = await ib.reqPositionsAsync()
            opt_pos = [p for p in pos_list if isinstance(p.contract, Option) and p.contract.symbol == 'AAPL']
            if opt_pos:
                contract = opt_pos[0].contract
                if not contract.exchange: contract.exchange = 'SMART'
                await ib.qualifyContractsAsync(contract)
                [ticker] = await ib.reqTickersAsync(contract)
                
                # --- STUTTER GUARD ---
                active_trades = [t for t in ib.trades() if t.contract.conId == contract.conId and t.isActive()]
                if active_trades:
                    print(f"[EXECUTOR] Stutter-Guard: Found existing active order {active_trades[0].order.orderId}. Monitoring existing order instead of placing new one.")
                    trade = active_trades[0]
                else:
                    # --- FIX 2: PRICE GUARDS ---
                    if ticker.bid > 0 and ticker.ask > 0:
                        mid_p = round((ticker.bid + ticker.ask) / 2, 2)
                    elif ticker.ask > 0:
                        mid_p = round(ticker.ask * 1.02, 2) # Limit buy higher
                    else: 
                        print("[EXECUTOR] ABORT: No valid market data for closing.")
                        return
                    trade = ib.placeOrder(contract, LimitOrder('BUY', 1, mid_p))
                if await wait_for_fill(ib, trade):
                    fill_p = trade.orderStatus.avgFillPrice
                    try:
                        state['current_phase'] = "CASH_ONLY"
                        state['current_cycle_put_premium'] = None
                        state['current_option_strike'] = None
                        state['current_option_expiry'] = None
                        append_to_log(decision, 'AAPL', contract.strike, fill_p, 0)
                    finally:
                        save_state(state)
                        print("[EXECUTOR] State saved safely after close.")
            return

        if decision.startswith("HOLD_"):
            state['last_decision'] = decision
            save_state(state)
            return

        if decision in ["ROLL_PUT", "ROLL_CALL"]:
            print(f"[EXECUTOR] Autopilot: Executing sequential ROLL for {decision}")
            # Step 1: Close Current
            pos_list = await ib.reqPositionsAsync()
            opt_pos = [p for p in pos_list if isinstance(p.contract, Option) and p.contract.symbol == 'AAPL']
            if opt_pos:
                curr_contract = opt_pos[0].contract
                if not curr_contract.exchange: curr_contract.exchange = 'SMART'
                await ib.qualifyContractsAsync(curr_contract)
                [t] = await ib.reqTickersAsync(curr_contract)
                
                # --- FIX 2: PRICE GUARDS ---
                if t.bid > 0 and t.ask > 0:
                    mid = round((t.bid + t.ask) / 2, 2)
                elif t.ask > 0:
                    mid = round(t.ask * 1.02, 2)
                else:
                    print("[EXECUTOR] ROLL ABORT: Market data blackout on step 1.")
                    return

                close_trade = ib.placeOrder(curr_contract, LimitOrder('BUY', 1, mid))
                print(f"[EXECUTOR] Closing position {curr_contract.localSymbol}...")
                if await wait_for_fill(ib, close_trade):
                    try:
                        print("[EXECUTOR] Step 1 Complete: Position Closed.")
                        state['current_phase'] = "CASH_ONLY"
                        state['current_option_strike'] = None
                        state['current_option_expiry'] = None
                    finally:
                        save_state(state)
                else:
                    print("[EXECUTOR] ROLL ABORTED: Failed to close current position.")
                    ib.cancelOrder(close_trade.order)
                    return

            # Step 2: Open New
            target_strike = decision_data.get("strike_held")
            target_dte = 45 # Default to next monthly
            expiry = await get_valid_expiry(ib, 'AAPL', target_dte)
            if not expiry or not target_strike:
                 print("[EXECUTOR] ROLL ERROR: Cannot find next expiry or strike.")
                 return
            
            right = 'P' if "PUT" in decision else 'C'
            new_contract = Option('AAPL', expiry, target_strike, right, 'SMART')
            await ib.qualifyContractsAsync(new_contract)
            [t_new] = await ib.reqTickersAsync(new_contract)
            
            # --- FIX 2: PRICE GUARDS ---
            if t_new.bid > 0 and t_new.ask > 0:
                mid_new = round((t_new.bid + t_new.ask) / 2, 2)
            elif t_new.ask > 0:
                mid_new = round(t_new.ask * 0.98, 2)
            else:
                print("[EXECUTOR] ROLL ABORT: Market data blackout on step 2.")
                # --- FIX 3: ROLL STATE RESET ---
                state['current_phase'] = "CASH_ONLY"
                state['current_option_strike'] = None
                state['current_option_expiry'] = None
                save_state(state)
                return
            
            print(f"[EXECUTOR] Opening new position {new_contract.localSymbol} at ${mid_new}...")
            open_trade = ib.placeOrder(new_contract, LimitOrder('SELL', 1, mid_new))
            if await wait_for_fill(ib, open_trade):
                 fill_p = open_trade.orderStatus.avgFillPrice
                 try:
                     state['current_phase'] = "CSP_ACTIVE" if right == 'P' else "CC_ACTIVE"
                     state['current_option_strike'] = target_strike
                     state['current_option_expiry'] = expiry
                     append_to_log(decision, 'AAPL', target_strike, fill_p, fill_p if right == 'P' else 0)
                 finally:
                     save_state(state)
                     print("[EXECUTOR] ROLL COMPLETE: New position active and state saved.")
            else:
                 # --- FIX 3: ROLL STATE RESET ---
                 ib.cancelOrder(open_trade.order)
                 print("[EXECUTOR] ROLL PARTIAL FAILURE: Position closed but new one not opened.")
                 try:
                     state['current_phase'] = "CASH_ONLY"
                     state['current_option_strike'] = None
                     state['current_option_expiry'] = None
                 finally:
                     save_state(state)
            return

    except Exception as e:
        print(f"[EXECUTOR] Error: {str(e)}")
    finally:
        # --- FIX 5: LOCK FILE CLEANUP ---
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
        ib.disconnect()

if __name__ == "__main__":
    try:
        raw_input = sys.stdin.read()
        decision_data = extract_decision(raw_input)
        if decision_data:
            ib = IB()
            ib.run(execute_decision(decision_data))
        else:
            print("[EXECUTOR] ERROR: No valid JSON decision found in input.")
    except Exception as e:
        print(f"CRITICAL: {str(e)}")
