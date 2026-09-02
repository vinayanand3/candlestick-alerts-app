import unittest
from qqq_macro_v4 import V4QQQMacroRotationEngine

class TestV4QQQMacroRotation(unittest.TestCase):
    def setUp(self):
        self.engine = V4QQQMacroRotationEngine(confirmation_days=2, hysteresis_pct=0.5)

    def test_continuous_bear_depth_scaling(self):
        qqq_candles = []
        c_price = 450.0
        for i in range(35):
            c_price -= 0.1
            qqq_candles.append({
                "time": 1000 + (i * 86400),
                "open": c_price,
                "high": c_price + 0.5,
                "low": c_price - 0.5,
                "close": c_price,
                "volume": 50000
            })
        for i in range(35):
            c_price -= 4.0
            qqq_candles.append({
                "time": 1000 + ((35 + i) * 86400),
                "open": c_price + 2.0,
                "high": c_price + 2.5,
                "low": c_price - 1.0,
                "close": c_price,
                "volume": 70000
            })
        analysis = self.engine.analyze(qqq_candles)
        self.assertEqual(analysis["macro_regime"]["regime"], "BEAR MARKET")
        sqqq_alloc = analysis["macro_telemetry"]["s9_bear_depth_pct"]
        self.assertGreaterEqual(sqqq_alloc, 40)
        self.assertLessEqual(sqqq_alloc, 100)

    def test_hysteresis_buffer_prevents_flip_on_minor_fluctuation(self):
        # SPY hovering +/- 0.2% around 200 SMA (within 0.5% hysteresis)
        qqq_candles = []
        c_price = 350.0
        for i in range(50):
            drift = 0.2 if (i % 2 == 0) else -0.1
            c_price += drift
            qqq_candles.append({
                "time": 1000 + (i * 86400),
                "open": c_price,
                "high": c_price + 0.3,
                "low": c_price - 0.3,
                "close": c_price,
                "volume": 50000
            })
        analysis = self.engine.analyze(qqq_candles)
        self.assertEqual(analysis["macro_regime"]["regime"], "BULL MARKET")

if __name__ == "__main__":
    unittest.main()
