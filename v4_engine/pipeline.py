"""
V4 Trading Alert Pipeline Orchestrator.
Coordinates all 12 modular layers into a single production-grade signal engine.
"""

from typing import List, Dict, Any, Optional
from v4_engine.config import V4_DEFAULT_CONFIG
from v4_engine.data_normalizer import validate_and_normalize_candles
from v4_engine.trend_engine import analyze_trend
from v4_engine.momentum_engine import calculate_rsi, calculate_macd, calculate_atr, analyze_momentum
from v4_engine.volume_engine import analyze_volume
from v4_engine.sr_engine import identify_key_levels, analyze_sr_context
from v4_engine.regime_engine import classify_market_regime
from v4_engine.candle_engine import analyze_candle_structure
from v4_engine.setup_engine import detect_setups
from v4_engine.scoring_engine import evaluate_3layer_score
from v4_engine.market_risk_engine import evaluate_market_risk
from v4_engine.risk_target_engine import calculate_structural_targets_and_risk
from v4_engine.state_machine import SignalStateMachine
from v4_engine.alert_filter import AlertDeduplicator
from v4_engine.explainability import build_explainability_report
from v4_engine.options_engine import get_options_intelligence

class V4Pipeline:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or V4_DEFAULT_CONFIG

    def analyze(self, raw_candles: List[Dict[str, Any]], symbol: str = "TSLA", timeframe: str = "15m") -> Dict[str, Any]:
        # Each request deterministically replays the supplied candle window. Keeping
        # these objects on the V4Pipeline instance caused repeated HTTP polls to
        # process old candles again and allowed one symbol's trade state to leak
        # into another symbol. Durable live state belongs in a keyed persistence
        # layer, not in this calculation object.
        state_machine = SignalStateMachine(self.config)
        deduplicator = AlertDeduplicator(
            self.config.get("state_machine", {}).get("score_refresh_delta", 8.0)
        )
        candles, warnings = validate_and_normalize_candles(raw_candles)
        n = len(candles)
        if n < 20:
            return {"symbol": symbol, "error": "Insufficient valid candles", "candles": candles, "alerts": []}

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        volumes = [float(c["volume"]) for c in candles]

        # Calculate indicators
        atr14 = calculate_atr(candles, 14)
        rsi14 = calculate_rsi(closes, 14)
        macd_line, macd_sig, macd_hist = calculate_macd(closes)

        supports, resistances = identify_key_levels(candles)

        # Run history step-by-step through state machine
        alerts = []
        active_signal = None
        latest_analysis = {}

        for i in range(15, n):
            trend_data = analyze_trend(closes, highs, lows, i)
            momentum_data = analyze_momentum(candles, closes, rsi14, macd_hist, i)
            volume_data = analyze_volume(volumes, i)
            sr_data = analyze_sr_context(candles, supports, resistances, i)
            regime_data = classify_market_regime(candles, trend_data, atr14, i)
            candle_data = analyze_candle_structure(candles, i, avg_atr=atr14[i])

            setup_data = detect_setups(
                candles, i, regime_data, trend_data, momentum_data, volume_data, sr_data, candle_data, atr14[i]
            )

            scoring_data = evaluate_3layer_score(
                regime_data, trend_data, sr_data, setup_data, candle_data, volume_data, momentum_data, self.config
            )

            market_risk_data = evaluate_market_risk(candles, atr14, i)

            # Risk & Target calculation
            c_close = closes[i]
            inval = setup_data["active_setup"]["invalidation"] if setup_data.get("active_setup") else (c_close - 1.5 * atr14[i])
            risk_data = calculate_structural_targets_and_risk(
                c_close, scoring_data["direction"], sr_data, atr14[i], inval, self.config
            )

            # Apply market risk veto
            if market_risk_data.get("is_veto"):
                scoring_data["direction"] = "NEUTRAL"
                scoring_data["applied_caps"].append("MARKET_RISK_VETO: New signals blocked due to extreme market risk.")

            # Process state machine
            sig, new_events = state_machine.process_candle(
                candles[i], scoring_data, risk_data, regime_data, atr14[i]
            )

            # Deduplicate & Filter alerts
            for evt in new_events:
                if deduplicator.should_emit_alert(symbol, timeframe, evt):
                    alerts.append(evt)

            if i == n - 1:
                active_signal = sig
                options_data = get_options_intelligence(
                    symbol, scoring_data["direction"], closes[-1],
                    risk_data.get("entry_price", closes[-1]),
                    risk_data.get("stop_loss", closes[-1] * 0.98),
                    risk_data.get("target_1", closes[-1] * 1.02),
                    risk_data.get("target_2", closes[-1] * 1.04),
                    risk_data.get("target_3", closes[-1] * 1.06),
                    atr14[-1], timeframe
                )
                explain_data = build_explainability_report(
                    symbol, timeframe, scoring_data["direction"], setup_data, scoring_data,
                    regime_data, market_risk_data, risk_data, trend_data, volume_data, momentum_data, sr_data, candles
                )
                latest_analysis = {
                    "regime": regime_data,
                    "market_risk": market_risk_data,
                    "trend": trend_data,
                    "momentum": momentum_data,
                    "volume": volume_data,
                    "sr": sr_data,
                    "candle": candle_data,
                    "setup": setup_data,
                    "scoring": scoring_data,
                    "risk": risk_data,
                    "options": options_data,
                    "explainability": explain_data
                }

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles,
            "active_signal": active_signal,
            "alerts": alerts,
            "regime": latest_analysis.get("regime"),
            "market_risk": latest_analysis.get("market_risk"),
            "setup": latest_analysis.get("setup"),
            "scoring": latest_analysis.get("scoring"),
            "risk": latest_analysis.get("risk"),
            "options": latest_analysis.get("options"),
            "explainability": latest_analysis.get("explainability"),
            "indicators": {
                "ema9": latest_analysis.get("trend", {}).get("ema9"),
                "ema21": latest_analysis.get("trend", {}).get("ema21"),
                "ema50": latest_analysis.get("trend", {}).get("ema50"),
                "rsi": latest_analysis.get("momentum", {}).get("rsi"),
                "macd_hist": latest_analysis.get("momentum", {}).get("macd_hist"),
                "rvol": latest_analysis.get("volume", {}).get("rvol"),
                "atr": round(atr14[-1], 2),
                "nearest_sup": latest_analysis.get("sr", {}).get("nearest_support"),
                "nearest_res": latest_analysis.get("sr", {}).get("nearest_resistance"),
            }
        }

    def analyze_latest(self, candles: List[Dict[str, Any]], symbol: str = "TSLA") -> Dict[str, Any]:
        return self.analyze(candles, symbol=symbol)
