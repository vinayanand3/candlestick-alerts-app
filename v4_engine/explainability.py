"""
Explainability Engine — Generates machine-readable reason codes and 7-point structured decision explanations.
"""

from typing import Dict, Any, List, Optional

def build_explainability_report(
    symbol: str,
    timeframe: str,
    direction: str,
    setup_data: Dict[str, Any],
    scoring_data: Dict[str, Any],
    regime_data: Dict[str, Any],
    market_risk_data: Dict[str, Any],
    risk_data: Dict[str, Any],
    trend_data: Dict[str, Any],
    volume_data: Dict[str, Any],
    momentum_data: Dict[str, Any],
    sr_data: Dict[str, Any],
    candles: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    score = scoring_data.get("signal_score", 0.0)
    setup_id = setup_data.get("setup_id", "NO_SETUP")
    regime = regime_data.get("regime", "RANGE")
    risk_state = market_risk_data.get("risk_state", "NORMAL")

    # 1. Machine-Readable Reason Codes
    reason_codes = []
    confirmation_flags = []
    risk_flags = []

    # Trend Codes
    if trend_data.get("is_bull_stack"):
        reason_codes.append("EMA_BULL_ALIGNMENT")
    elif trend_data.get("is_bear_stack"):
        reason_codes.append("EMA_BEAR_ALIGNMENT")
    if trend_data.get("structural_hh_hl"):
        reason_codes.append("HIGHER_LOW_STRUCTURE")
    elif trend_data.get("structural_lh_ll"):
        reason_codes.append("LOWER_HIGH_STRUCTURE")

    # S/R Codes
    if sr_data.get("near_support_bounce"):
        reason_codes.append("SUPPORT_REJECTION")
    elif sr_data.get("near_res_rejection"):
        reason_codes.append("RESISTANCE_REJECTION")
    if sr_data.get("retest_res_hold"):
        reason_codes.append("BREAKOUT_RETEST_HELD")
    elif sr_data.get("retest_sup_fail"):
        reason_codes.append("BREAKDOWN_RETEST_FAILED")

    # Confirmation Flags
    if volume_data.get("is_breakout_vol"):
        confirmation_flags.append("BREAKOUT_VOLUME_SURGE")
    elif volume_data.get("is_expansion"):
        confirmation_flags.append("RVOL_EXPANSION")
    if momentum_data.get("is_accelerating_bull") or momentum_data.get("is_accelerating_bear"):
        confirmation_flags.append("MOMENTUM_ACCELERATION")
    if momentum_data.get("divergence", {}).get("bullish"):
        confirmation_flags.append("BULLISH_DIVERGENCE")
    elif momentum_data.get("divergence", {}).get("bearish"):
        confirmation_flags.append("BEARISH_DIVERGENCE")

    # Risk Flags
    if sr_data.get("immediate_resistance_ahead"):
        risk_flags.append("NEAR_MAJOR_RESISTANCE")
    if sr_data.get("immediate_support_ahead"):
        risk_flags.append("NEAR_MAJOR_SUPPORT")
    if market_risk_data.get("is_veto"):
        risk_flags.append("MARKET_RISK_VETO")
    if not risk_data.get("risk_passed"):
        risk_flags.append("RR_REJECTED")

    # 2. Plain-English 7 Core Explainability Answers
    if direction == "CALL":
        why_dir = f"Bullish thesis confirmed with Signal Score {score:.0f}/100 and +{scoring_data.get('directional_separation', 0):.0f} directional separation."
        what_failed = f"Immediate risk: overhead supply barrier at ${sr_data.get('nearest_resistance', 0):.2f} or broad market volatility expansion."
    elif direction == "PUT":
        why_dir = f"Bearish thesis confirmed with Signal Score {score:.0f}/100 and +{scoring_data.get('directional_separation', 0):.0f} directional separation."
        what_failed = f"Immediate risk: support demand shelf at ${sr_data.get('nearest_support', 0):.2f} or short squeeze rebound."
    else:
        why_dir = "Market is in neutral balance. No directional edge meets the 75/100 threshold."
        what_failed = "Choppy price action without directional separation."

    # 3. Actionable Next Trigger Checklist (for Waiting/Watch or In-Trade progression)
    next_triggers = []
    c_now = float(candles[-1]["close"]) if candles else 0.0

    # Price Trigger
    if direction == "PUT" or (scoring_data.get("bear_score", 0) > scoring_data.get("bull_score", 0)):
        sup_level = sr_data.get("nearest_support")
        if sup_level:
            is_met = c_now <= sup_level
            next_triggers.append({
                "condition": f"Breakdown close < ${sup_level:.2f} (Support)",
                "status": "MET" if is_met else "PENDING",
                "current": f"${c_now:.2f}"
            })
    else:
        res_level = sr_data.get("nearest_resistance")
        if res_level:
            is_met = c_now >= res_level
            next_triggers.append({
                "condition": f"Breakout close > ${res_level:.2f} (Resistance)",
                "status": "MET" if is_met else "PENDING",
                "current": f"${c_now:.2f}"
            })

    # Volume Trigger
    rvol = volume_data.get("rvol", 1.0)
    vol_met = rvol >= 1.25
    next_triggers.append({
        "condition": "Volume Expansion RVOL >= 1.25x",
        "status": "MET" if vol_met else "PENDING",
        "current": f"{rvol:.2f}x avg"
    })

    # Momentum Trigger
    rsi = momentum_data.get("rsi", 50.0)
    macd_hist = momentum_data.get("macd_hist", 0.0)
    if direction == "PUT":
        mom_met = rsi <= 50.0 and macd_hist <= 0
        cond_text = "RSI <= 50 & MACD Histogram <= 0"
    else:
        mom_met = rsi >= 50.0 and macd_hist >= 0
        cond_text = "RSI >= 50 & MACD Histogram >= 0"
    next_triggers.append({
        "condition": cond_text,
        "status": "MET" if mom_met else "PENDING",
        "current": f"RSI {rsi:.1f}, Hist {macd_hist:+.3f}"
    })

    q_and_a = {
        "why_direction": why_dir,
        "why_now": f"Trigger candle with RVOL {volume_data.get('rvol', 1.0)}x expansion and {momentum_data.get('desc', 'favorable momentum')}.",
        "setup_type": setup_id,
        "confirmation_factors": confirmation_flags or ["Standard Moving Average & Trend Alignment"],
        "invalidation_level": f"${risk_data.get('stop_loss', 0):.2f} (Risk distance: ${risk_data.get('risk_distance', 0):.2f})",
        "targets": f"T1: ${risk_data.get('target_1', 0):.2f} (50% scale-out) | T2: ${risk_data.get('target_2', 0):.2f} (30% scale-out) | T3: ${risk_data.get('target_3', 0):.2f} (Runner)",
        "failure_risks": what_failed
    }

    return {
        "reason_codes": reason_codes,
        "confirmation_flags": confirmation_flags,
        "risk_flags": risk_flags,
        "explainability": q_and_a,
        "next_triggers": next_triggers
    }
