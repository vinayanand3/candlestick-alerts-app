"""
Risk & Target Engine — Structural Targets, Multi-Tier Scale-Outs, and Expected Value (EV) Gate.
Prioritizes Major S/R and Swing Pivots over blind ATR projections.
"""

from typing import Dict, Any, List

def calculate_structural_targets_and_risk(
    entry_price: float,
    direction: str,
    sr_data: Dict[str, Any],
    atr_val: float,
    invalidation_level: float,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    risk_cfg = config.get("risk", {})
    min_rr_threshold = risk_cfg.get("min_rr_ratio", 1.8)
    max_risk_pct = risk_cfg.get("max_risk_pct_of_price", 4.0)

    supports = sr_data.get("supports", [])
    resistances = sr_data.get("resistances", [])

    entry = entry_price

    if direction == "CALL":
        # Invalidation Stop: min(setup invalidation, entry - 1.2 * ATR)
        calculated_stop = invalidation_level if invalidation_level < entry else round(entry - (1.2 * atr_val), 2)
        stop_loss = round(min(calculated_stop, entry - (0.8 * atr_val)), 2)
        risk_dist = max(0.1, entry - stop_loss)

        # Target 1 (Structural or 1.5 ATR)
        nearest_res = [r for r in resistances if r > entry]
        if nearest_res and (nearest_res[0] - entry) >= (1.0 * atr_val):
            t1 = nearest_res[0]
            t1_type = "Structural Resistance"
        else:
            t1 = round(entry + (1.5 * atr_val), 2)
            t1_type = "1.5x ATR Expansion"

        # Target 2 (Major Resistance or 2.5 ATR)
        if len(nearest_res) > 1 and (nearest_res[1] - entry) >= (2.0 * atr_val):
            t2 = nearest_res[1]
            t2_type = "Major Structural Resistance"
        else:
            t2 = round(entry + (2.5 * atr_val), 2)
            t2_type = "2.5x ATR Expansion"

        # Target 3 (Runner or 4.0 ATR)
        t3 = round(max(nearest_res[-1] if nearest_res else entry + (4.0 * atr_val), t2 + (1.5 * atr_val)), 2)

        rr_t1 = round((t1 - entry) / risk_dist, 2)
        rr_t2 = round((t2 - entry) / risk_dist, 2)
        rr_t3 = round((t3 - entry) / risk_dist, 2)

    else: # PUT
        calculated_stop = invalidation_level if invalidation_level > entry else round(entry + (1.2 * atr_val), 2)
        stop_loss = round(max(calculated_stop, entry + (0.8 * atr_val)), 2)
        risk_dist = max(0.1, stop_loss - entry)

        # Target 1 (Structural Support or 1.5 ATR)
        nearest_sup = [s for s in supports if s < entry]
        if nearest_sup and (entry - nearest_sup[-1]) >= (1.0 * atr_val):
            t1 = nearest_sup[-1]
            t1_type = "Structural Support"
        else:
            t1 = round(entry - (1.5 * atr_val), 2)
            t1_type = "1.5x ATR Expansion"

        # Target 2 (Major Support or 2.5 ATR)
        if len(nearest_sup) > 1 and (entry - nearest_sup[0]) >= (2.0 * atr_val):
            t2 = nearest_sup[0]
            t2_type = "Major Structural Support"
        else:
            t2 = round(entry - (2.5 * atr_val), 2)
            t2_type = "2.5x ATR Expansion"

        t3 = round(min(nearest_sup[0] if nearest_sup else entry - (4.0 * atr_val), t2 - (1.5 * atr_val)), 2)

        rr_t1 = round((entry - t1) / risk_dist, 2)
        rr_t2 = round((entry - t2) / risk_dist, 2)
        rr_t3 = round((entry - t3) / risk_dist, 2)

    # Risk as % of entry price
    risk_pct = round((risk_dist / (entry or 1.0)) * 100.0, 2)

    # Expected Value (EV): P(T1)=65%, P(T2)=40%, P(Stop)=35%
    ev_r = round((0.65 * rr_t1) + (0.40 * (rr_t2 - rr_t1)) - (0.35 * 1.0), 2)

    # Gates
    rr_passed = rr_t2 >= min_rr_threshold
    risk_pct_passed = risk_pct <= max_risk_pct

    rejection_reasons = []
    if not rr_passed:
        rejection_reasons.append(f"R:R to T2 ({rr_t2}:1) below minimum threshold ({min_rr_threshold}:1)")
    if not risk_pct_passed:
        rejection_reasons.append(f"Stop distance risk ({risk_pct}%) exceeds max allowable ({max_risk_pct}%)")

    return {
        "entry_price": round(entry, 2),
        "entry_zone": f"${entry * 0.998:.2f} - ${entry * 1.002:.2f}",
        "stop_loss": round(stop_loss, 2),
        "initial_stop": round(stop_loss, 2),
        "risk_distance": round(risk_dist, 2),
        "risk_pct": risk_pct,
        "target_1": round(t1, 2),
        "target_2": round(t2, 2),
        "target_3": round(t3, 2),
        "t1_type": t1_type,
        "t2_type": t2_type,
        "rr_t1": rr_t1,
        "rr_t2": rr_t2,
        "rr_t3": rr_t3,
        "expected_value_r": ev_r,
        "risk_passed": rr_passed and risk_pct_passed,
        "rejection_reasons": rejection_reasons
    }
