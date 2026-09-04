"""
Institutional Confluence & Macro Rotation Trading App — V4 Production Engine.
Supports: TSLA, AAPL, NVDA, META, QQQ.
"""

import os
import time
import random
import secrets
import threading
from datetime import datetime, time as datetime_time
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
import yfinance as yf

from v4_engine.pipeline import V4Pipeline
from v4_engine.config import V4_DEFAULT_CONFIG
from v4_engine.backtester import run_backtest
from qqq_macro_v4 import V4QQQMacroRotationEngine
from push_notifications import (
    InvalidPushEndpoint,
    PushConfigurationError,
    alert_was_sent,
    delete_subscription,
    deliver_payload,
    event_id,
    get_vapid_public_key,
    list_subscriptions,
    mark_alert_sent,
    missing_push_settings,
    push_is_configured,
    save_subscription,
    send_web_push,
    validate_push_subscription,
)

docs_enabled = os.getenv("ENABLE_API_DOCS", "false").lower() == "true"
app = FastAPI(
    title="V4 Institutional Confluence & Macro Rotation Engine",
    description="Production-Oriented High-Conviction Signal Engine for TSLA, AAPL, NVDA, META, and QQQ",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS)).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

allowed_hosts = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,testserver,*.onrender.com",
    ).split(",")
    if host.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# Initialize engines
v4_pipeline = V4Pipeline(config=V4_DEFAULT_CONFIG)
v4_qqq_engine = V4QQQMacroRotationEngine(confirmation_days=2, hysteresis_pct=0.5)

TARGET_SYMBOLS = [
    {"symbol": "SPX", "name": "S&P 500 Index (SPXW Options)", "sector": "Broad Market Benchmark", "base_price": 5850.0, "type": "index_options", "yf_ticker": "^GSPC"},
    {"symbol": "NDX", "name": "Nasdaq-100 Index (NDXP Options)", "sector": "Tech Mega-Cap Benchmark", "base_price": 20400.0, "type": "index_options", "yf_ticker": "^NDX"},
    {"symbol": "TSLA", "name": "Tesla, Inc.", "sector": "Automotive / Tech", "base_price": 220.0, "type": "equity"},
    {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Consumer Electronics", "base_price": 230.0, "type": "equity"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "Semiconductors / AI", "base_price": 125.0, "type": "equity"},
    {"symbol": "META", "name": "Meta Platforms, Inc.", "sector": "Digital Media / AI", "base_price": 520.0, "type": "equity"},
    {"symbol": "QQQ", "name": "Invesco QQQ (TQQQ / SQQQ Macro Rotation)", "sector": "Tech Index / Macro Rotation", "base_price": 480.0, "type": "macro_rotation"},
]

VALID_SYMBOLS = {s["symbol"]: s for s in TARGET_SYMBOLS}
VALID_TIMEFRAMES = {"1m", "5m", "15m", "1h", "1d"}
DEFAULT_NOTIFICATION_SYMBOLS = ["SPX", "NDX", "TSLA", "AAPL", "NVDA", "META", "QQQ"]

bearer_scheme = HTTPBearer(auto_error=False)


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=8, max_length=512, pattern=r"^[A-Za-z0-9_-]+$")
    auth: str = Field(min_length=8, max_length=512, pattern=r"^[A-Za-z0-9_-]+$")


class BrowserPushSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    endpoint: HttpUrl = Field(max_length=2048)
    expiration_time: Optional[int] = Field(default=None, alias="expirationTime")
    keys: PushKeys


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: List[str] = Field(default_factory=lambda: list(DEFAULT_NOTIFICATION_SYMBOLS), min_length=1, max_length=7)
    min_score: int = Field(default=68, ge=0, le=100)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, symbols: List[str]) -> List[str]:
        normalized = list(dict.fromkeys(symbol.upper() for symbol in symbols))
        if any(symbol not in VALID_SYMBOLS for symbol in normalized):
            raise ValueError("Preferences include an unsupported symbol.")
        return normalized


class SubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscription: BrowserPushSubscription
    preferences: NotificationPreferences = Field(default_factory=NotificationPreferences)


class UnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: HttpUrl = Field(max_length=2048)


def _require_token(
    setting_name: str,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> None:
    expected = os.getenv(setting_name, "")
    if not expected:
        raise HTTPException(status_code=503, detail=f"{setting_name} is not configured.")
    supplied = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else ""
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_subscription_access(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> None:
    _require_token("SUBSCRIPTION_ACCESS_TOKEN", credentials)


def require_scan_access(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> None:
    _require_token("SCAN_TOKEN", credentials)

_market_data_cache: Dict[str, Dict[str, Any]] = {}
_market_data_cache_lock = threading.Lock()


def _cache_ttl_seconds(interval: str) -> int:
    configured_ttl = os.getenv("MARKET_DATA_CACHE_SECONDS")
    if configured_ttl:
        return max(1, int(configured_ttl))
    return {
        "1m": 20,
        "5m": 45,
        "15m": 60,
        "1h": 300,
        "1d": 900,
    }.get(interval, 60)

def fetch_equity_candles(symbol: str, interval: str = "15m") -> List[Dict[str, Any]]:
    cache_key = f"{symbol.upper()}:{interval}"
    now = time.monotonic()
    with _market_data_cache_lock:
        cached = _market_data_cache.get(cache_key)
        if cached and now - cached["stored_at"] < _cache_ttl_seconds(interval):
            return [dict(candle) for candle in cached["candles"]]

    interval_map = {
        "1m": ("1m", "1d"),
        "5m": ("5m", "5d"),
        "15m": ("15m", "5d"),
        "1h": ("60m", "1mo"),
        "1d": ("1d", "1y")
    }
    yf_interval, yf_period = interval_map.get(interval, ("15m", "5d"))
    yf_symbol = VALID_SYMBOLS.get(symbol, {}).get("yf_ticker", symbol)
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=yf_period, interval=yf_interval)
        if not df.empty:
            candles = []
            for index, row in df.iterrows():
                ts = int(index.timestamp())
                candles.append({
                    "time": ts,
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": float(row["Volume"]) if "Volume" in row and row["Volume"] > 0 else 1000.0
                })
            if len(candles) >= 20:
                result = candles[-300:]
                with _market_data_cache_lock:
                    _market_data_cache[cache_key] = {
                        "stored_at": time.monotonic(),
                        "candles": result,
                    }
                return [dict(candle) for candle in result]
    except Exception as e:
        print(f"Error fetching Yahoo Finance data for {symbol} ({yf_symbol}): {e}")
    return []


def align_candle_series(
    primary: List[Dict[str, Any]],
    companions: Dict[str, List[Dict[str, Any]]],
) -> tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Align independently downloaded series by their exact candle timestamps."""
    companion_maps = {
        symbol: {candle["time"]: candle for candle in candles}
        for symbol, candles in companions.items()
    }
    common_times = {
        candle["time"]
        for candle in primary
        if all(candle["time"] in candle_map for candle_map in companion_maps.values())
    }
    aligned_primary = [candle for candle in primary if candle["time"] in common_times]
    aligned_companions = {
        symbol: [candle_map[candle["time"]] for candle in aligned_primary]
        for symbol, candle_map in companion_maps.items()
    }
    return aligned_primary, aligned_companions

def generate_simulated_market(symbol: str, num_candles: int = 100) -> List[Dict[str, Any]]:
    meta = VALID_SYMBOLS.get(symbol, {"base_price": 200.0})
    base_price = meta["base_price"]
    now = int(time.time()) - (num_candles * 900)
    
    candles = []
    current_price = base_price
    
    for i in range(num_candles):
        c_time = now + (i * 900)
        
        # Wave cycle
        if i < 30:
            drift = random.uniform(-0.003, 0.003)
        elif 30 <= i < 40:
            drift = -0.005
        elif i == 40:
            drift = 0.016
        elif 40 < i <= 75:
            drift = random.uniform(0.001, 0.007)
        elif i == 76:
            drift = -0.015
        else:
            drift = random.uniform(-0.006, 0.002)

        c_open = current_price
        c_close = c_open * (1 + drift)
        high_extra = abs(c_open * random.uniform(0.001, 0.004))
        low_extra = abs(c_open * random.uniform(0.001, 0.004))
        c_high = max(c_open, c_close) + high_extra
        c_low = min(c_open, c_close) - low_extra
        c_volume = random.uniform(8000, 15000)

        if i == 40:
            c_low = c_open * 0.995
            c_high = c_close * 1.002
            c_volume = 38000
        elif i == 58:
            c_high = c_close * 1.006
            c_volume = 42000
        elif i == 76:
            c_high = c_open * 1.022
            c_close = c_open * 0.994
            c_volume = 36000

        c_high = max(c_open, c_close, c_high)
        c_low = min(c_open, c_close, c_low)

        candles.append({
            "time": c_time,
            "open": round(c_open, 2),
            "high": round(c_high, 2),
            "low": round(c_low, 2),
            "close": round(c_close, 2),
            "volume": round(c_volume, 0)
        })
        current_price = c_close

    return candles

@app.get("/api/symbols")
def get_symbols():
    return {"symbols": TARGET_SYMBOLS}

@app.get("/api/health")
def get_health():
    return {"status": "ok", "service": "candlestick-alerts-api"}


@app.get("/api/push/config")
def get_push_config():
    missing = missing_push_settings()
    return {
        "configured": not missing,
        "public_key": get_vapid_public_key() if "VAPID_PUBLIC_KEY" not in missing else None,
        "missing_settings": missing,
    }


@app.post("/api/push/subscriptions", dependencies=[Security(require_subscription_access)])
def subscribe_to_push(request: SubscribeRequest):
    if not push_is_configured():
        raise HTTPException(status_code=503, detail="Browser notifications are not configured.")
    subscription = request.subscription.model_dump(mode="json", by_alias=True)
    try:
        subscription_identifier = save_subscription(
            subscription,
            request.preferences.model_dump(mode="json"),
        )
    except InvalidPushEndpoint as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PushConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"subscribed": True, "subscription_id": subscription_identifier}


@app.delete("/api/push/subscriptions", dependencies=[Security(require_subscription_access)])
def unsubscribe_from_push(request: UnsubscribeRequest):
    try:
        delete_subscription(str(request.endpoint))
    except PushConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"subscribed": False}


@app.post("/api/push/test", dependencies=[Security(require_subscription_access)])
def test_push_notification(request: SubscribeRequest):
    subscription = request.subscription.model_dump(mode="json", by_alias=True)
    try:
        validate_push_subscription(subscription)
        delivered, expired = send_web_push(
            subscription,
            {
                "title": "Candlestick alerts are enabled",
                "body": "This browser is ready to receive new trading alerts.",
                "tag": "candlestick-alerts-test",
                "url": os.getenv(
                    "DASHBOARD_URL",
                    "https://vinayanand3.github.io/candlestick-alerts-app/",
                ),
            },
        )
    except InvalidPushEndpoint as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PushConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not delivered:
        status_code = 410 if expired else 502
        raise HTTPException(status_code=status_code, detail="The browser push service rejected the test notification.")
    return {"delivered": True}

@app.get("/api/analysis")
def get_market_analysis(
    symbol: str = Query("TSLA", description="Stock symbol (TSLA, AAPL, NVDA, META, QQQ)"),
    timeframe: str = Query("15m", description="Timeframe"),
    mode: str = Query("auto", description="auto, live, or simulate")
):
    sym = symbol.upper()
    if sym not in VALID_SYMBOLS:
        sym = "TSLA"

    requested_timeframe = timeframe
    analysis_timeframe = "1d" if sym == "QQQ" else timeframe

    if mode == "simulate":
        candles = generate_simulated_market(sym, num_candles=100)
        source = "simulation"
    else:
        candles = fetch_equity_candles(sym, analysis_timeframe)
        source = "yahoo_finance"
        if not candles:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Live market data is temporarily unavailable.",
                    "symbol": sym,
                    "source": "unavailable",
                    "simulation_available": True,
                },
            )

    # Route QQQ to V4 Macro Rotation Engine
    if sym == "QQQ":
        if mode == "simulate":
            rotation_analysis = v4_qqq_engine.analyze(candles)
            return {
                "symbol": "QQQ",
                "company_name": VALID_SYMBOLS["QQQ"]["name"],
                "sector": VALID_SYMBOLS["QQQ"]["sector"],
                "type": "macro_rotation",
                "timeframe": "1d",
                "requested_timeframe": requested_timeframe,
                "source": source,
                "candles": candles,
                "macro_regime": rotation_analysis.get("macro_regime"),
                "active_state": rotation_analysis.get("active_state"),
                "macro_telemetry": rotation_analysis.get("macro_telemetry"),
                "alerts": rotation_analysis.get("alerts", []),
            }

        companion_data = {
            ticker: fetch_equity_candles(ticker, "1d")
            for ticker in ("SPY", "TQQQ", "SQQQ", "IEF")
        }
        missing_companions = [ticker for ticker, data in companion_data.items() if not data]
        if missing_companions:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "QQQ macro analysis requires live SPY, TQQQ, SQQQ, and IEF data.",
                    "missing_symbols": missing_companions,
                    "source": "unavailable",
                },
            )

        candles, companion_data = align_candle_series(candles, companion_data)
        if len(candles) < 20:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "QQQ macro series do not have enough matching trading dates.",
                    "source": "unavailable",
                },
            )
        rotation_analysis = v4_qqq_engine.analyze(
            candles,
            spy_candles=companion_data["SPY"],
            tqqq_candles=companion_data["TQQQ"],
            sqqq_candles=companion_data["SQQQ"],
            ief_candles=companion_data["IEF"],
        )
        return {
            "symbol": "QQQ",
            "company_name": VALID_SYMBOLS["QQQ"]["name"],
            "sector": VALID_SYMBOLS["QQQ"]["sector"],
            "type": "macro_rotation",
            "timeframe": "1d",
            "requested_timeframe": requested_timeframe,
            "source": source,
            "candles": candles,
            "macro_regime": rotation_analysis.get("macro_regime"),
            "active_state": rotation_analysis.get("active_state"),
            "macro_telemetry": rotation_analysis.get("macro_telemetry"),
            "alerts": rotation_analysis.get("alerts", [])
        }

    # Route Individual Equities to V4 Pipeline
    analysis = v4_pipeline.analyze(candles, symbol=sym, timeframe=analysis_timeframe)

    return {
        "symbol": sym,
        "company_name": VALID_SYMBOLS[sym]["name"],
        "sector": VALID_SYMBOLS[sym]["sector"],
        "type": "equity",
        "timeframe": timeframe,
        "source": source,
        "candle_count": len(candles),
        "candles": candles,
        "regime": analysis.get("regime"),
        "market_risk": analysis.get("market_risk"),
        "setup": analysis.get("setup"),
        "scoring": analysis.get("scoring"),
        "risk": analysis.get("risk"),
        "active_signal": analysis.get("active_signal"),
        "alerts": analysis.get("alerts", []),
        "options": analysis.get("options"),
        "explainability": analysis.get("explainability"),
        "indicators": analysis.get("indicators", {})
    }


def _within_scan_window(now: Optional[datetime] = None) -> bool:
    eastern_now = now or datetime.now(ZoneInfo("America/New_York"))
    if eastern_now.tzinfo is None:
        eastern_now = eastern_now.replace(tzinfo=ZoneInfo("America/New_York"))
    return (
        eastern_now.weekday() < 5
        and datetime_time(9, 20) <= eastern_now.time() <= datetime_time(16, 30)
    )


def _latest_completed_candle_time(
    candles: List[Dict[str, Any]],
    timeframe: str,
    now: Optional[datetime] = None,
) -> Optional[int]:
    eastern_now = now or datetime.now(ZoneInfo("America/New_York"))
    if eastern_now.tzinfo is None:
        eastern_now = eastern_now.replace(tzinfo=ZoneInfo("America/New_York"))

    if timeframe == "1d":
        if eastern_now.time() < datetime_time(16, 5):
            return None
        today = eastern_now.date()
        matching = [
            int(candle["time"])
            for candle in candles
            if datetime.fromtimestamp(int(candle["time"]), ZoneInfo("America/New_York")).date() == today
        ]
        return max(matching) if matching else None

    interval_seconds = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
    }.get(timeframe)
    if interval_seconds is None:
        return None

    now_timestamp = eastern_now.timestamp()
    today = eastern_now.date()
    completed = [
        int(candle["time"])
        for candle in candles
        if int(candle["time"]) + interval_seconds + 30 <= now_timestamp
        and datetime.fromtimestamp(int(candle["time"]), ZoneInfo("America/New_York")).date() == today
    ]
    return max(completed) if completed else None


def _notification_score(event: Dict[str, Any], analysis: Dict[str, Any]) -> float:
    if event.get("type") in {"SIGNAL_EXIT", "TARGET_1_HIT", "TARGET_2_HIT", "SIGNAL_WEAKENING", "PORTFOLIO_ROTATION"}:
        return 100.0
    return float(event.get("signal_score") or (analysis.get("scoring") or {}).get("signal_score") or 0.0)


def _notification_payload(symbol: str, event: Dict[str, Any], alert_identifier: str) -> Dict[str, Any]:
    dashboard_url = os.getenv(
        "DASHBOARD_URL",
        "https://vinayanand3.github.io/candlestick-alerts-app/",
    ).rstrip("/") + "/"
    title = str(event.get("title") or f"New {symbol} trading alert")[:120]
    description = str(event.get("desc") or event.get("reason") or "Open the dashboard for details.")[:240]
    return {
        "title": f"{symbol}: {title}",
        "body": description,
        "tag": alert_identifier,
        "url": f"{dashboard_url}?symbol={symbol}",
    }


def run_notification_scan(force: bool = False, now: Optional[datetime] = None) -> Dict[str, Any]:
    if not push_is_configured():
        raise PushConfigurationError("Browser notifications are not fully configured.")
    if not force and not _within_scan_window(now):
        return {"status": "skipped", "reason": "outside_market_scan_window"}

    subscriptions = list_subscriptions()
    if not subscriptions:
        return {"status": "ok", "symbols_scanned": 0, "events_found": 0, "delivered": 0}

    configured_symbols = [
        symbol.strip().upper()
        for symbol in os.getenv("SCAN_SYMBOLS", ",".join(DEFAULT_NOTIFICATION_SYMBOLS)).split(",")
        if symbol.strip().upper() in VALID_SYMBOLS
    ]
    timeframe = os.getenv("SCAN_TIMEFRAME", "15m")
    if timeframe not in VALID_TIMEFRAMES:
        timeframe = "15m"

    totals = {
        "status": "ok",
        "symbols_scanned": 0,
        "symbols_failed": 0,
        "events_found": 0,
        "delivered": 0,
        "failed": 0,
        "expired": 0,
        "skipped": 0,
    }
    actionable_types = {
        "SIGNAL_CONFIRMED",
        "SIGNAL_EXIT",
        "SIGNAL_WEAKENING",
        "TARGET_1_HIT",
        "TARGET_2_HIT",
        "PORTFOLIO_ROTATION",
    }

    for symbol in configured_symbols:
        symbol_timeframe = "1d" if symbol == "QQQ" else timeframe
        analysis = get_market_analysis(symbol, symbol_timeframe, "auto")
        if isinstance(analysis, JSONResponse):
            totals["symbols_failed"] += 1
            continue

        totals["symbols_scanned"] += 1
        completed_time = _latest_completed_candle_time(
            analysis.get("candles", []),
            symbol_timeframe,
            now=now,
        )
        if completed_time is None:
            continue

        events = [
            event
            for event in analysis.get("alerts", [])
            if event.get("type") in actionable_types and int(event.get("time", 0)) == completed_time
        ]
        totals["events_found"] += len(events)

        for event in events:
            alert_identifier = event_id(symbol, symbol_timeframe, event)
            if alert_was_sent(alert_identifier):
                totals["skipped"] += 1
                continue

            payload = _notification_payload(symbol, event, alert_identifier)
            delivery = deliver_payload(
                subscriptions,
                symbol,
                _notification_score(event, analysis),
                payload,
            )
            for key in ("delivered", "failed", "expired", "skipped"):
                totals[key] += delivery[key]
            if delivery["delivered"] > 0:
                mark_alert_sent(alert_identifier, payload)

    return totals


@app.post("/api/scan", dependencies=[Security(require_scan_access)])
def trigger_notification_scan(force: bool = Query(False)):
    try:
        return run_notification_scan(force=force)
    except PushConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@app.get("/api/backtest")
def run_backtest_simulation(
    symbol: str = Query("TSLA", description="Stock symbol (TSLA, AAPL, NVDA, META)"),
    timeframe: str = Query("15m", description="Timeframe")
):
    sym = symbol.upper()
    candles = fetch_equity_candles(sym, timeframe)
    if not candles or len(candles) < 40:
        candles = generate_simulated_market(sym, num_candles=120)

    results = run_backtest(candles, symbol=sym, config=V4_DEFAULT_CONFIG)
    return results

@app.get("/api/config")
def get_config():
    return {"config": V4_DEFAULT_CONFIG}

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend static file index.html not found."})

@app.get("/config.js")
def serve_frontend_config():
    config_file = os.path.join(static_dir, "config.js")
    if os.path.exists(config_file):
        return FileResponse(config_file, media_type="application/javascript")
    return JSONResponse({"message": "Frontend config file not found."}, status_code=404)


@app.get("/sw.js")
def serve_service_worker():
    worker_file = os.path.join(static_dir, "sw.js")
    if os.path.exists(worker_file):
        response = FileResponse(worker_file, media_type="application/javascript")
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response
    return JSONResponse({"message": "Service worker not found."}, status_code=404)


@app.get("/manifest.webmanifest")
def serve_web_manifest():
    manifest_file = os.path.join(static_dir, "manifest.webmanifest")
    if os.path.exists(manifest_file):
        return FileResponse(manifest_file, media_type="application/manifest+json")
    return JSONResponse({"message": "Web manifest not found."}, status_code=404)

if __name__ == "__main__":
    print("Starting V4 Institutional Confluence & Macro Alert App at http://127.0.0.1:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
