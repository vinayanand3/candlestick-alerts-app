import unittest
from qqq_engine import QQQMacroRotationEngine

class TestQQQRotationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = QQQMacroRotationEngine(confirmation_days=2)

    def test_bull_regime_default_state_1(self):
        # Oscillating natural uptrend keeping RSI in normal 50-65 range
        qqq_candles = []
        c_price = 350.0
        for i in range(60):
            # Up-down waves with net positive drift
            drift = 1.0 if (i % 2 == 0) else -0.3
            c_price += drift
            qqq_candles.append({
                "time": 1000 + (i * 86400),
                "open": c_price - 0.5,
                "high": c_price + 0.8,
                "low": c_price - 0.6,
                "close": c_price,
                "volume": 50000
            })
        analysis = self.engine.analyze(qqq_candles)
        self.assertEqual(analysis["macro_regime"]["regime"], "BULL MARKET")
        self.assertEqual(analysis["active_state"]["state_id"], 1)
        self.assertEqual(analysis["active_state"]["allocation"]["TQQQ"], 100)

    def test_bull_regime_overbought_hedge_state_2(self):
        # Setup base candles
        qqq_candles = []
        c_price = 350.0
        for i in range(40):
            drift = 0.5 if (i % 2 == 0) else -0.2
            c_price += drift
            qqq_candles.append({
                "time": 1000 + (i * 86400),
                "open": c_price,
                "high": c_price + 0.5,
                "low": c_price - 0.5,
                "close": c_price,
                "volume": 50000
            })
        # Parabolic surge over 5 consecutive days pushing TQQQ RSI >= 80
        for j in range(5):
            c_price += 15.0
            qqq_candles.append({
                "time": 1000 + ((40 + j) * 86400),
                "open": c_price - 14.0,
                "high": c_price + 1.0,
                "low": c_price - 14.0,
                "close": c_price,
                "volume": 90000
            })
        analysis = self.engine.analyze(qqq_candles)
        self.assertEqual(analysis["macro_regime"]["regime"], "BULL MARKET")
        self.assertEqual(analysis["active_state"]["state_id"], 2)
        self.assertEqual(analysis["active_state"]["allocation"]["TQQQ"], 50)
        self.assertEqual(analysis["active_state"]["allocation"]["SQQQ"], 50)

    def test_2day_persistence_filter(self):
        qqq_candles = []
        c_price = 300.0
        for i in range(40):
            drift = 0.5 if (i % 2 == 0) else -0.2
            c_price += drift
            qqq_candles.append({
                "time": 1000 + (i * 86400),
                "open": c_price,
                "high": c_price + 0.5,
                "low": c_price - 0.5,
                "close": c_price,
                "volume": 50000
            })
        # Exactly 1 day of overbought spike
        c_price += 25.0
        qqq_candles.append({
            "time": 1000 + (41 * 86400),
            "open": c_price - 24.0,
            "high": c_price,
            "low": c_price - 24.0,
            "close": c_price,
            "volume": 90000
        })
        analysis = self.engine.analyze(qqq_candles)
        # Because it only lasted 1 day, confirmed state remains 1
        self.assertEqual(analysis["active_state"]["state_id"], 1)
        self.assertTrue(analysis["active_state"]["is_pending_transition"])

    def test_bear_regime_s9_adaptive_scaling(self):
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
        # Continuous decline dropping below 200 SMA
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
        self.assertGreater(analysis["macro_telemetry"]["s9_bear_depth_pct"], 0)

if __name__ == "__main__":
    unittest.main()
