"""
Layer 3 — Setup Engine.
Detects 10 explicit, high-conviction setup types, enforcing regime eligibility filters.
"""

from typing import List, Dict, Any, Optional

def detect_setups(
    candles: List[Dict[str, Any]],
    idx: int,
    regime_data: Dict[str, Any],
    trend_data: Dict[str, Any],
    momentum_data: Dict[str, Any],
    volume_data: Dict[str, Any],
    sr_data: Dict[str, Any],
    candle_data: Dict[str, Any],
    atr_val: float
) -> Dict[str, Any]:
    if idx < 4:
        return {"active_setup": None, "setups_detected": [], "score_bull": 0, "score_bear": 0}

    c_now = float(candles[idx]["close"])
    c_open = float(candles[idx]["open"])
    c_high = float(candles[idx]["high"])
    c_low = float(candles[idx]["low"])

    c_prev = float(candles[idx - 1]["close"])
    c_prev_high = float(candles[idx - 1]["high"])
    c_prev_low = float(candles[idx - 1]["low"])

    eligible_bull = regime_data.get("eligible_bull_setups", [])
    eligible_bear = regime_data.get("eligible_bear_setups", [])

    detected_setups = []

    # 1. PULLBACK_CONTINUATION
    if trend_data.get("pullback_bull") and candle_data.get("is_bull_close"):
        if "PULLBACK_CONTINUATION" in eligible_bull:
            detected_setups.append({
                "setup_id": "PULLBACK_CONTINUATION",
                "direction": "CALL",
                "score": 20,
                "invalidation": round(min(c_low, trend_data["ema21"]) - (0.5 * atr_val), 2),
                "reason": f"Pullback to EMA9 (${trend_data['ema9']:.2f}) / EMA21 in Bullish Trend, holding structure."
            })

    if trend_data.get("pullback_bear") and candle_data.get("is_bear_close"):
        if "PULLBACK_CONTINUATION" in eligible_bear:
            detected_setups.append({
                "setup_id": "PULLBACK_CONTINUATION",
                "direction": "PUT",
                "score": 20,
                "invalidation": round(max(c_high, trend_data["ema21"]) + (0.5 * atr_val), 2),
                "reason": f"Pullback rally to EMA9 (${trend_data['ema9']:.2f}) / EMA21 in Bearish Trend, rejecting."
            })

    # 2. SUPPORT_REJECTION & RESISTANCE_REJECTION
    if sr_data.get("near_support_bounce") and (candle_data.get("is_hammer") or candle_data.get("is_bull_engulfing") or candle_data.get("is_bull_close")):
        if "SUPPORT_REJECTION" in eligible_bull:
            detected_setups.append({
                "setup_id": "SUPPORT_REJECTION",
                "direction": "CALL",
                "score": 20,
                "invalidation": round(c_low - (0.5 * atr_val), 2),
                "reason": f"Clean rejection & demand bounce at Support (${sr_data['nearest_support']:.2f})."
            })

    if sr_data.get("near_res_rejection") and (candle_data.get("is_shooting_star") or candle_data.get("is_bear_engulfing") or candle_data.get("is_bear_close")):
        if "RESISTANCE_REJECTION" in eligible_bear:
            detected_setups.append({
                "setup_id": "RESISTANCE_REJECTION",
                "direction": "PUT",
                "score": 20,
                "invalidation": round(c_high + (0.5 * atr_val), 2),
                "reason": f"Clean rejection & supply barrier at Resistance (${sr_data['nearest_resistance']:.2f})."
            })

    # 3. BREAKOUT_RETEST & BREAKDOWN_RETEST
    if sr_data.get("retest_res_hold") and volume_data.get("is_expansion") and candle_data.get("is_bull_close"):
        if "BREAKOUT_RETEST" in eligible_bull:
            detected_setups.append({
                "setup_id": "BREAKOUT_RETEST",
                "direction": "CALL",
                "score": 20,
                "invalidation": round(sr_data["nearest_resistance"] - (0.8 * atr_val), 2),
                "reason": f"Breakout and successful retest holding above ${sr_data['nearest_resistance']:.2f} on RVOL {volume_data['rvol']}x."
            })

    if sr_data.get("retest_sup_fail") and volume_data.get("is_expansion") and candle_data.get("is_bear_close"):
        if "BREAKDOWN_RETEST" in eligible_bear:
            detected_setups.append({
                "setup_id": "BREAKDOWN_RETEST",
                "direction": "PUT",
                "score": 20,
                "invalidation": round(sr_data["nearest_support"] + (0.8 * atr_val), 2),
                "reason": f"Breakdown and failed retest below ${sr_data['nearest_support']:.2f} on RVOL {volume_data['rvol']}x."
            })

    # 4. MOMENTUM_ACCELERATION
    if momentum_data.get("is_accelerating_bull") and volume_data.get("is_expansion") and c_now > c_open:
        if "MOMENTUM_ACCELERATION" in eligible_bull:
            detected_setups.append({
                "setup_id": "MOMENTUM_ACCELERATION",
                "direction": "CALL",
                "score": 18,
                "invalidation": round(c_low - (0.8 * atr_val), 2),
                "reason": f"Strong price ROC expansion (+{momentum_data['roc']:.2f}%) with RVOL {volume_data['rvol']}x."
            })

    if momentum_data.get("is_accelerating_bear") and volume_data.get("is_expansion") and c_now < c_open:
        if "MOMENTUM_ACCELERATION" in eligible_bear:
            detected_setups.append({
                "setup_id": "MOMENTUM_ACCELERATION",
                "direction": "PUT",
                "score": 18,
                "invalidation": round(c_high + (0.8 * atr_val), 2),
                "reason": f"Strong downward price ROC (-{abs(momentum_data['roc']):.2f}%) with RVOL {volume_data['rvol']}x."
            })

    # 5. HIGHER_LOW_REVERSAL & LOWER_HIGH_REVERSAL
    if trend_data.get("structural_hh_hl") and (momentum_data.get("divergence", {}).get("bullish") or candle_data.get("is_hammer")):
        if "HIGHER_LOW_REVERSAL" in eligible_bull:
            detected_setups.append({
                "setup_id": "HIGHER_LOW_REVERSAL",
                "direction": "CALL",
                "score": 18,
                "invalidation": round(c_low - (0.6 * atr_val), 2),
                "reason": "Higher Low structural pivot confirmed with momentum divergence support."
            })

    if trend_data.get("structural_lh_ll") and (momentum_data.get("divergence", {}).get("bearish") or candle_data.get("is_shooting_star")):
        if "LOWER_HIGH_REVERSAL" in eligible_bear:
            detected_setups.append({
                "setup_id": "LOWER_HIGH_REVERSAL",
                "direction": "PUT",
                "score": 18,
                "invalidation": round(c_high + (0.6 * atr_val), 2),
                "reason": "Lower High structural pivot confirmed with momentum divergence rejection."
            })

    # 6. INSIDE_BAR_BREAKOUT & INSIDE_BAR_BREAKDOWN
    if idx >= 2 and float(candles[idx - 1]["high"]) <= float(candles[idx - 2]["high"]) and float(candles[idx - 1]["low"]) >= float(candles[idx - 2]["low"]):
        # Prior candle was inside bar
        if c_now > float(candles[idx - 2]["high"]) and volume_data.get("is_expansion"):
            if "INSIDE_BAR_BREAKOUT" in eligible_bull:
                detected_setups.append({
                    "setup_id": "INSIDE_BAR_BREAKOUT",
                    "direction": "CALL",
                    "score": 17,
                    "invalidation": round(float(candles[idx - 1]["low"]) - (0.5 * atr_val), 2),
                    "reason": f"Inside bar compression expansion breakout above ${float(candles[idx - 2]['high']):.2f}."
                })
        elif c_now < float(candles[idx - 2]["low"]) and volume_data.get("is_expansion"):
            if "INSIDE_BAR_BREAKDOWN" in eligible_bear:
                detected_setups.append({
                    "setup_id": "INSIDE_BAR_BREAKDOWN",
                    "direction": "PUT",
                    "score": 17,
                    "invalidation": round(float(candles[idx - 1]["high"]) + (0.5 * atr_val), 2),
                    "reason": f"Inside bar compression breakdown below ${float(candles[idx - 2]['low']):.2f}."
                })

    # Select dominant setup
    dominant_setup = max(detected_setups, key=lambda s: s["score"]) if detected_setups else None

    score_bull = sum(s["score"] for s in detected_setups if s["direction"] == "CALL")
    score_bear = sum(s["score"] for s in detected_setups if s["direction"] == "PUT")

    return {
        "active_setup": dominant_setup,
        "setups_detected": detected_setups,
        "setup_id": dominant_setup["setup_id"] if dominant_setup else "NO_SETUP",
        "score_bull": min(35, score_bull),
        "score_bear": min(35, score_bear)
    }
