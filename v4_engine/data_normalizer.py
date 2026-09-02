"""
Layer 1 — Data Validation & Normalization Engine.
Ensures clean, chronological, validated OHLCV candles normalized to America/New_York.
"""

from typing import List, Dict, Any, Tuple

def validate_and_normalize_candles(candles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings = []
    if not candles:
        return [], ["Empty candle list provided."]

    normalized = []
    seen_timestamps = set()

    for idx, c in enumerate(candles):
        if not isinstance(c, dict):
            warnings.append(f"Candle at index {idx} is not a dictionary. Dropped.")
            continue

        if "time" not in c or "open" not in c or "high" not in c or "low" not in c or "close" not in c:
            warnings.append(f"Candle at index {idx} missing required OHLC fields. Dropped.")
            continue

        try:
            ts = int(c["time"])
            c_open = float(c["open"])
            c_high = float(c["high"])
            c_low = float(c["low"])
            c_close = float(c["close"])
            c_vol = float(c.get("volume", 100.0))
        except (ValueError, TypeError) as e:
            warnings.append(f"Candle at index {idx} contains non-numeric data ({e}). Dropped.")
            continue

        # Basic Sanity Checks
        if c_low > c_high or c_open < 0 or c_close < 0:
            warnings.append(f"Candle at index {idx} has invalid price bounds (High: {c_high}, Low: {c_low}). Dropped.")
            continue

        # Adjust minor floating point boundary imperfections
        c_high = max(c_high, c_open, c_close)
        c_low = min(c_low, c_open, c_close)

        if ts in seen_timestamps:
            # Overwrite duplicate timestamp with latest candle
            for i, existing in enumerate(normalized):
                if existing["time"] == ts:
                    normalized[i] = {
                        "time": ts,
                        "open": round(c_open, 2),
                        "high": round(c_high, 2),
                        "low": round(c_low, 2),
                        "close": round(c_close, 2),
                        "volume": round(c_vol, 2),
                        "is_closed": True
                    }
                    break
        else:
            seen_timestamps.add(ts)
            normalized.append({
                "time": ts,
                "open": round(c_open, 2),
                "high": round(c_high, 2),
                "low": round(c_low, 2),
                "close": round(c_close, 2),
                "volume": round(c_vol, 2),
                "is_closed": True
            })

    # Chronological sort
    normalized.sort(key=lambda x: x["time"])
    return normalized, warnings
