import unittest
from unittest.mock import patch

from v4_engine.pipeline import V4Pipeline


def make_candles(base: float):
    candles = []
    for i in range(40):
        open_price = base + (i * 0.25)
        close_price = open_price + 0.15
        candles.append(
            {
                "time": 1_700_000_000 + (i * 900),
                "open": open_price,
                "high": close_price + 0.20,
                "low": open_price - 0.20,
                "close": close_price,
                "volume": 2_000 + (i * 10),
            }
        )
    return candles


class TestPollingIsolation(unittest.TestCase):
    def test_repeated_poll_is_deterministic(self):
        pipeline = V4Pipeline()
        candles = make_candles(100.0)

        first = pipeline.analyze(candles, symbol="TSLA", timeframe="15m")
        second = pipeline.analyze(candles, symbol="TSLA", timeframe="15m")

        self.assertEqual(first, second)

    def test_each_analysis_uses_fresh_state_machine(self):
        real_state_machine = __import__(
            "v4_engine.state_machine", fromlist=["SignalStateMachine"]
        ).SignalStateMachine
        instances = []

        class TrackingStateMachine(real_state_machine):
            def __init__(self, config):
                super().__init__(config)
                instances.append(self)

        pipeline = V4Pipeline()
        with patch("v4_engine.pipeline.SignalStateMachine", TrackingStateMachine):
            pipeline.analyze(make_candles(100.0), symbol="TSLA", timeframe="15m")
            pipeline.analyze(make_candles(200.0), symbol="AAPL", timeframe="15m")

        self.assertEqual(len(instances), 2)
        self.assertIsNot(instances[0], instances[1])


if __name__ == "__main__":
    unittest.main()
