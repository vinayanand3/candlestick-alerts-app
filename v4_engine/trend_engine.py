"""
Layer 5 — Trend Engine.
Calculates EMA 9, 21, 50, 200 stacks, slopes, and structural higher-high/lower-low alignment.
"""

from typing import List, Dict, Any

def calculate_ema(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    if len(values) < period:
        sma = sum(values) / len(values)
        return [sma] * len(values)
    ema = []
    multiplier = 2.0 / (period + 1.0)
    sma = sum(values[:period]) / period
    for _ in range(period - 1):
        ema.append(sma)
    ema.append(sma)
    for v in values[period:]:
        ema.append((v - ema[-1]) * multiplier + ema[-1])
    return ema

def calculate_sma(values: List[float], period: int) -> List[float]:
    sma = []
    for i in range(len(values)):
        if i < period - 1:
            window = values[:i + 1]
        else:
            window = values[i - period + 1 : i + 1]
        sma.append(sum(window) / len(window) if window else 0.0)
    return sma

def analyze_trend(closes: List[float], highs: List[float], lows: List[float], idx: int) -> Dict[str, Any]:
    n = len(closes)
    if idx < 5:
        return {
            "ema9": closes[idx], "ema21": closes[idx], "ema50": closes[idx], "ema200": closes[idx],
            "is_bull_stack": False, "is_bear_stack": False,
            "trend_dir": "NEUTRAL", "trend_strength": 0.0,
            "structural_hh_hl": False, "structural_lh_ll": False,
            "pullback_to_ema": False, "desc": "Insufficient history for trend analysis"
        }

    ema9 = calculate_ema(closes, 9)
    ema21 = calculate_ema(closes, 21)
    ema50 = calculate_ema(closes, 50)
    ema200 = calculate_ema(closes, min(200, max(20, n)))

    e9 = ema9[idx]
    e21 = ema21[idx]
    e50 = ema50[idx]
    e200 = ema200[idx]
    c_now = closes[idx]

    # Stacks
    is_bull_stack = (c_now >= e9 >= e21 >= e50)
    is_bear_stack = (c_now <= e9 <= e21 <= e50)

    # Slopes (over last 4 bars)
    e9_slope = (e9 - ema9[idx - 3]) / (ema9[idx - 3] or 1.0) * 100.0 if idx >= 3 else 0.0
    e21_slope = (e21 - ema21[idx - 3]) / (ema21[idx - 3] or 1.0) * 100.0 if idx >= 3 else 0.0

    # Structural Highs & Lows (Price swings)
    lookback = min(idx, 8)
    recent_highs = highs[idx - lookback : idx + 1]
    recent_lows = lows[idx - lookback : idx + 1]
    
    hh_hl = (recent_highs[-1] >= max(recent_highs[:-1]) * 0.999) and (recent_lows[-1] > min(recent_lows[:-1]))
    lh_ll = (recent_lows[-1] <= min(recent_lows[:-1]) * 1.001) and (recent_highs[-1] < max(recent_highs[:-1]))

    # Pullback check (price touches or nears EMA9/EMA21 in an aligned trend)
    pullback_bull = is_bull_stack and (lows[idx] <= e9 * 1.002 or lows[idx] <= e21 * 1.002) and c_now >= e21
    pullback_bear = is_bear_stack and (highs[idx] >= e9 * 0.998 or highs[idx] >= e21 * 0.998) and c_now <= e21

    if is_bull_stack and e9_slope > 0.05:
        trend_dir = "BULLISH"
        trend_strength = min(1.0, (e9_slope + e21_slope) / 0.5)
        desc = f"Bullish EMA Stack (9>=21>=50>=200), Price ${c_now:.2f} > EMA9 ${e9:.2f}"
    elif is_bear_stack and e9_slope < -0.05:
        trend_dir = "BEARISH"
        trend_strength = min(1.0, abs(e9_slope + e21_slope) / 0.5)
        desc = f"Bearish EMA Stack (9<=21<=50<=200), Price ${c_now:.2f} < EMA9 ${e9:.2f}"
    else:
        trend_dir = "NEUTRAL"
        trend_strength = 0.0
        desc = f"Mixed / Flat EMA Structure (${c_now:.2f})"

    return {
        "ema9": round(e9, 2),
        "ema21": round(e21, 2),
        "ema50": round(e50, 2),
        "ema200": round(e200, 2),
        "is_bull_stack": is_bull_stack,
        "is_bear_stack": is_bear_stack,
        "trend_dir": trend_dir,
        "trend_strength": round(trend_strength, 2),
        "structural_hh_hl": hh_hl,
        "structural_lh_ll": lh_ll,
        "pullback_bull": pullback_bull,
        "pullback_bear": pullback_bear,
        "desc": desc
    }
