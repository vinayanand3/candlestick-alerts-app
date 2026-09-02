"""
Layer 7 — Volume Engine.
Calculates Relative Volume (RVOL), volume expansion/contraction, and breakout volume verification.
"""

from typing import List, Dict, Any
from v4_engine.trend_engine import calculate_sma

def analyze_volume(volumes: List[float], idx: int, period: int = 20) -> Dict[str, Any]:
    if not volumes or idx < 0:
        return {"rvol": 1.0, "is_expansion": False, "is_breakout_vol": False, "desc": "No volume data"}

    vol_sma = calculate_sma(volumes, period)
    c_vol = volumes[idx]
    avg_vol = vol_sma[idx] if vol_sma[idx] > 0 else 1.0
    rvol = c_vol / avg_vol

    is_expansion = rvol >= 1.25
    is_breakout_vol = rvol >= 1.45
    is_climax_vol = rvol >= 2.50
    is_contraction = rvol <= 0.65

    if is_climax_vol:
        desc = f"Volume Climax ({rvol:.2f}x avg)"
    elif is_breakout_vol:
        desc = f"Breakout Volume Surge ({rvol:.2f}x avg)"
    elif is_expansion:
        desc = f"Volume Expansion ({rvol:.2f}x avg)"
    elif is_contraction:
        desc = f"Volume Contraction / Drying ({rvol:.2f}x avg)"
    else:
        desc = f"Average Volume ({rvol:.2f}x avg)"

    return {
        "volume": round(c_vol, 0),
        "avg_volume": round(avg_vol, 0),
        "rvol": round(rvol, 2),
        "is_expansion": is_expansion,
        "is_breakout_vol": is_breakout_vol,
        "is_climax_vol": is_climax_vol,
        "is_contraction": is_contraction,
        "desc": desc
    }
