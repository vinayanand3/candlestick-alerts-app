"""
Index & Equity Options Intelligence Engine.
Computes recommended Call/Put strikes, Delta profile, Expiration horizon, and projected Option P&L for SPX, NDX, and equities.
"""

from typing import Dict, Any

def get_options_intelligence(
    symbol: str,
    direction: str,
    current_price: float,
    entry_price: float,
    stop_loss: float,
    target_1: float,
    target_2: float,
    target_3: float,
    atr_val: float,
    timeframe: str = "15m"
) -> Dict[str, Any]:
    sym = symbol.upper()
    is_index = sym in ["SPX", "^GSPC", "NDX", "^NDX"]

    if direction not in ["CALL", "PUT"]:
        return {
            "symbol": sym,
            "is_index": is_index,
            "recommended_contract": None,
            "contract_notes": "No option scenario is shown until a directional setup exists.",
        }
    
    # 1. Strike Spacing
    if sym in ["SPX", "^GSPC"]:
        strike_step = 5.0
        contract_type = "SPXW (Cash-Settled S&P 500 Index)"
    elif sym in ["NDX", "^NDX"]:
        strike_step = 25.0
        contract_type = "NDXP (Cash-Settled Nasdaq-100 Index)"
    elif sym in ["TSLA", "META"]:
        strike_step = 5.0
        contract_type = f"{sym} Standard American Equity Option"
    else:
        strike_step = 2.5
        contract_type = f"{sym} Standard American Equity Option"

    effective_dir = direction

    # 2. Strike Selection
    atm_strike = round(current_price / strike_step) * strike_step

    if effective_dir == "CALL":
        itm_strike = atm_strike - strike_step
        otm_strike = atm_strike + strike_step
        recommended_strike = atm_strike
        action_verb = "CALL"
    else:
        itm_strike = atm_strike + strike_step
        otm_strike = atm_strike - strike_step
        recommended_strike = atm_strike
        action_verb = "PUT"

    # 3. Expiration Recommendation
    if timeframe in ["1m", "5m"]:
        recommended_expiry = "0-1 DTE (Intraday Scalp / 0DTE)"
        iv_factor = 0.0028
    elif timeframe == "15m":
        recommended_expiry = "1-3 DTE (Short-Term Momentum)"
        iv_factor = 0.0042
    else:
        recommended_expiry = "3-7 DTE (Weekly Trend Continuation)"
        iv_factor = 0.0075

    # 4. Estimated Contract Pricing & Returns
    # Rough baseline ATM premium model based on spot price and time horizon
    est_premium = max(1.50, round(current_price * iv_factor, 2))
    if is_index and sym in ["SPX", "^GSPC"]:
        est_premium = max(12.0, round(current_price * iv_factor, 1))
    elif is_index and sym in ["NDX", "^NDX"]:
        est_premium = max(45.0, round(current_price * iv_factor, 1))

    # Delta assumptions: ATM = 0.50, ITM = 0.65, OTM = 0.35
    delta = 0.50
    t1_dist = abs(target_1 - entry_price)
    t2_dist = abs(target_2 - entry_price)
    risk_dist = abs(entry_price - stop_loss)

    t1_gain = round(t1_dist * delta, 2)
    t2_gain = round(t2_dist * delta, 2)
    loss_at_stop = round(risk_dist * delta, 2)

    t1_roi_pct = round((t1_gain / est_premium) * 100.0, 1) if est_premium > 0 else 0.0
    t2_roi_pct = round((t2_gain / est_premium) * 100.0, 1) if est_premium > 0 else 0.0
    max_loss_pct = min(100.0, round((loss_at_stop / est_premium) * 100.0, 1)) if est_premium > 0 else 0.0

    return {
        "symbol": sym,
        "is_index": is_index,
        "contract_type": contract_type,
        "recommended_contract": f"{sym} ${recommended_strike:.0f} {action_verb}",
        "action_verb": action_verb,
        "atm_strike": recommended_strike,
        "itm_strike": itm_strike,
        "otm_strike": otm_strike,
        "recommended_expiry": recommended_expiry,
        "delta_profile": "0.50 ATM (Balanced Gamma/Theta)",
        "estimated_premium": f"${est_premium:.2f}",
        "target_1_contract_target": f"${(est_premium + t1_gain):.2f} (+{t1_roi_pct}%)",
        "target_2_contract_target": f"${(est_premium + t2_gain):.2f} (+{t2_roi_pct}%)",
        "invalidation_contract_stop": f"${max(0.10, est_premium - loss_at_stop):.2f} (-{max_loss_pct}%)",
        "contract_notes": (
            "Cash-settled European style (No early exercise risk, Section 1256 60/40 tax treatment)."
            if is_index else "Standard equity options (Monitor earnings and assignment risk)."
        )
    }
