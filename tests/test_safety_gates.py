import unittest
import json
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# Import the core modules under test
import core.executor as executor
import core.get_ibkr_analysis as analysis
from core.utils import PolicyBlockError, PacingBlockError

# Setup temporary paths for testing (within workspace)
TEST_DIR = Path(__file__).parent
TEMP_DATA_DIR = TEST_DIR / "temp_data"

# Patch the path constants in the core modules to point to temp_data
executor.TRACKER_PATH = TEMP_DATA_DIR / "intraday_tracker.json"
executor.PORTFOLIO_PATH = TEMP_DATA_DIR / "portfolio.json"
executor.STATE_PATH = TEMP_DATA_DIR / "trade_state.json"
executor.MEMORY_PATH = TEMP_DATA_DIR / "MEMORY.md"

analysis.TRACKER_PATH = executor.TRACKER_PATH
analysis.PORTFOLIO_PATH = executor.PORTFOLIO_PATH

class TestSafetyGates(unittest.TestCase):

    def setUp(self):
        # Re-create temp directory before each test
        TEMP_DATA_DIR.mkdir(exist_ok=True)
            
        # Write default mock portfolio
        self.mock_portfolio = {
            "total_cash": 250000.0,
            "positions": [],
            "portfolio_summary": {
                "current_risk_units": 1
            }
        }
        with open(executor.PORTFOLIO_PATH, "w") as f:
            json.dump(self.mock_portfolio, f)

    def tearDown(self):
        # Clean up temp files
        shutil.rmtree(TEMP_DATA_DIR, ignore_errors=True)

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY A: Pure Unit Tests for Deterministic Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def test_tracker_date_uses_market_day(self):
        """
        Test that get_market_date resolves to the US Eastern date
        even if local system clock rolls over to the next day in IST.
        """
        # Scenario: UTC is 2026-06-01 19:00:00. IST is 2026-06-02 00:30:00.
        # dt represents naive datetime from local system clock (IST)
        dt_ist = datetime(2026, 6, 2, 0, 30, 0)
        
        # Expected: Market date must remain 2026-06-01 (US Eastern)
        market_day = executor.get_market_date(dt_ist)
        self.assertEqual(market_day, "2026-06-01")

    def test_option_price_falls_back_from_wide_spread(self):
        """
        Test that calculate_midpoint uses last_price when bid/ask spread
        is excessively wide (off-hours stale quotes), and uses midpoint otherwise.
        """
        # Case 1: Normal Spread -> should use midpoint
        # (2.20 + 2.40)/2 = 2.30
        normal_price = analysis.calculate_midpoint(bid=2.20, ask=2.40, last_price=2.35)
        self.assertEqual(normal_price, 2.30)
        
        # Case 2: Wide Spread (> 50% bid) -> should use lastPrice
        wide_price = analysis.calculate_midpoint(bid=2.00, ask=6.00, last_price=2.35)
        self.assertEqual(wide_price, 2.35)

    def test_calculate_midpoint_invalid_pricing(self):
        """
        Test that calculate_midpoint falls back to last_price when bid/ask
        quotes are zero, negative, or otherwise invalid.
        """
        # Zero bid/ask
        self.assertEqual(analysis.calculate_midpoint(bid=0.0, ask=0.0, last_price=1.45), 1.45)
        # Negative bid
        self.assertEqual(analysis.calculate_midpoint(bid=-0.50, ask=2.00, last_price=1.45), 1.45)
        # Zero ask
        self.assertEqual(analysis.calculate_midpoint(bid=1.00, ask=0.0, last_price=1.45), 1.45)

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY B: Validation Tests for Executor Decisions
    # ─────────────────────────────────────────────────────────────────────────
    def test_normal_day_blocks_second_put(self):
        """
        Test that a 2nd contract is strictly blocked on a NORMAL_DAY.
        Scenario: written = 1, day_class = NORMAL_DAY, AI tries to sell another put.
        Expected: Rejection and soft override to HOLD_PUT_POSITION.
        """
        tracker_data = {
            "date": executor.get_market_date(),
            "contracts_written_today": 1,
            "first_strike": 290.0,
            "first_premium": 3.17
        }
        with open(executor.TRACKER_PATH, "w") as f:
            json.dump(tracker_data, f)

        dec = {
            "decision": "SELL_NEW_PUT",
            "strike_to_trade": 285.0,
            "premium_to_collect": 3.20
        }
        
        eye_data = {
            "market_regime": {
                "day_classification": "NORMAL_DAY"
            },
            "portfolio_summary": {
                "current_risk_units": 1
            }
        }

        new_dec, overridden = executor.validate_single_decision(dec, eye_data, self.mock_portfolio)
        self.assertTrue(overridden)
        self.assertEqual(new_dec.get("decision"), "HOLD_PUT_POSITION")
        self.assertIn("Pacing Block: Daily cap (1) reached", new_dec.get("reason", ""))

    def test_good_day_requires_better_option(self):
        """
        Test that a 2nd contract on a GOOD_DAY is subject to the Better Option check.
        Scenario: written = 1, day_class = GOOD_DAY, AI tries strike 295.0 (>= first_strike 290.0).
        Expected: Rejection and soft override to HOLD_PUT_POSITION because strike is not lower.
        """
        tracker_data = {
            "date": executor.get_market_date(),
            "contracts_written_today": 1,
            "first_strike": 290.0,
            "first_premium": 3.17
        }
        with open(executor.TRACKER_PATH, "w") as f:
            json.dump(tracker_data, f)

        dec = {
            "decision": "SELL_NEW_PUT",
            "strike_to_trade": 295.0,
            "premium_to_collect": 3.45
        }
        
        eye_data = {
            "market_regime": {
                "day_classification": "GOOD_DAY"
            },
            "portfolio_summary": {
                "current_risk_units": 1
            }
        }

        new_dec, overridden = executor.validate_single_decision(dec, eye_data, self.mock_portfolio)
        self.assertTrue(overridden)
        self.assertEqual(new_dec.get("decision"), "HOLD_PUT_POSITION")
        self.assertIn("Pacing Block: Better Option check failed", new_dec.get("reason", ""))

    def test_pacing_rejection_soft_overrides_to_hold(self):
        """
        Test that when validation fails, it does NOT throw a script-terminating exception
        but soft overrides the decision to HOLD_PUT_POSITION.
        """
        tracker_data = {
            "date": executor.get_market_date(),
            "contracts_written_today": 1,
            "first_strike": 290.0,
            "first_premium": 3.17
        }
        with open(executor.TRACKER_PATH, "w") as f:
            json.dump(tracker_data, f)

        dec = {
            "decision": "SELL_NEW_PUT",
            "strike_to_trade": 295.0,
            "premium_to_collect": 3.45
        }
        
        eye_data = {
            "market_regime": {
                "day_classification": "GOOD_DAY"
            },
            "portfolio_summary": {
                "current_risk_units": 1
            }
        }

        # Validate decision: should return overridden dict instead of raising error
        new_dec, overridden = executor.validate_single_decision(dec, eye_data, self.mock_portfolio)
        self.assertTrue(overridden)
        self.assertEqual(new_dec.get("decision"), "HOLD_PUT_POSITION")
        self.assertIn("Pacing Block", new_dec.get("reason", ""))

    def test_policy_block_retains_hard_failure(self):
        """
        Test that a Policy Block violation (e.g. max risk units exceeded) still raises
        a PolicyBlockError (and is not soft-overridden to HOLD).
        """
        dec = {
            "decision": "SELL_NEW_PUT",
            "strike_to_trade": 285.0,
            "premium_to_collect": 3.20
        }
        
        eye_data = {
            "market_regime": {
                "day_classification": "NORMAL_DAY"
            },
            "portfolio_summary": {
                "current_risk_units": 4  # Capped at 4 for NORMAL_DAY
            }
        }
        
        # Current portfolio has risk units already at max allowed (4)
        portfolio = {
            "portfolio_summary": {
                "current_risk_units": 4
            }
        }

        with self.assertRaises(PolicyBlockError):
            executor.validate_single_decision(dec, eye_data, portfolio)

    def test_roll_put_policy_boundary(self):
        """
        Test that rolling a put when DTE <= 15 and Delta >= 0.30 raises a PolicyBlockError.
        """
        dec = {
            "decision": "ROLL_PUT",
            "position_key": "AAPL_260619P00290000",
            "close_strike": 290.0
        }
        
        eye_data = {
            "active_positions": [{
                "type": "Option",
                "position_key": "AAPL_260619P00290000",
                "strike": 290.0,
                "delta": 0.35,
                "dte": 10
            }]
        }

        with self.assertRaises(PolicyBlockError):
            executor.validate_single_decision(dec, eye_data, self.mock_portfolio)

    def test_scan_capacity_normal_day_cap_is_one(self):
        """
        Test that daily_cap in scan_capacity is exactly 1 for a NORMAL_DAY.
        """
        # Setup tracker with contracts_written_today = 1
        tracker_data = {
            "date": executor.get_market_date(),
            "contracts_written_today": 1,
            "first_strike": 290.0,
            "first_premium": 3.17
        }
        with open(executor.TRACKER_PATH, "w") as f:
            json.dump(tracker_data, f)

        # Force mock values for market regimes to isolate cap logic
        with patch('core.get_ibkr_analysis.get_vix', return_value=16.0), \
             patch('core.get_ibkr_analysis.get_earnings_days', return_value=60), \
             patch('core.get_ibkr_analysis.get_recent_news', return_value=[]), \
             patch('core.get_ibkr_analysis.get_sma_200', return_value=260.0), \
             patch('core.get_ibkr_analysis.get_sma_50', return_value=270.0), \
             patch('core.get_ibkr_analysis.get_yf_option_chain') as mock_chain, \
             patch('core.get_ibkr_analysis.yf.Ticker') as mock_ticker:

            mock_t = MagicMock()
            mock_t.fast_info = {'lastPrice': 300.0, 'previousClose': 301.5}
            mock_ticker.return_value = mock_t

            mock_chain.return_value = {
                "option_chain": [{"strike": 300.0, "iv": 18.0}],
                "chosen_expiry": "20260717",
                "chosen_dte": 45
            }

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            data = loop.run_until_complete(analysis.fetch_analysis_data())
            loop.close()

            # Verify regime classification
            self.assertEqual(data["market_regime"]["day_classification"], "NORMAL_DAY")
            # Verify capacity is 0 because cap is 1 and written is 1
            self.assertEqual(data["scan_capacity"]["daily_cap_remaining"], 0)

    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY C: Integration Tests
    # ─────────────────────────────────────────────────────────────────────────
    @patch('core.utils.datetime')
    def test_eye_and_executor_share_same_market_day_view(self, mock_utils_dt):
        """
        Verify that both Eye (analysis.py) and Executor (executor.py) resolve
        to the exact same market day when system clock rolls over to next day.
        """
        # Scenario: Clock is 2026-06-02 00:30:00 IST (June 1 EST)
        mock_now = datetime(2026, 6, 2, 0, 30, 0)
        mock_utils_dt.now.return_value = mock_now
        mock_utils_dt.strftime = datetime.strftime

        # 1. Eye starts: loads or initializes tracker
        eye_tracker = analysis.get_intraday_tracker()
        
        # 2. Executor starts: resets and loads tracker
        exec_tracker = executor.reset_and_load_tracker()

        # Both must see the exact same date ("2026-06-01")
        self.assertEqual(eye_tracker.get("date"), "2026-06-01")
        self.assertEqual(exec_tracker.get("date"), "2026-06-01")
        self.assertEqual(eye_tracker.get("date"), exec_tracker.get("date"))

if __name__ == "__main__":
    unittest.main()
