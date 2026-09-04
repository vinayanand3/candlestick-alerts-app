"""Persistent Web Push subscriptions and delivery helpers.

Secrets are supplied only through environment variables. Firestore keeps browser
subscriptions and alert deduplication state durable across Render restarts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

from google.cloud import firestore
from google.oauth2 import service_account
from pywebpush import WebPushException, webpush


class PushConfigurationError(RuntimeError):
    """Raised when server-side push configuration is incomplete or invalid."""


class InvalidPushEndpoint(ValueError):
    """Raised when a subscription endpoint is not a known browser push service."""


REQUIRED_PUSH_SETTINGS = (
    "FIREBASE_SERVICE_ACCOUNT_JSON",
    "VAPID_PRIVATE_KEY",
    "VAPID_PUBLIC_KEY",
    "VAPID_CONTACT_EMAIL",
    "SUBSCRIPTION_ACCESS_TOKEN",
    "SCAN_TOKEN",
)

DEFAULT_PUSH_HOSTS = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "web.push.apple.com",
)

_client = None
_client_lock = threading.Lock()


def missing_push_settings() -> List[str]:
    return [name for name in REQUIRED_PUSH_SETTINGS if not os.getenv(name)]


def push_is_configured() -> bool:
    return not missing_push_settings()


def get_vapid_public_key() -> str:
    public_key = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    if not public_key:
        raise PushConfigurationError("VAPID_PUBLIC_KEY is not configured.")
    return public_key


def _allowed_push_host(hostname: str) -> bool:
    hostname = hostname.lower().rstrip(".")
    configured = tuple(
        item.strip().lower().rstrip(".")
        for item in os.getenv("PUSH_ENDPOINT_HOSTS", "").split(",")
        if item.strip()
    )
    exact_hosts = DEFAULT_PUSH_HOSTS + configured
    if hostname in exact_hosts:
        return True
    return hostname.endswith(".notify.windows.com")


def validate_push_subscription(subscription: Dict[str, Any]) -> None:
    endpoint = str(subscription.get("endpoint", ""))
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or not _allowed_push_host(parsed.hostname):
        raise InvalidPushEndpoint("Unsupported browser push endpoint.")

    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise InvalidPushEndpoint("Invalid browser push endpoint.")

    keys = subscription.get("keys") or {}
    base64url = re.compile(r"^[A-Za-z0-9_-]+$")
    for key_name in ("p256dh", "auth"):
        value = str(keys.get(key_name, ""))
        if not 8 <= len(value) <= 512 or not base64url.fullmatch(value):
            raise InvalidPushEndpoint(f"Invalid {key_name} subscription key.")


def subscription_id(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def event_id(symbol: str, timeframe: str, event: Dict[str, Any]) -> str:
    identity = "|".join(
        [
            symbol.upper(),
            timeframe,
            str(event.get("type", "")),
            str(event.get("time", "")),
            str(event.get("direction", "")),
            str(event.get("state", "")),
            str(event.get("title", "")),
        ]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _firestore_client():
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client

        raw_credentials = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
        if not raw_credentials:
            raise PushConfigurationError("FIREBASE_SERVICE_ACCOUNT_JSON is not configured.")
        try:
            info = json.loads(raw_credentials)
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n")
            credentials = service_account.Credentials.from_service_account_info(info)
            _client = firestore.Client(project=info["project_id"], credentials=credentials)
        except (KeyError, TypeError, ValueError) as exc:
            raise PushConfigurationError("Firebase service-account configuration is invalid.") from exc
    return _client


def _collection(name: str):
    prefix = re.sub(r"[^a-zA-Z0-9_-]", "", os.getenv("FIRESTORE_COLLECTION_PREFIX", "candlestick_alerts"))
    if not prefix:
        prefix = "candlestick_alerts"
    return _firestore_client().collection(f"{prefix}_{name}")


def save_subscription(subscription: Dict[str, Any], preferences: Dict[str, Any]) -> str:
    validate_push_subscription(subscription)
    doc_id = subscription_id(subscription["endpoint"])
    _collection("subscriptions").document(doc_id).set(
        {
            "subscription": subscription,
            "preferences": preferences,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    return doc_id


def delete_subscription(endpoint: str) -> None:
    _collection("subscriptions").document(subscription_id(endpoint)).delete()


def list_subscriptions() -> List[Dict[str, Any]]:
    records = []
    for document in _collection("subscriptions").stream():
        data = document.to_dict() or {}
        data["id"] = document.id
        records.append(data)
    return records


def alert_was_sent(alert_id: str) -> bool:
    return _collection("sent_alerts").document(alert_id).get().exists


def mark_alert_sent(alert_id: str, payload: Dict[str, Any]) -> None:
    _collection("sent_alerts").document(alert_id).set(
        {"payload": payload, "sent_at": firestore.SERVER_TIMESTAMP}
    )


def _vapid_claims() -> Dict[str, str]:
    contact = os.getenv("VAPID_CONTACT_EMAIL", "").strip()
    if "@" in contact and not contact.startswith("mailto:"):
        contact = f"mailto:{contact}"
    if not contact.startswith(("mailto:", "https://")):
        raise PushConfigurationError("VAPID_CONTACT_EMAIL must be an email address or HTTPS URL.")
    return {"sub": contact}


def send_web_push(subscription: Dict[str, Any], payload: Dict[str, Any]) -> Tuple[bool, bool]:
    """Send one push message.

    Returns ``(delivered, subscription_expired)``. Message bodies and endpoint
    capability URLs are never logged here.
    """
    validate_push_subscription(subscription)
    private_key = os.getenv("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
    if not private_key:
        raise PushConfigurationError("VAPID_PRIVATE_KEY is not configured.")

    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload, separators=(",", ":")),
            vapid_private_key=private_key,
            vapid_claims=_vapid_claims(),
            timeout=15,
        )
        return True, False
    except WebPushException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return False, status_code in (404, 410)


def deliver_payload(
    records: Iterable[Dict[str, Any]],
    symbol: str,
    score: float,
    payload: Dict[str, Any],
) -> Dict[str, int]:
    delivered = failed = expired = skipped = 0
    for record in records:
        preferences = record.get("preferences") or {}
        symbols = {str(item).upper() for item in preferences.get("symbols", [])}
        min_score = float(preferences.get("min_score", 68))
        if symbol.upper() not in symbols or score < min_score:
            skipped += 1
            continue

        subscription = record.get("subscription") or {}
        try:
            was_delivered, is_expired = send_web_push(subscription, payload)
        except (InvalidPushEndpoint, PushConfigurationError):
            was_delivered, is_expired = False, False

        if was_delivered:
            delivered += 1
        elif is_expired:
            expired += 1
            delete_subscription(str(subscription.get("endpoint", "")))
        else:
            failed += 1

    return {
        "delivered": delivered,
        "failed": failed,
        "expired": expired,
        "skipped": skipped,
    }
