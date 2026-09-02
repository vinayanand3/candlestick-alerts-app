"""
Backtester — Zero-Lookahead Simulation & Calibration Engine.
Evaluates historical performance broken down by Regime, Setup, and Score Bucket.
Tracks Expectancy, Profit Factor, Win/Loss Rate, Average R, and Maximum Drawdown.
"""

from typing import List, Dict, Any

def run_backtest(
    candles: List[Dict[str, Any]],
    symbol: str = "TSLA",
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    from v4_engine.pipeline import V4Pipeline
    pipeline = V4Pipeline(config=config)

    n = len(candles)
    if n < 35:
        return {"error": "Insufficient history for backtesting (minimum 35 candles required)."}

    # Simulate candle-by-candle (Strict Zero-Lookahead)
    completed_trades = []
    trade_in_progress = None

    for i in range(25, n):
        visible_candles = candles[:i + 1]
        analysis = pipeline.analyze_latest(visible_candles, symbol=symbol)
        curr_c = visible_candles[-1]
        c_time = curr_c["time"]
        c_high = float(curr_c["high"])
        c_low = float(curr_c["low"])
        c_close = float(curr_c["close"])

        # Check existing trade in progress
        if trade_in_progress:
            t = trade_in_progress
            sig_dir = t["direction"]
            entry_p = t["entry_price"]
            risk_dist = t["risk_distance"]

            if sig_dir == "CALL":
                # Check Target 1
                if not t["t1_hit"] and c_high >= t["target_1"]:
                    t["t1_hit"] = True
                    t["trailing_stop"] = max(t["trailing_stop"], entry_p) # Move to breakeven
                # Check Target 2
                if not t["t2_hit"] and c_high >= t["target_2"]:
                    t["t2_hit"] = True
                    t["trailing_stop"] = max(t["trailing_stop"], t["target_1"])

                # Check Stop / Invalidation
                if c_low <= t["trailing_stop"]:
                    exit_price = t["trailing_stop"]
                    pnl_r = round((exit_price - entry_p) / risk_dist, 2)
                    t["exit_time"] = c_time
                    t["exit_price"] = exit_price
                    t["pnl_r"] = pnl_r
                    t["outcome"] = "WIN" if pnl_r > 0 else ("BREAKEVEN" if pnl_r == 0 else "LOSS")
                    completed_trades.append(t)
                    trade_in_progress = None
                    continue

            else: # PUT
                if not t["t1_hit"] and c_low <= t["target_1"]:
                    t["t1_hit"] = True
                    t["trailing_stop"] = min(t["trailing_stop"], entry_p)
                if not t["t2_hit"] and c_low <= t["target_2"]:
                    t["t2_hit"] = True
                    t["trailing_stop"] = min(t["trailing_stop"], t["target_1"])

                if c_high >= t["trailing_stop"]:
                    exit_price = t["trailing_stop"]
                    pnl_r = round((entry_p - exit_price) / risk_dist, 2)
                    t["exit_time"] = c_time
                    t["exit_price"] = exit_price
                    t["pnl_r"] = pnl_r
                    t["outcome"] = "WIN" if pnl_r > 0 else ("BREAKEVEN" if pnl_r == 0 else "LOSS")
                    completed_trades.append(t)
                    trade_in_progress = None
                    continue

        # Check for new signal entry
        if trade_in_progress is None:
            active_sig = analysis.get("active_signal")
            scoring = analysis.get("scoring", {})
            risk = analysis.get("risk", {})
            regime = analysis.get("regime", {}).get("regime", "RANGE")
            setup_id = analysis.get("setup", {}).get("setup_id", "NO_SETUP")

            if active_sig and active_sig.get("state") == "ACTIVE" and risk.get("risk_passed"):
                # Avoid entering on the same candle if already entered
                trade_in_progress = {
                    "symbol": symbol,
                    "entry_time": c_time,
                    "direction": active_sig["direction"],
                    "setup_id": setup_id,
                    "regime": regime,
                    "score": scoring.get("signal_score", 75.0),
                    "score_bucket": "85+" if scoring.get("signal_score", 0) >= 85 else ("80-84" if scoring.get("signal_score", 0) >= 80 else "75-79"),
                    "entry_price": risk["entry_price"],
                    "stop_loss": risk["stop_loss"],
                    "trailing_stop": risk["stop_loss"],
                    "risk_distance": max(0.1, risk["risk_distance"]),
                    "target_1": risk["target_1"],
                    "target_2": risk["target_2"],
                    "t1_hit": False,
                    "t2_hit": False,
                }

    # Aggregate Statistics
    total_trades = len(completed_trades)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_r": 0.0,
            "avg_r": 0.0,
            "max_drawdown_r": 0.0,
            "by_regime": {},
            "by_setup": {},
            "by_score_bucket": {},
            "trades": []
        }

    wins = [t for t in completed_trades if t["pnl_r"] > 0]
    losses = [t for t in completed_trades if t["pnl_r"] < 0]
    be = [t for t in completed_trades if t["pnl_r"] == 0]

    win_rate = round(len(wins) / total_trades * 100.0, 1)
    loss_rate = round(len(losses) / total_trades * 100.0, 1)

    gross_gains_r = sum(t["pnl_r"] for t in wins)
    gross_losses_r = abs(sum(t["pnl_r"] for t in losses))
    profit_factor = round(gross_gains_r / gross_losses_r, 2) if gross_losses_r > 0 else round(gross_gains_r, 2)

    total_r = sum(t["pnl_r"] for t in completed_trades)
    avg_r = round(total_r / total_trades, 2)
    expectancy_r = round(((len(wins)/total_trades) * (gross_gains_r / len(wins) if wins else 0)) - ((len(losses)/total_trades) * (gross_losses_r / len(losses) if losses else 0)), 2)

    # Max Drawdown in R
    cum_r = 0.0
    peak_r = 0.0
    max_dd = 0.0
    for t in completed_trades:
        cum_r += t["pnl_r"]
        peak_r = max(peak_r, cum_r)
        max_dd = max(max_dd, peak_r - cum_r)

    # Breakdown by Regime
    by_regime = {}
    for t in completed_trades:
        r_name = t["regime"]
        if r_name not in by_regime:
            by_regime[r_name] = {"trades": 0, "wins": 0, "total_r": 0.0}
        by_regime[r_name]["trades"] += 1
        if t["pnl_r"] > 0:
            by_regime[r_name]["wins"] += 1
        by_regime[r_name]["total_r"] = round(by_regime[r_name]["total_r"] + t["pnl_r"], 2)

    for r_name, data in by_regime.items():
        data["win_rate"] = round(data["wins"] / data["trades"] * 100.0, 1)

    # Breakdown by Setup
    by_setup = {}
    for t in completed_trades:
        s_id = t["setup_id"]
        if s_id not in by_setup:
            by_setup[s_id] = {"trades": 0, "wins": 0, "total_r": 0.0}
        by_setup[s_id]["trades"] += 1
        if t["pnl_r"] > 0:
            by_setup[s_id]["wins"] += 1
        by_setup[s_id]["total_r"] = round(by_setup[s_id]["total_r"] + t["pnl_r"], 2)

    for s_id, data in by_setup.items():
        data["win_rate"] = round(data["wins"] / data["trades"] * 100.0, 1)

    # Breakdown by Score Bucket
    by_bucket = {}
    for t in completed_trades:
        b_id = t["score_bucket"]
        if b_id not in by_bucket:
            by_bucket[b_id] = {"trades": 0, "wins": 0, "total_r": 0.0}
        by_bucket[b_id]["trades"] += 1
        if t["pnl_r"] > 0:
            by_bucket[b_id]["wins"] += 1
        by_bucket[b_id]["total_r"] = round(by_bucket[b_id]["total_r"] + t["pnl_r"], 2)

    for b_id, data in by_bucket.items():
        data["win_rate"] = round(data["wins"] / data["trades"] * 100.0, 1)

    return {
        "symbol": symbol,
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "breakevens": len(be),
        "win_rate": win_rate,
        "loss_rate": loss_rate,
        "profit_factor": profit_factor,
        "expectancy_r": expectancy_r,
        "avg_r": avg_r,
        "total_r": round(total_r, 2),
        "max_drawdown_r": round(max_dd, 2),
        "by_regime": by_regime,
        "by_setup": by_setup,
        "by_score_bucket": by_bucket,
        "trades": completed_trades[-20:] # Last 20 trades
    }
