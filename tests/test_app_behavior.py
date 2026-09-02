import json
import unittest
from unittest.mock import patch

import app


class TestAppBehavior(unittest.TestCase):
    def setUp(self):
        app._market_data_cache.clear()

    def test_live_data_failure_does_not_silently_simulate(self):
        with patch("app.fetch_equity_candles", return_value=[]):
            response = app.get_market_analysis("TSLA", "15m", "auto")

        self.assertEqual(response.status_code, 503)
        body = json.loads(response.body)
        self.assertEqual(body["source"], "unavailable")
        self.assertTrue(body["simulation_available"])

    def test_simulation_is_available_only_when_selected(self):
        response = app.get_market_analysis("TSLA", "15m", "simulate")

        self.assertEqual(response["source"], "simulation")
        self.assertEqual(response["symbol"], "TSLA")
        self.assertEqual(len(response["candles"]), 100)

    def test_simulated_candles_have_valid_ohlc_bounds(self):
        candles = app.generate_simulated_market("TSLA", num_candles=100)

        for candle in candles:
            self.assertGreaterEqual(candle["high"], max(candle["open"], candle["close"]))
            self.assertLessEqual(candle["low"], min(candle["open"], candle["close"]))

    def test_macro_series_are_aligned_by_timestamp(self):
        primary = [
            {"time": 1, "close": 10},
            {"time": 2, "close": 11},
            {"time": 3, "close": 12},
        ]
        companions = {
            "SPY": [{"time": 1}, {"time": 3}, {"time": 4}],
            "IEF": [{"time": 1}, {"time": 2}, {"time": 3}],
        }

        aligned_primary, aligned_companions = app.align_candle_series(primary, companions)

        self.assertEqual([c["time"] for c in aligned_primary], [1, 3])
        self.assertEqual([c["time"] for c in aligned_companions["SPY"]], [1, 3])
        self.assertEqual([c["time"] for c in aligned_companions["IEF"]], [1, 3])


if __name__ == "__main__":
    unittest.main()
