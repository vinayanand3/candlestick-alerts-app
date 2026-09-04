import os
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

import app
from push_notifications import InvalidPushEndpoint, event_id, validate_push_subscription


VALID_SUBSCRIPTION = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/example-capability",
    "expirationTime": None,
    "keys": {
        "p256dh": "A" * 87,
        "auth": "B" * 22,
    },
}


class TestPushSecurity(unittest.TestCase):
    def test_rejects_arbitrary_push_endpoint(self):
        subscription = {
            **VALID_SUBSCRIPTION,
            "endpoint": "https://attacker.example/internal-callback",
        }
        with self.assertRaises(InvalidPushEndpoint):
            validate_push_subscription(subscription)

    def test_event_identifier_is_deterministic(self):
        event = {
            "type": "SIGNAL_CONFIRMED",
            "time": 1_700_000_000,
            "direction": "CALL",
            "state": "CONFIRMED",
            "title": "Test",
        }
        self.assertEqual(event_id("TSLA", "15m", event), event_id("TSLA", "15m", event))
        self.assertNotEqual(event_id("TSLA", "15m", event), event_id("AAPL", "15m", event))

    def test_scan_endpoint_requires_bearer_token(self):
        with patch.dict(os.environ, {"SCAN_TOKEN": "correct-token"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                app.require_scan_access(None)
        self.assertEqual(raised.exception.status_code, 401)

    def test_subscription_endpoint_rejects_wrong_token(self):
        with patch.dict(os.environ, {"SUBSCRIPTION_ACCESS_TOKEN": "correct-token"}, clear=False):
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token")
            with self.assertRaises(HTTPException) as raised:
                app.require_subscription_access(credentials)
        self.assertEqual(raised.exception.status_code, 401)

    def test_subscription_payload_rejects_unknown_fields(self):
        invalid = dict(VALID_SUBSCRIPTION)
        invalid["unexpected"] = "value"
        with self.assertRaises(ValidationError):
            app.SubscribeRequest.model_validate({"subscription": invalid})


class TestScannerTiming(unittest.TestCase):
    def test_uses_latest_completed_intraday_candle(self):
        eastern = ZoneInfo("America/New_York")
        now = datetime(2026, 9, 2, 10, 21, tzinfo=eastern)
        candles = [
            {"time": int(datetime(2026, 9, 2, 10, 0, tzinfo=eastern).timestamp())},
            {"time": int(datetime(2026, 9, 2, 10, 15, tzinfo=eastern).timestamp())},
        ]
        latest = app._latest_completed_candle_time(candles, "15m", now=now)
        self.assertEqual(latest, candles[0]["time"])

    def test_does_not_replay_previous_day(self):
        eastern = ZoneInfo("America/New_York")
        now = datetime(2026, 9, 2, 9, 25, tzinfo=eastern)
        candles = [
            {"time": int(datetime(2026, 9, 1, 15, 45, tzinfo=eastern).timestamp())},
        ]
        self.assertIsNone(app._latest_completed_candle_time(candles, "15m", now=now))

    def test_market_window_excludes_weekends(self):
        eastern = ZoneInfo("America/New_York")
        saturday = datetime(2026, 9, 5, 11, 0, tzinfo=eastern)
        self.assertFalse(app._within_scan_window(saturday))


if __name__ == "__main__":
    unittest.main()
