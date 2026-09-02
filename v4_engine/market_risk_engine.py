"""
Market Risk Engine — Market-Wide Risk Veto System.
Evaluates market volatility, gap expansions, and ATR multiples to issue NORMAL, ELEVATED, HIGH, or EXTREME risk state.
"""

from typing import List, Dict, Any

def evaluate_market_risk(
    candles: List[Dict[str, Any]],
    atr_list: List[float],
    idx: int
) -> Dict[str, Any]:
    if idx < 15 or len(candles) < 20:
        return {"risk_state": "NORMAL", "is_veto": False, "desc": "Market conditions normal."}

    c_now = float(candles[idx]["close"])
    c_open = float(candles[idx]["open"])
    c_prev = float(candles[idx - 1]["close"])

    recent_atr = atr_list[idx]
    avg_atr = sum(atr_list[idx - 15 : idx + 1]) / 16 if idx >= 15 else recent_atr
    atr_ratio = recent_atr / avg_atr if avg_atr > 0 else 1.0

    gap_pct = abs(c_open - c_prev) / (c_prev or 1.0) * 100.0

    if atr_ratio >= 2.2 or gap_pct >= 2.5:
        risk_state = "EXTREME"
        is_veto = True
        desc = f"EXTREME Volatility Veto (ATR spike {atr_ratio:.1f}x / Gap {gap_pct:.1f}%). New entries halted."
    elif atr_ratio >= 1.7 or gap_pct >= 1.5:
        risk_state = "HIGH"
        is_veto = False
        desc = f"HIGH Market Volatility (ATR ratio {atr_ratio:.1f}x). Requiring heightened confirmation."
    elif atr_ratio >= 1.3:
        risk_state = "ELEVATED"
        is_veto = False
        desc = f"ELEVATED Volatility (ATR ratio {atr_ratio:.1f}x)."
    else:
        risk_state = "NORMAL"
        is_veto = False
        desc = "Market Volatility & Risk Normal."

    return {
        "risk_state": risk_state,
        "is_veto": is_veto,
        "atr_ratio": round(atr_ratio, 2),
        "gap_pct": round(gap_pct, 2),
        "desc": desc
    }
