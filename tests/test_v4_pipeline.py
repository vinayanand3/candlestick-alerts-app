import unittest
from v4_engine.pipeline import V4Pipeline

class TestV4Pipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = V4Pipeline()

    def test_full_pipeline_analysis(self):
        candles = []
        base = 150.0
        for i in range(40):
            c_open = base + (i * 0.5)
            c_close = c_open + 0.4
            candles.append({
                "time": 1000 + (i * 60),
                "open": c_open,
                "high": c_close + 0.3,
                "low": c_open - 0.2,
                "close": c_close,
                "volume": 2000
            })
        
        # Add high volume breakout candle
        c_open = candles[-1]["close"]
        candles.append({
            "time": 1000 + (40 * 60),
            "open": c_open,
            "high": c_open + 3.0,
            "low": c_open - 0.2,
            "close": c_open + 2.8,
            "volume": 6000
        })

        analysis = self.pipeline.analyze(candles, symbol="TSLA", timeframe="15m")
        self.assertIsNotNone(analysis)
        self.assertIn("regime", analysis)
        self.assertIn("scoring", analysis)
        self.assertIn("explainability", analysis)
        self.assertIn("reason_codes", analysis["explainability"])
        self.assertIn("why_direction", analysis["explainability"]["explainability"])
        self.assertIn("why_now", analysis["explainability"]["explainability"])
        self.assertIn("targets", analysis["explainability"]["explainability"])

if __name__ == "__main__":
    unittest.main()
