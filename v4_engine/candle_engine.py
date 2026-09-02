"""
Layer 4 — Candle Structure & Pattern Engine.
Extracts structured candle evidence without treating single patterns as standalone triggers.
"""

from typing import List, Dict, Any

def analyze_candle_structure(candles: List[Dict[str, Any]], idx: int, avg_atr: float = 1.0) -> Dict[str, Any]:
    if idx < 1:
        c = candles[idx]
        return {
            "body": 0.0, "upper_wick": 0.0, "lower_wick": 0.0, "body_to_range": 0.5,
            "is_bull_close": c["close"] > c["open"], "pattern": None, "score_bull": 0, "score_bear": 0, "desc": "Initial candle"
        }

    c0 = candles[idx]
    c1 = candles[idx - 1]
    c2 = candles[idx - 2] if idx >= 2 else c1

    o0, h0, l0, cl0 = float(c0["open"]), float(c0["high"]), float(c0["low"]), float(c0["close"])
    o1, h1, l1, cl1 = float(c1["open"]), float(c1["high"]), float(c1["low"]), float(c1["close"])
    o2, h2, l2, cl2 = float(c2["open"]), float(c2["high"]), float(c2["low"]), float(c2["close"])

    body = abs(cl0 - o0)
    rng = max(0.0001, h0 - l0)
    upper_wick = h0 - max(o0, cl0)
    lower_wick = min(o0, cl0) - l0
    body_to_range = body / rng
    is_bull_close = cl0 > o0
    is_bear_close = cl0 < o0

    # Pattern Recognition
    is_bull_engulfing = (cl1 < o1) and (cl0 > o0) and (cl0 >= o1) and (o0 <= cl1)
    is_bear_engulfing = (cl1 > o1) and (cl0 < o0) and (cl0 <= o1) and (o0 >= cl1)

    is_hammer = (lower_wick >= 1.8 * body) and (upper_wick <= 0.25 * rng) and (rng >= 0.5 * avg_atr)
    is_shooting_star = (upper_wick >= 1.8 * body) and (lower_wick <= 0.25 * rng) and (rng >= 0.5 * avg_atr)

    is_bull_marubozu = is_bull_close and (body_to_range >= 0.80) and (rng >= 0.7 * avg_atr)
    is_bear_marubozu = is_bear_close and (body_to_range >= 0.80) and (rng >= 0.7 * avg_atr)

    is_inside_bar = (h0 <= h1) and (l0 >= l1)

    is_morning_star = (cl2 < o2) and (abs(cl1 - o1) <= 0.35 * abs(cl2 - o2)) and (cl0 > o0) and (cl0 > (o2 + cl2) / 2.0)
    is_evening_star = (cl2 > o2) and (abs(cl1 - o1) <= 0.35 * abs(cl2 - o2)) and (cl0 < o0) and (cl0 < (o2 + cl2) / 2.0)

    score_bull = 0
    score_bear = 0
    patterns_detected = []

    if is_bull_engulfing:
        score_bull += 15
        patterns_detected.append("Bullish Engulfing")
    elif is_morning_star:
        score_bull += 15
        patterns_detected.append("Morning Star Reversal")
    elif is_hammer:
        score_bull += 12
        patterns_detected.append("Hammer (Lower Wick Demand Rejection)")
    elif is_bull_marubozu:
        score_bull += 12
        patterns_detected.append("Bullish Marubozu Expansion")
    elif is_bull_close:
        score_bull += 6
        patterns_detected.append("Bullish Close")

    if is_bear_engulfing:
        score_bear += 15
        patterns_detected.append("Bearish Engulfing")
    elif is_evening_star:
        score_bear += 15
        patterns_detected.append("Evening Star Reversal")
    elif is_shooting_star:
        score_bear += 12
        patterns_detected.append("Shooting Star (Overhead Supply Rejection)")
    elif is_bear_marubozu:
        score_bear += 12
        patterns_detected.append("Bearish Marubozu Expansion")
    elif is_bear_close:
        score_bear += 6
        patterns_detected.append("Bearish Close")

    if is_inside_bar:
        patterns_detected.append("Inside Bar Compression")

    return {
        "body": round(body, 2),
        "range": round(rng, 2),
        "upper_wick": round(upper_wick, 2),
        "lower_wick": round(lower_wick, 2),
        "body_to_range": round(body_to_range, 2),
        "is_bull_close": is_bull_close,
        "is_bear_close": is_bear_close,
        "is_inside_bar": is_inside_bar,
        "is_hammer": is_hammer,
        "is_shooting_star": is_shooting_star,
        "is_bull_engulfing": is_bull_engulfing,
        "is_bear_engulfing": is_bear_engulfing,
        "score_bull": score_bull,
        "score_bear": score_bear,
        "patterns": patterns_detected,
        "desc": ", ".join(patterns_detected) if patterns_detected else "Standard Candle"
    }
