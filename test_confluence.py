import unittest
from confluence_engine import ConfluenceAlertEngine, classify_market_regime, identify_key_levels

class TestConfluenceEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ConfluenceAlertEngine(min_confidence=75.0, min_rr_ratio=1.8)

    def test_bullish_confluence_score_and_alert(self):
        candles = []
        base = 200.0
        for i in range(40):
            c_open = base + (i * 0.8)
            c_close = c_open + 0.6
            candles.append({
                "time": 1000 + (i * 60),
                "open": c_open,
                "high": c_close + 0.3,
                "low": c_open - 0.2,
                "close": c_close,
                "volume": 1000
            })
        
        last_open = candles[-1]["close"]
        candles.append({
            "time": 1000 + (40 * 60),
            "open": last_open - 0.5,
            "high": last_open + 3.0,
            "low": last_open - 0.6,
            "close": last_open + 2.8,
            "volume": 3500
        })

        analysis = self.engine.analyze(candles, symbol="TSLA")
        self.assertIsNotNone(analysis)
        self.assertIn("current_score", analysis)
        score = analysis["current_score"]
        self.assertGreaterEqual(score["bull_score"], 6)
        self.assertEqual(score["direction"], "CALL")
        self.assertGreaterEqual(score["confidence"], 70.0)

    def test_market_regime_trending_up(self):
        candles = []
        for i in range(30):
            c_close = 150.0 + (i * 1.5)
            candles.append({
                "time": 1000 + i * 60,
                "open": c_close - 1.0,
                "high": c_close + 0.5,
                "low": c_close - 1.2,
                "close": c_close,
                "volume": 1200
            })
        closes = [c["close"] for c in candles]
        from confluence_engine import calculate_ema, calculate_atr
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        ema50 = calculate_ema(closes, 50)
        atr = calculate_atr(candles, 14)
        
        regime = classify_market_regime(candles, ema9, ema21, ema50, atr)
        self.assertEqual(regime["regime"], "TRENDING UP")

    def test_signal_state_machine_with_trailing_stop_and_targets(self):
        candles = []
        for i in range(35):
            c_open = 100.0 + (i * 0.5)
            c_close = c_open + 0.4
            candles.append({
                "time": 1000 + (i * 60),
                "open": c_open,
                "high": c_close + 0.2,
                "low": c_open - 0.2,
                "close": c_close,
                "volume": 1000
            })
        
        # High volume breakout with strong expansion
        candles.append({
            "time": 1000 + (35 * 60),
            "open": candles[-1]["close"],
            "high": candles[-1]["close"] + 3.0,
            "low": candles[-1]["close"] - 0.1,
            "close": candles[-1]["close"] + 2.8,
            "volume": 4000
        })

        analysis = self.engine.analyze(candles, symbol="NVDA")
        self.assertIn("alerts", analysis)
        self.assertTrue(len(analysis["alerts"]) >= 1)
        confirmed_alert = next((a for a in analysis["alerts"] if a["type"] == "SIGNAL_CONFIRMED"), None)
        self.assertIsNotNone(confirmed_alert)
        self.assertEqual(confirmed_alert["direction"], "CALL")
        self.assertIn("entry_zone", confirmed_alert)
        self.assertIn("invalidation", confirmed_alert)
        self.assertIn("target", confirmed_alert)

    def test_spam_suppression(self):
        candles = []
        for i in range(45):
            c_open = 100.0 + (i * 0.5)
            c_close = c_open + 0.4
            candles.append({
                "time": 1000 + (i * 60),
                "open": c_open,
                "high": c_close + 0.2,
                "low": c_open - 0.2,
                "close": c_close,
                "volume": 2000
            })
        analysis = self.engine.analyze(candles, symbol="AAPL")
        self.assertLessEqual(len(analysis["alerts"]), 4)

if __name__ == "__main__":
    unittest.main()
