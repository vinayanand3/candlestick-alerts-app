"""
Layer 8 — Support / Resistance & Breakout/Retest Engine.
Identifies dynamic swing levels, horizontal clusters, proximity checks, and retest holding/failing.
"""

from typing import List, Dict, Any, Tuple

def identify_key_levels(candles: List[Dict[str, Any]], window: int = 4) -> Tuple[List[float], List[float]]:
    supports = []
    resistances = []
    n = len(candles)
    if n < window * 2 + 1:
        return supports, resistances

    for i in range(window, n - window):
        low = float(candles[i]["low"])
        high = float(candles[i]["high"])
        
        is_pivot_low = all(low <= float(candles[j]["low"]) for j in range(i - window, i + window + 1))
        if is_pivot_low:
            supports.append(low)
            
        is_pivot_high = all(high >= float(candles[j]["high"]) for j in range(i - window, i + window + 1))
        if is_pivot_high:
            resistances.append(high)

    def cluster_levels(levels: List[float]) -> List[float]:
        if not levels:
            return []
        levels = sorted(levels)
        merged = [levels[0]]
        for l in levels[1:]:
            if (l - merged[-1]) / (merged[-1] or 1.0) < 0.005:
                merged[-1] = round((merged[-1] + l) / 2.0, 2)
            else:
                merged.append(round(l, 2))
        return merged

    return cluster_levels(supports)[-5:], cluster_levels(resistances)[-5:]

def analyze_sr_context(
    candles: List[Dict[str, Any]],
    supports: List[float],
    resistances: List[float],
    idx: int
) -> Dict[str, Any]:
    c_now = float(candles[idx]["close"])
    c_high = float(candles[idx]["high"])
    c_low = float(candles[idx]["low"])
    c_prev = float(candles[idx - 1]["close"]) if idx > 0 else c_now
    c_prev_high = float(candles[idx - 1]["high"]) if idx > 0 else c_high
    c_prev_low = float(candles[idx - 1]["low"]) if idx > 0 else c_low

    # Nearest S/R
    valid_sups = [s for s in supports if s < c_now]
    valid_res = [r for r in resistances if r > c_now]

    nearest_sup = max(valid_sups) if valid_sups else (c_now * 0.97)
    nearest_res = min(valid_res) if valid_res else (c_now * 1.03)

    dist_to_sup_pct = (c_now - nearest_sup) / (nearest_sup or 1.0) * 100.0
    dist_to_res_pct = (nearest_res - c_now) / (c_now or 1.0) * 100.0

    # Immediate Obstacle Check (<0.5% distance directly into ceiling or floor)
    immediate_resistance_ahead = dist_to_res_pct < 0.50
    immediate_support_ahead = dist_to_sup_pct < 0.50

    # Support bounce: low wicked near support (<0.5%) and closed green
    near_support_bounce = any(abs(c_low - s) / s < 0.006 for s in supports) and (c_now > float(candles[idx]["open"]))
    near_res_rejection = any(abs(c_high - r) / r < 0.006 for r in resistances) and (c_now < float(candles[idx]["open"]))

    # Breakout & Retest validation
    broke_above_res = any(c_prev <= r and c_now > r for r in resistances)
    broke_below_sup = any(c_prev >= s and c_now < s for s in supports)

    retest_res_hold = any(c_low <= r and c_now > r and c_prev > r for r in resistances)
    retest_sup_fail = any(c_high >= s and c_now < s and c_prev < s for s in supports)

    desc = []
    if near_support_bounce:
        desc.append(f"Support Bounce (${nearest_sup:.2f})")
    if near_res_rejection:
        desc.append(f"Resistance Rejection (${nearest_res:.2f})")
    if broke_above_res:
        desc.append("Breakout Above Resistance")
    if broke_below_sup:
        desc.append("Breakdown Below Support")
    if retest_res_hold:
        desc.append("Retest Holding as New Support")
    if retest_sup_fail:
        desc.append("Retest Failing at Old Support")

    return {
        "supports": supports,
        "resistances": resistances,
        "nearest_support": round(nearest_sup, 2),
        "nearest_resistance": round(nearest_res, 2),
        "dist_to_sup_pct": round(dist_to_sup_pct, 2),
        "dist_to_res_pct": round(dist_to_res_pct, 2),
        "immediate_resistance_ahead": immediate_resistance_ahead,
        "immediate_support_ahead": immediate_support_ahead,
        "near_support_bounce": near_support_bounce,
        "near_res_rejection": near_res_rejection,
        "broke_above_res": broke_above_res,
        "broke_below_sup": broke_below_sup,
        "retest_res_hold": retest_res_hold,
        "retest_sup_fail": retest_sup_fail,
        "desc": " | ".join(desc) if desc else f"Mid-Range (Sup: ${nearest_sup:.2f} [{dist_to_sup_pct:.1f}%], Res: ${nearest_res:.2f} [{dist_to_res_pct:.1f}%])"
    }
