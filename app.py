"""
Institutional Confluence & Macro Rotation Trading App — V4 Production Engine.
Supports: TSLA, AAPL, NVDA, META, QQQ.
"""

import os
import time
import random
import threading
from typing import List, Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import yfinance as yf

from v4_engine.pipeline import V4Pipeline
from v4_engine.config import V4_DEFAULT_CONFIG
from v4_engine.backtester import run_backtest
from qqq_macro_v4 import V4QQQMacroRotationEngine

app = FastAPI(
    title="V4 Institutional Confluence & Macro Rotation Engine",
    description="Production-Oriented High-Conviction Signal Engine for TSLA, AAPL, NVDA, META, and QQQ"
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
    allow_methods=["*"],
    allow_headers=["*"],
)

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

if __name__ == "__main__":
    print("Starting V4 Institutional Confluence & Macro Alert App at http://127.0.0.1:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
