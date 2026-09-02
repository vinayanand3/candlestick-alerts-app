"""
Layer 2 — Market Regime Engine.
Classifies market environment (TRENDING_UP, TRENDING_DOWN, RANGE, HIGH_VOLATILITY)
and determines eligible setup types and gating constraints.
"""

from typing import List, Dict, Any

def classify_market_regime(
    candles: List[Dict[str, Any]],
    trend_data: Dict[str, Any],
    atr_list: List[float],
    idx: int
) -> Dict[str, Any]:
    if idx < 15 or len(candles) < 20:
        return {
            "regime": "RANGE",
            "desc": "Insufficient history, defaulting to Range regime.",
            "eligible_bull_setups": ["SUPPORT_REJECTION", "HIGHER_LOW_REVERSAL", "BREAKOUT_RETEST"],
            "eligible_bear_setups": ["RESISTANCE_REJECTION", "LOWER_HIGH_REVERSAL", "BREAKDOWN_RETEST"],
            "min_separation_required": 15.0,
            "min_rvol_breakout": 1.40,
            "score_cap": 100.0,
            "is_high_volatility": False
        }

    c_now = float(candles[idx]["close"])
    c_prev10 = float(candles[idx - 10]["close"])
    pct_drift = (c_now - c_prev10) / (c_prev10 or 1.0) * 100.0

    recent_atr = atr_list[idx]
    avg_atr = sum(atr_list[idx - 15 : idx + 1]) / 16 if idx >= 15 else recent_atr
    is_volatility_spike = (avg_atr > 0) and (recent_atr / avg_atr > 1.65)

    is_bull_stack = trend_data.get("is_bull_stack", False)
    is_bear_stack = trend_data.get("is_bear_stack", False)

    # 1. High Volatility Regime
    if is_volatility_spike:
        return {
            "regime": "HIGH_VOLATILITY",
            "desc": f"High Volatility Regime (ATR spike {recent_atr/avg_atr:.2f}x normal). Requiring heightened confirmation.",
            "eligible_bull_setups": ["BREAKOUT_RETEST", "SUPPORT_REJECTION"],
            "eligible_bear_setups": ["BREAKDOWN_RETEST", "RESISTANCE_REJECTION"],
            "min_separation_required": 22.0, # Heightened separation
            "min_rvol_breakout": 1.70,        # Higher volume needed
            "score_cap": 85.0,
            "is_high_volatility": True
        }

    # 2. Trending Up Regime
    if is_bull_stack and pct_drift > 0.20:
        return {
            "regime": "TRENDING_UP",
            "desc": "Bullish Trend (EMA 9 >= 21 >= 50 stack with positive drift). Prioritizing pullbacks and breakouts.",
            "eligible_bull_setups": [
                "PULLBACK_CONTINUATION", "HIGHER_LOW_REVERSAL", "BREAKOUT_RETEST",
                "MOMENTUM_ACCELERATION", "INSIDE_BAR_BREAKOUT", "SUPPORT_REJECTION"
            ],
            "eligible_bear_setups": [
                "RESISTANCE_REJECTION" # Only strong resistance rejection permitted; aggressive shorting suppressed
            ],
            "min_separation_required": 14.0,
            "min_rvol_breakout": 1.35,
            "score_cap": 100.0,
            "is_high_volatility": False
        }

    # 3. Trending Down Regime
    if is_bear_stack and pct_drift < -0.20:
        return {
            "regime": "TRENDING_DOWN",
            "desc": "Bearish Trend (EMA 9 <= 21 <= 50 stack with negative drift). Prioritizing breakdown retests and rally rejections.",
            "eligible_bull_setups": [
                "SUPPORT_REJECTION" # Only strong support bounce permitted; aggressive buying suppressed
            ],
            "eligible_bear_setups": [
                "PULLBACK_CONTINUATION", "LOWER_HIGH_REVERSAL", "BREAKDOWN_RETEST",
                "MOMENTUM_ACCELERATION", "INSIDE_BAR_BREAKDOWN", "RESISTANCE_REJECTION"
            ],
            "min_separation_required": 14.0,
            "min_rvol_breakout": 1.35,
            "score_cap": 100.0,
            "is_high_volatility": False
        }

    # 4. Range-Bound Regime
    return {
        "regime": "RANGE",
        "desc": "Range-Bound Market. Prioritizing Support bounce CALLs and Resistance rejection PUTs.",
        "eligible_bull_setups": ["SUPPORT_REJECTION", "HIGHER_LOW_REVERSAL", "INSIDE_BAR_BREAKOUT"],
        "eligible_bear_setups": ["RESISTANCE_REJECTION", "LOWER_HIGH_REVERSAL", "INSIDE_BAR_BREAKDOWN"],
        "min_separation_required": 16.0,
        "min_rvol_breakout": 1.50,
        "score_cap": 90.0,
        "is_high_volatility": False
    }
