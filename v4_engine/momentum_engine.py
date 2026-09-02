"""
Layer 6 — Momentum & Divergence Engine.
Calculates RSI(14), MACD(12,26,9), Price ROC, Acceleration, and Location-Qualified Divergence.
"""

import math
from typing import List, Dict, Any, Tuple
from v4_engine.trend_engine import calculate_ema, calculate_sma

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    if len(prices) < 2:
        return [50.0] * len(prices)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))
    
    avg_gain = calculate_sma(gains, period)
    avg_loss = calculate_sma(losses, period)
    
    rsi = []
    for i in range(len(prices)):
        if avg_loss[i] == 0:
            rsi.append(100.0 if avg_gain[i] > 0 else 50.0)
        else:
            rs = avg_gain[i] / avg_loss[i]
            rsi.append(100.0 - (100.0 / (1.0 + rs)))
    return rsi

def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = calculate_ema(macd_line, signal)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, histogram

def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> List[float]:
    tr_list = []
    for i in range(len(candles)):
        c = candles[i]
        high = float(c["high"])
        low = float(c["low"])
        if i == 0:
            tr = high - low
        else:
            prev_close = float(candles[i - 1]["close"])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return calculate_sma(tr_list, period)

def analyze_momentum(
    candles: List[Dict[str, Any]],
    closes: List[float],
    rsi: List[float],
    macd_hist: List[float],
    idx: int,
    lookback: int = 15
) -> Dict[str, Any]:
    if idx < 4:
        return {
            "rsi": 50.0, "macd_hist": 0.0, "roc": 0.0, "is_accelerating_bull": False, "is_accelerating_bear": False,
            "divergence": {"bullish": False, "bearish": False, "desc": None}, "desc": "Neutral"
        }

    c_now = closes[idx]
    c_prev = closes[idx - 1]
    c_prev2 = closes[idx - 2]

    # Rate of Change (ROC)
    roc_1 = (c_now - c_prev) / (c_prev or 1.0) * 100.0
    roc_2 = (c_prev - c_prev2) / (c_prev2 or 1.0) * 100.0

    # Acceleration: rate of change expanding significantly
    is_accel_bull = (roc_1 > roc_2 * 1.4) and (roc_1 > 0.25)
    is_accel_bear = (roc_1 < roc_2 * 1.4) and (roc_1 < -0.25)

    curr_rsi = rsi[idx]
    curr_hist = macd_hist[idx]

    # Location-Qualified Divergence
    div_info = {"bullish": False, "bearish": False, "desc": None}
    if idx >= lookback + 2:
        curr_low = float(candles[idx]["low"])
        curr_high = float(candles[idx]["high"])

        window_lows = [float(candles[j]["low"]) for j in range(idx - lookback, idx - 2)]
        window_highs = [float(candles[j]["high"]) for j in range(idx - lookback, idx - 2)]
        window_rsi = [rsi[j] for j in range(idx - lookback, idx - 2)]

        if window_lows and window_highs:
            min_prev_low = min(window_lows)
            min_prev_idx = window_lows.index(min_prev_low)
            prev_low_rsi = window_rsi[min_prev_idx]

            max_prev_high = max(window_highs)
            max_prev_idx = window_highs.index(max_prev_high)
            prev_high_rsi = window_rsi[max_prev_idx]

            # Bullish: Lower price low, Higher RSI low (<50)
            if (curr_low < min_prev_low * 0.998) and (curr_rsi > prev_low_rsi + 2.0) and (curr_rsi < 50.0):
                div_info = {
                    "bullish": True,
                    "bearish": False,
                    "type": "Bullish RSI Divergence",
                    "desc": f"Bullish Divergence: Price Low (${curr_low:.2f}) vs Higher RSI ({curr_rsi:.0f} > {prev_low_rsi:.0f})"
                }
            # Bearish: Higher price high, Lower RSI high (>50)
            elif (curr_high > max_prev_high * 1.002) and (curr_rsi < prev_high_rsi - 2.0) and (curr_rsi > 50.0):
                div_info = {
                    "bullish": False,
                    "bearish": True,
                    "type": "Bearish RSI Divergence",
                    "desc": f"Bearish Divergence: Price High (${curr_high:.2f}) vs Lower RSI ({curr_rsi:.0f} < {prev_high_rsi:.0f})"
                }

    # Contextual desc
    desc_parts = [f"RSI: {curr_rsi:.1f}", f"MACD Hist: {curr_hist:+.3f}"]
    if is_accel_bull:
        desc_parts.append("Bull Momentum Acceleration")
    elif is_accel_bear:
        desc_parts.append("Bear Momentum Acceleration")
    if div_info.get("desc"):
        desc_parts.append(div_info["desc"])

    return {
        "rsi": round(curr_rsi, 1),
        "macd_hist": round(curr_hist, 4),
        "roc": round(roc_1, 2),
        "is_accelerating_bull": is_accel_bull,
        "is_accelerating_bear": is_accel_bear,
        "divergence": div_info,
        "desc": " | ".join(desc_parts)
    }
