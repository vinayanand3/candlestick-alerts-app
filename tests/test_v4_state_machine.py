import unittest
from v4_engine.state_machine import SignalStateMachine
from v4_engine.config import V4_DEFAULT_CONFIG

class TestV4StateMachine(unittest.TestCase):
    def setUp(self):
        self.sm = SignalStateMachine(V4_DEFAULT_CONFIG)

    def test_ratcheting_chandelier_stop_loss_never_loosens(self):
        c1 = {"time": 1000, "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.8}
        scoring = {"direction": "CALL", "signal_score": 82.0, "setup_id": "BREAKOUT_RETEST"}
        risk = {
            "entry_price": 100.8, "entry_zone": "$100.60 - $101.00",
            "stop_loss": 98.8, "target_1": 103.0, "target_2": 105.0, "target_3": 108.0,
            "rr_t2": 2.1, "expected_value_r": 1.2, "risk_passed": True
        }
        regime = {"regime": "TRENDING_UP"}

        sig, events = self.sm.process_candle(c1, scoring, risk, regime, atr_val=1.5)
        self.assertIsNotNone(sig)
        self.assertEqual(sig["state"], "ACTIVE")
        self.assertEqual(sig["trailing_stop"], 98.8)

        # Price rallies: High = 104.0 (Hits Target 1)
        c2 = {"time": 2000, "open": 101.0, "high": 104.0, "low": 101.0, "close": 103.5}
        sig, events = self.sm.process_candle(c2, scoring, risk, regime, atr_val=1.5)
        self.assertTrue(sig["t1_hit"])
        # Stop must be at least breakeven (100.8)
        self.assertGreaterEqual(sig["trailing_stop"], 100.8)

        # Price pulls back slightly but ATR spikes: trailing stop must NOT move backwards
        c3 = {"time": 3000, "open": 103.5, "high": 103.6, "low": 102.0, "close": 102.5}
        prev_stop = sig["trailing_stop"]
        sig, events = self.sm.process_candle(c3, scoring, risk, regime, atr_val=3.0)
        self.assertGreaterEqual(sig["trailing_stop"], prev_stop)

    def test_structural_invalidation_override(self):
        c1 = {"time": 1000, "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.8}
        scoring = {"direction": "CALL", "signal_score": 85.0, "setup_id": "BREAKOUT_RETEST"}
        risk = {
            "entry_price": 100.8, "entry_zone": "$100.60 - $101.00",
            "stop_loss": 99.0, "target_1": 103.0, "target_2": 105.0, "target_3": 108.0,
            "rr_t2": 2.1, "expected_value_r": 1.2, "risk_passed": True
        }
        regime = {"regime": "TRENDING_UP"}

        sig, events = self.sm.process_candle(c1, scoring, risk, regime, atr_val=1.5)
        self.assertIsNotNone(sig)

        # Candle closes below invalidation level (99.0) even if mathematical score is still reported high
        c2 = {"time": 2000, "open": 100.0, "high": 100.2, "low": 98.5, "close": 98.7}
        sig, events = self.sm.process_candle(c2, scoring, risk, regime, atr_val=1.5)
        self.assertIsNone(sig)
        exit_event = next((e for e in events if e["type"] == "SIGNAL_EXIT"), None)
        self.assertIsNotNone(exit_event)

if __name__ == "__main__":
    unittest.main()
