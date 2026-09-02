import unittest
from v4_engine.backtester import run_backtest

class TestV4Backtester(unittest.TestCase):
    def test_backtest_execution_and_metrics(self):
        candles = []
        base = 100.0
        # Create a wave pattern of 60 candles
        for i in range(60):
            drift = 0.8 if (i % 6 < 4) else -0.5
            base += drift
            candles.append({
                "time": 1000 + (i * 900),
                "open": base,
                "high": base + 1.2,
                "low": base - 0.8,
                "close": base + 0.5,
                "volume": 3000 + (i * 50)
            })

        results = run_backtest(candles, symbol="NVDA")
        self.assertIsNotNone(results)
        self.assertIn("total_trades", results)
        self.assertIn("win_rate", results)
        self.assertIn("profit_factor", results)
        self.assertIn("expectancy_r", results)
        self.assertIn("by_regime", results)
        self.assertIn("by_setup", results)

if __name__ == "__main__":
    unittest.main()
