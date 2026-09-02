"""
V4 Trading Alert Engine — Centralized Configuration Layer.
All scoring weights, indicator periods, risk parameters, thresholds, and cooldowns are defined here.
"""

from typing import Dict, Any

V4_DEFAULT_CONFIG: Dict[str, Any] = {
    # 1. Data Normalization
    "timezone": "America/New_York",
    "min_candles_required": 30,
    
    # 2. Market Regime Engine
    "regime": {
        "trend_ema_fast": 9,
        "trend_ema_mid": 21,
        "trend_ema_slow": 50,
        "trend_ema_anchor": 200,
        "atr_period": 14,
        "volatility_expansion_ratio": 1.65,
        "trend_drift_threshold_pct": 0.20,
    },
    
    # 3. 3-Layer Scoring Model (Max 100 pts)
    "scoring": {
        "context_max_score": 35.0,
        "setup_max_score": 35.0,
        "confirmation_max_score": 30.0,
        
        # Trigger thresholds (P2 Strong Alert at >= 68.0, P1 High-Confidence at >= 78.0)
        "min_call_score": 68.0,
        "min_put_score": 68.0,
        "min_directional_separation": 12.0,
        "no_setup_score_cap": 59.0,
        "immediate_obstacle_score_cap": 60.0,
        "extreme_volatility_score_cap": 75.0,
    },
    
    # 4. Indicators & Features
    "indicators": {
        "rsi_period": 14,
        "rsi_bull_min": 45.0,
        "rsi_bull_max": 75.0,
        "rsi_bear_min": 25.0,
        "rsi_bear_max": 55.0,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "rvol_moving_avg_period": 20,
        "rvol_normal_threshold": 1.25,
        "rvol_breakout_threshold": 1.45,
        "divergence_lookback": 15,
        "divergence_rsi_delta": 2.0,
    },
    
    # 5. Support / Resistance & Pivots
    "sr": {
        "pivot_window": 4,
        "cluster_tolerance_pct": 0.004,
        "proximity_threshold_pct": 0.006,
        "immediate_obstacle_pct": 0.005,
    },
    
    # 6. Risk Engine & Targets
    "risk": {
        "min_rr_ratio": 1.8,
        "stop_atr_multiplier": 1.2,
        "trailing_stop_atr_multiplier": 1.5,
        "t1_atr_multiplier": 1.5,
        "t2_atr_multiplier": 2.5,
        "t3_atr_multiplier": 4.0,
        "t1_scale_out_pct": 50.0,
        "t2_scale_out_pct": 30.0,
        "t3_runner_pct": 20.0,
        "max_risk_pct_of_price": 4.0,
    },
    
    # 7. Anti-Spam & State Machine
    "state_machine": {
        "weakening_confidence_threshold": 58.0,
        "score_refresh_delta": 8.0,
        "cooldown_periods": {
            "TRENDING_UP": 3,
            "TRENDING_DOWN": 3,
            "RANGE": 5,
            "HIGH_VOLATILITY": 8,
        },
    },
    
    # 8. QQQ Macro Tactical Rotation
    "qqq_macro": {
        "spy_sma_period": 200,
        "tqqq_rsi_period": 10,
        "tqqq_rsi_overbought": 79.0,
        "tqqq_rsi_oversold": 31.0,
        "spy_rsi_oversold": 30.0,
        "tqqq_sma_fast": 20,
        "sqqq_ief_roc_period": 20,
        "confirmation_days": 2,
        "hysteresis_pct": 0.5,
        "bear_depth_base_sqqq": 35.0,
        "bear_depth_slope": 8.0,
    }
}
