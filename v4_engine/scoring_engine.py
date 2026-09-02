"""
Scoring Engine — 3-Layer Scoring Model (Context 35, Setup 35, Confirmation 30).
Calculates Bull Score, Bear Score, Directional Separation, and CALL / PUT / NEUTRAL decisions.
Enforces score caps for missing setups, immediate structural obstacles, and insufficient separation.
"""

from typing import Dict, Any, Tuple

def evaluate_3layer_score(
    regime_data: Dict[str, Any],
    trend_data: Dict[str, Any],
    sr_data: Dict[str, Any],
    setup_data: Dict[str, Any],
    candle_data: Dict[str, Any],
    volume_data: Dict[str, Any],
    momentum_data: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    scoring_cfg = config.get("scoring", {})
    min_call_threshold = scoring_cfg.get("min_call_score", 75.0)
    min_put_threshold = scoring_cfg.get("min_put_score", 75.0)
    min_separation = regime_data.get("min_separation_required", 15.0)

    # -------------------------------------------------------------
    # 1. CONTEXT LAYER (Max 35 points)
    # -------------------------------------------------------------
    ctx_bull = 0.0
    ctx_bear = 0.0

    # A. Regime compatibility (+10 pts)
    regime = regime_data.get("regime", "RANGE")
    if regime == "TRENDING_UP":
        ctx_bull += 10.0
    elif regime == "TRENDING_DOWN":
        ctx_bear += 10.0
    elif regime == "RANGE":
        ctx_bull += 5.0
        ctx_bear += 5.0

    # B. Trend & EMA stack (+15 pts)
    if trend_data.get("is_bull_stack"):
        ctx_bull += 15.0
    elif trend_data.get("is_bear_stack"):
        ctx_bear += 15.0
    elif trend_data.get("structural_hh_hl"):
        ctx_bull += 8.0
    elif trend_data.get("structural_lh_ll"):
        ctx_bear += 8.0

    # C. S/R & Structural Location (+10 pts)
    if sr_data.get("near_support_bounce"):
        ctx_bull += 10.0
    elif sr_data.get("retest_res_hold"):
        ctx_bull += 10.0
    elif trend_data.get("pullback_bull"):
        ctx_bull += 7.0

    if sr_data.get("near_res_rejection"):
        ctx_bear += 10.0
    elif sr_data.get("retest_sup_fail"):
        ctx_bear += 10.0
    elif trend_data.get("pullback_bear"):
        ctx_bear += 7.0

    ctx_bull = min(35.0, ctx_bull)
    ctx_bear = min(35.0, ctx_bear)

    # -------------------------------------------------------------
    # 2. SETUP LAYER (Max 35 points)
    # -------------------------------------------------------------
    setup_score_bull = float(setup_data.get("score_bull", 0))
    setup_score_bear = float(setup_data.get("score_bear", 0))

    candle_score_bull = min(15.0, float(candle_data.get("score_bull", 0)))
    candle_score_bear = min(15.0, float(candle_data.get("score_bear", 0)))

    stp_bull = min(35.0, setup_score_bull + candle_score_bull)
    stp_bear = min(35.0, setup_score_bear + candle_score_bear)

    # -------------------------------------------------------------
    # 3. CONFIRMATION LAYER (Max 30 points)
    # -------------------------------------------------------------
    cnf_bull = 0.0
    cnf_bear = 0.0

    # A. Volume RVOL (+10 pts)
    rvol = volume_data.get("rvol", 1.0)
    if rvol >= 1.35:
        if candle_data.get("is_bull_close"):
            cnf_bull += 10.0
        elif candle_data.get("is_bear_close"):
            cnf_bear += 10.0
        else:
            cnf_bull += 5.0
            cnf_bear += 5.0
    elif rvol >= 1.10:
        if candle_data.get("is_bull_close"):
            cnf_bull += 7.0
        elif candle_data.get("is_bear_close"):
            cnf_bear += 7.0
        else:
            cnf_bull += 4.0
            cnf_bear += 4.0
    elif rvol >= 0.85:
        if candle_data.get("is_bull_close"):
            cnf_bull += 4.0
        elif candle_data.get("is_bear_close"):
            cnf_bear += 4.0

    # B. Momentum & RSI/MACD (+10 pts)
    rsi = momentum_data.get("rsi", 50.0)
    macd_hist = momentum_data.get("macd_hist", 0.0)
    
    # Bullish momentum
    if (48.0 <= rsi <= 75.0) and macd_hist >= 0:
        cnf_bull += 10.0
    elif (45.0 <= rsi <= 75.0) or macd_hist >= 0 or momentum_data.get("is_accelerating_bull"):
        cnf_bull += 6.0
    elif (42.0 <= rsi < 45.0):
        cnf_bull += 3.0

    # Bearish momentum
    if (25.0 <= rsi <= 52.0) and macd_hist <= 0:
        cnf_bear += 10.0
    elif (25.0 <= rsi <= 55.0) or macd_hist <= 0 or momentum_data.get("is_accelerating_bear"):
        cnf_bear += 6.0
    elif (52.0 < rsi <= 58.0):
        cnf_bear += 3.0

    # C. Location-Qualified Divergence (+10 pts)
    div = momentum_data.get("divergence", {})
    if div.get("bullish"):
        cnf_bull += 10.0
    elif div.get("bearish"):
        cnf_bear += 10.0

    cnf_bull = min(30.0, cnf_bull)
    cnf_bear = min(30.0, cnf_bear)

    # Raw Sums
    raw_bull_score = round(ctx_bull + stp_bull + cnf_bull, 1)
    raw_bear_score = round(ctx_bear + stp_bear + cnf_bear, 1)

    # -------------------------------------------------------------
    # 4. SCORE CAPS & HARD CONSTRAINTS
    # -------------------------------------------------------------
    active_setup = setup_data.get("active_setup")
    has_bull_setup = active_setup and active_setup.get("direction") == "CALL"
    has_bear_setup = active_setup and active_setup.get("direction") == "PUT"

    applied_caps = []

    # Cap 1: No Setup Cap (<= 59.0)
    if not has_bull_setup and raw_bull_score > 59.0:
        raw_bull_score = 59.0
        applied_caps.append("Bull Score capped at 59.0 (No valid Bullish Setup)")
    if not has_bear_setup and raw_bear_score > 59.0:
        raw_bear_score = 59.0
        applied_caps.append("Bear Score capped at 59.0 (No valid Bearish Setup)")

    # Cap 2: Immediate Obstacle Cap (<= 60.0)
    if sr_data.get("immediate_resistance_ahead") and raw_bull_score > 60.0:
        raw_bull_score = 60.0
        applied_caps.append("Bull Score capped at 60.0 (Immediate Overhead Resistance <0.5% away)")
    if sr_data.get("immediate_support_ahead") and raw_bear_score > 60.0:
        raw_bear_score = 60.0
        applied_caps.append("Bear Score capped at 60.0 (Immediate Support Floor <0.5% away)")

    # Cap 3: Regime Score Cap
    regime_cap = regime_data.get("score_cap", 100.0)
    raw_bull_score = min(regime_cap, raw_bull_score)
    raw_bear_score = min(regime_cap, raw_bear_score)

    # -------------------------------------------------------------
    # 5. DIRECTIONAL SEPARATION & DECISION
    # -------------------------------------------------------------
    separation = round(abs(raw_bull_score - raw_bear_score), 1)

    direction = "NEUTRAL"
    is_valid_call = (
        raw_bull_score >= min_call_threshold and
        (raw_bull_score - raw_bear_score) >= min_separation and
        has_bull_setup
    )
    is_valid_put = (
        raw_bear_score >= min_put_threshold and
        (raw_bear_score - raw_bull_score) >= min_separation and
        has_bear_setup
    )

    if is_valid_call:
        direction = "CALL"
        final_signal_score = raw_bull_score
    elif is_valid_put:
        direction = "PUT"
        final_signal_score = raw_bear_score
    else:
        direction = "NEUTRAL"
        final_signal_score = max(raw_bull_score, raw_bear_score)

    return {
        "direction": direction,
        "signal_score": final_signal_score,
        "bull_score": raw_bull_score,
        "bear_score": raw_bear_score,
        "directional_separation": separation,
        "min_separation_required": min_separation,
        "layers": {
            "context": {"bull": ctx_bull, "bear": ctx_bear, "max": 35.0},
            "setup": {"bull": stp_bull, "bear": stp_bear, "max": 35.0},
            "confirmation": {"bull": cnf_bull, "bear": cnf_bear, "max": 30.0}
        },
        "applied_caps": applied_caps,
        "setup_id": active_setup.get("setup_id") if active_setup else "NO_SETUP"
    }
