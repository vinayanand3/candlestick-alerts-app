import unittest
from v4_engine.scoring_engine import evaluate_3layer_score
from v4_engine.config import V4_DEFAULT_CONFIG

class TestV4ScoringEngine(unittest.TestCase):
    def test_3layer_score_caps_when_no_setup(self):
        regime_data = {"regime": "TRENDING_UP", "min_separation_required": 15.0}
        trend_data = {"is_bull_stack": True}
        sr_data = {"near_support_bounce": True, "immediate_resistance_ahead": False}
        setup_data = {"active_setup": None, "score_bull": 0, "score_bear": 0, "setup_id": "NO_SETUP"}
        candle_data = {"score_bull": 15, "score_bear": 0, "is_bull_close": True}
        volume_data = {"rvol": 1.5}
        momentum_data = {"rsi": 60.0, "macd_hist": 0.5, "is_accelerating_bull": True, "divergence": {}}

        scoring = evaluate_3layer_score(
            regime_data, trend_data, sr_data, setup_data, candle_data, volume_data, momentum_data, V4_DEFAULT_CONFIG
        )

        # Because active_setup is None, Bull Score must be capped at 59.0
        self.assertLessEqual(scoring["bull_score"], 59.0)
        self.assertEqual(scoring["direction"], "NEUTRAL")

    def test_directional_separation_requirement(self):
        regime_data = {"regime": "RANGE", "min_separation_required": 16.0}
        trend_data = {"is_bull_stack": False, "is_bear_stack": False}
        sr_data = {"near_support_bounce": False, "near_res_rejection": False}
        setup_data = {
            "active_setup": {"setup_id": "SUPPORT_REJECTION", "direction": "CALL"},
            "score_bull": 20, "score_bear": 15, "setup_id": "SUPPORT_REJECTION"
        }
        candle_data = {"score_bull": 15, "score_bear": 15, "is_bull_close": True}
        volume_data = {"rvol": 1.0}
        momentum_data = {"rsi": 50.0, "macd_hist": 0.0, "divergence": {}}

        scoring = evaluate_3layer_score(
            regime_data, trend_data, sr_data, setup_data, candle_data, volume_data, momentum_data, V4_DEFAULT_CONFIG
        )

        # Bull score = 50.0, Bear score = 35.0, Separation = 15.0 (< 16.0) -> Direction is NEUTRAL
        self.assertLess(scoring["directional_separation"], 16.0)
        self.assertEqual(scoring["direction"], "NEUTRAL")

    def test_valid_call_signal(self):
        regime_data = {"regime": "TRENDING_UP", "min_separation_required": 14.0, "score_cap": 100.0}
        trend_data = {"is_bull_stack": True}
        sr_data = {"near_support_bounce": True, "immediate_resistance_ahead": False}
        setup_data = {
            "active_setup": {"setup_id": "PULLBACK_CONTINUATION", "direction": "CALL"},
            "score_bull": 20, "score_bear": 0, "setup_id": "PULLBACK_CONTINUATION"
        }
        candle_data = {"score_bull": 15, "score_bear": 0, "is_bull_close": True}
        volume_data = {"rvol": 1.5}
        momentum_data = {"rsi": 62.0, "macd_hist": 0.8, "is_accelerating_bull": True, "divergence": {"bullish": True}}

        scoring = evaluate_3layer_score(
            regime_data, trend_data, sr_data, setup_data, candle_data, volume_data, momentum_data, V4_DEFAULT_CONFIG
        )

        self.assertGreaterEqual(scoring["bull_score"], 75.0)
        self.assertGreaterEqual(scoring["directional_separation"], 14.0)
        self.assertEqual(scoring["direction"], "CALL")

if __name__ == "__main__":
    unittest.main()
