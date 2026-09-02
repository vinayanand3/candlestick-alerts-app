import unittest
from detector import CandlestickDetector

class TestCandlestickDetector(unittest.TestCase):
    def setUp(self):
        self.detector = CandlestickDetector(min_confidence=75.0)

    def test_bullish_engulfing_high_confidence(self):
        candles = [
            {"time": 1000, "open": 110, "high": 111, "low": 108, "close": 108, "volume": 100},
            {"time": 1060, "open": 108, "high": 109, "low": 105, "close": 105, "volume": 100},
            {"time": 1120, "open": 105, "high": 106, "low": 102, "close": 102, "volume": 100},
            {"time": 1180, "open": 102, "high": 103, "low": 99,  "close": 100, "volume": 100},
            {"time": 1240, "open": 100, "high": 101, "low": 97,  "close": 98,  "volume": 120},
            {"time": 1300, "open": 97,  "high": 104, "low": 96,  "close": 103, "volume": 350},
        ]
        alerts = self.detector.analyze_candles(candles)
        engulfing_alert = next((a for a in alerts if a["pattern"] == "Bullish Engulfing"), None)
        self.assertIsNotNone(engulfing_alert)
        self.assertGreaterEqual(engulfing_alert["confidence"], 75.0)
        self.assertEqual(engulfing_alert["direction"], "Bullish")

    def test_bearish_engulfing_high_confidence(self):
        candles = [
            {"time": 1000, "open": 90, "high": 92, "low": 90, "close": 92, "volume": 100},
            {"time": 1060, "open": 92, "high": 95, "low": 92, "close": 95, "volume": 100},
            {"time": 1120, "open": 95, "high": 98, "low": 95, "close": 98, "volume": 100},
            {"time": 1180, "open": 98, "high": 101, "low": 98, "close": 101, "volume": 100},
            # Green candle c1
            {"time": 1240, "open": 101, "high": 104, "low": 101, "close": 103.5, "volume": 120},
            # Red engulfing candle c0 with high volume
            {"time": 1300, "open": 104.5, "high": 105, "low": 98, "close": 99, "volume": 350},
        ]
        alerts = self.detector.analyze_candles(candles)
        engulfing_alert = next((a for a in alerts if a["pattern"] == "Bearish Engulfing"), None)
        self.assertIsNotNone(engulfing_alert)
        self.assertGreaterEqual(engulfing_alert["confidence"], 75.0)
        self.assertEqual(engulfing_alert["direction"], "Bearish")

    def test_hammer_high_confidence(self):
        candles = [
            {"time": 1000, "open": 120, "high": 121, "low": 118, "close": 118, "volume": 100},
            {"time": 1060, "open": 118, "high": 119, "low": 115, "close": 115, "volume": 100},
            {"time": 1120, "open": 115, "high": 116, "low": 112, "close": 112, "volume": 100},
            {"time": 1180, "open": 112, "high": 113, "low": 108, "close": 108, "volume": 100},
            {"time": 1240, "open": 108, "high": 110, "low": 103, "close": 109.5, "volume": 300},
        ]
        alerts = self.detector.analyze_candles(candles)
        hammer_alert = next((a for a in alerts if a["pattern"] == "Hammer"), None)
        self.assertIsNotNone(hammer_alert)
        self.assertGreaterEqual(hammer_alert["confidence"], 75.0)
        self.assertEqual(hammer_alert["direction"], "Bullish")

    def test_shooting_star_high_confidence(self):
        candles = [
            {"time": 1000, "open": 100, "high": 103, "low": 100, "close": 103, "volume": 100},
            {"time": 1060, "open": 103, "high": 106, "low": 103, "close": 106, "volume": 100},
            {"time": 1120, "open": 106, "high": 109, "low": 106, "close": 109, "volume": 100},
            {"time": 1180, "open": 109, "high": 113, "low": 109, "close": 113, "volume": 100},
            {"time": 1240, "open": 113, "high": 119, "low": 111, "close": 111.5, "volume": 320},
        ]
        alerts = self.detector.analyze_candles(candles)
        star_alert = next((a for a in alerts if a["pattern"] == "Shooting Star"), None)
        self.assertIsNotNone(star_alert)
        self.assertGreaterEqual(star_alert["confidence"], 75.0)
        self.assertEqual(star_alert["direction"], "Bearish")

    def test_morning_star_high_confidence(self):
        candles = [
            {"time": 1000, "open": 120, "high": 121, "low": 116, "close": 116, "volume": 100},
            {"time": 1060, "open": 116, "high": 117, "low": 112, "close": 112, "volume": 100},
            # c2: Long red candle
            {"time": 1120, "open": 112, "high": 113, "low": 104, "close": 105, "volume": 120},
            # c1: Small star/indecision candle
            {"time": 1180, "open": 104, "high": 105, "low": 102, "close": 103.5, "volume": 80},
            # c0: Strong green candle closing well above midpoint
            {"time": 1240, "open": 104, "high": 111, "low": 103.5, "close": 110.5, "volume": 280},
        ]
        alerts = self.detector.analyze_candles(candles)
        morning_alert = next((a for a in alerts if a["pattern"] == "Morning Star"), None)
        self.assertIsNotNone(morning_alert)
        self.assertGreaterEqual(morning_alert["confidence"], 75.0)
        self.assertEqual(morning_alert["direction"], "Bullish")

    def test_three_white_soldiers_high_confidence(self):
        candles = [
            {"time": 1000, "open": 90, "high": 91, "low": 89, "close": 90, "volume": 100},
            {"time": 1060, "open": 90, "high": 93, "low": 89.5, "close": 92.8, "volume": 150},
            {"time": 1120, "open": 92.5, "high": 96, "low": 92.2, "close": 95.8, "volume": 180},
            {"time": 1180, "open": 95.5, "high": 99, "low": 95.2, "close": 98.9, "volume": 220},
        ]
        alerts = self.detector.analyze_candles(candles)
        soldiers_alert = next((a for a in alerts if a["pattern"] == "Three White Soldiers"), None)
        self.assertIsNotNone(soldiers_alert)
        self.assertGreaterEqual(soldiers_alert["confidence"], 75.0)
        self.assertEqual(soldiers_alert["direction"], "Bullish")

    def test_low_confidence_filtered_out(self):
        candles = [
            {"time": 1000, "open": 100, "high": 100.5, "low": 99.5, "close": 100.1, "volume": 100},
            {"time": 1060, "open": 100.1, "high": 100.4, "low": 99.7, "close": 99.9, "volume": 100},
            {"time": 1120, "open": 99.9, "high": 100.3, "low": 99.8, "close": 100.0, "volume": 100},
            {"time": 1180, "open": 100.0, "high": 100.4, "low": 99.6, "close": 100.2, "volume": 100},
            {"time": 1240, "open": 100.2, "high": 100.3, "low": 99.8, "close": 99.9, "volume": 90},
        ]
        alerts = self.detector.analyze_candles(candles)
        self.assertEqual(len(alerts), 0)

if __name__ == "__main__":
    unittest.main()
