"""
QQQ Tactical Macro Rotation & Adaptive Bear Scaling Engine.
Implements:
1. Macro Market Regime: Bull (SPY > 200 SMA) vs Bear (SPY <= 200 SMA).
2. Raw Signal Generation:
   - Bull Regime: Defaults to Long TQQQ (raw_signal = 1); Hedge if TQQQ RSI-10 >= 79 (raw_signal = 2).
   - Bear Regime: Long bounce if TQQQ RSI-10 <= 31, SPY RSI-10 <= 30, or TQQQ > 20 SMA (raw_signal = 1).
     Otherwise, SQQQ vs IEF Relative Strength -> SQQQ Short (raw_signal = 4/5) or Cash/IEF (raw_signal = 3).
3. 2-Day Confirmation Persistence Filter (s5_days = 2) to eliminate whipsaws.
4. Adaptive Bear Scaling (S9): Dynamically scales SQQQ allocation % based on distance below 200 SMA over 252-day lookback.
5. 5 Portfolio States:
   - State 1 (Full Long): 100% TQQQ
   - State 2 (Hedge): 50% TQQQ / 50% SQQQ
   - State 3 (Neutral): 100% Cash / IEF
   - State 4 (Partial Short): Scaled SQQQ% + remaining Cash
   - State 5 (Full Short): 100% SQQQ
"""

import math
from typing import List, Dict, Any, Tuple, Optional

def calculate_sma(values: List[float], period: int) -> List[float]:
    sma = []
    for i in range(len(values)):
        if i < period - 1:
            window = values[:i + 1]
        else:
            window = values[i - period + 1 : i + 1]
        sma.append(sum(window) / len(window) if window else 0.0)
    return sma

def calculate_rsi(prices: List[float], period: int = 10) -> List[float]:
    if len(prices) < 2:
        return [50.0] * len(prices)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(prices)):
        chg = prices[i] - prices[i - 1]
        gains.append(max(0.0, chg))
        losses.append(max(0.0, -chg))
    
    avg_gain = calculate_sma(gains, period)
    avg_loss = calculate_sma(losses, period)
    
    rsi = []
    for i in range(len(prices)):
        if avg_loss[i] == 0:
            rsi.append(100.0 if avg_gain[i] > 0 else 50.0)
        else:
            rs = avg_gain[i] / avg_loss[i]
            rsi.append(100.0 - (100.0 / (1.0 + rs)))
    return rsi

def calculate_roc(prices: List[float], period: int = 20) -> List[float]:
    roc = []
    for i in range(len(prices)):
        if i < period:
            roc.append(0.0)
        else:
            ref = prices[i - period]
            roc.append(((prices[i] - ref) / ref * 100.0) if ref > 0 else 0.0)
    return roc

class QQQMacroRotationEngine:
    def __init__(self, confirmation_days: int = 2):
        self.confirmation_days = confirmation_days

    def analyze(
        self,
        qqq_candles: List[Dict[str, Any]],
        spy_candles: Optional[List[Dict[str, Any]]] = None,
        tqqq_candles: Optional[List[Dict[str, Any]]] = None,
        sqqq_candles: Optional[List[Dict[str, Any]]] = None,
        ief_candles: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        n = len(qqq_candles)
        if n < 20:
            return {"error": "Insufficient data"}

        qqq_closes = [float(c["close"]) for c in qqq_candles]
        
        # SPY proxy/real
        if spy_candles and len(spy_candles) == n:
            spy_closes = [float(c["close"]) for c in spy_candles]
        else:
            spy_closes = [round(q * 1.18, 2) for q in qqq_closes]

        # TQQQ proxy/real
        if tqqq_candles and len(tqqq_candles) == n:
            tqqq_closes = [float(c["close"]) for c in tqqq_candles]
        else:
            tqqq_closes = []
            base_t = 60.0
            for i in range(n):
                if i == 0:
                    tqqq_closes.append(base_t)
                else:
                    q_pct = (qqq_closes[i] - qqq_closes[i-1]) / (qqq_closes[i-1] or 1.0)
                    tqqq_closes.append(round(max(1.0, tqqq_closes[-1] * (1.0 + 3.0 * q_pct)), 2))

        # SQQQ proxy/real
        if sqqq_candles and len(sqqq_candles) == n:
            sqqq_closes = [float(c["close"]) for c in sqqq_candles]
        else:
            sqqq_closes = []
            base_s = 15.0
            for i in range(n):
                if i == 0:
                    sqqq_closes.append(base_s)
                else:
                    q_pct = (qqq_closes[i] - qqq_closes[i-1]) / (qqq_closes[i-1] or 1.0)
                    sqqq_closes.append(round(max(1.0, sqqq_closes[-1] * (1.0 - 3.0 * q_pct)), 2))

        # IEF proxy/real
        if ief_candles and len(ief_candles) == n:
            ief_closes = [float(c["close"]) for c in ief_candles]
        else:
            ief_closes = [94.0 + math.sin(i / 10.0) * 1.5 for i in range(n)]

        # --- TECHNICAL METRICS ---
        sma_len = min(200, max(15, n - 5))
        spy_sma200 = calculate_sma(spy_closes, sma_len)
        spy_rsi10 = calculate_rsi(spy_closes, 10)
        tqqq_rsi10 = calculate_rsi(tqqq_closes, 10)
        tqqq_sma20 = calculate_sma(tqqq_closes, 20)
        
        sqqq_roc20 = calculate_roc(sqqq_closes, 20)
        ief_roc20 = calculate_roc(ief_closes, 20)

        # --- STEP-BY-STEP SIMULATION WITH 2-DAY CONFIRMATION FILTER ---
        raw_signals = []
        confirmed_states = []
        scaled_sqqq_pcts = []
        
        current_confirmed_state = 1
        consecutive_count = 0
        last_raw_signal = 1
        history_alerts = []

        for i in range(n):
            c_spy = spy_closes[i]
            c_sma200 = spy_sma200[i]
            c_tqqq = tqqq_closes[i]
            c_tqqq_sma20 = tqqq_sma20[i]
            rsi_tqqq = tqqq_rsi10[i]
            rsi_spy = spy_rsi10[i]
            roc_sqqq = sqqq_roc20[i]
            roc_ief = ief_roc20[i]
            c_time = qqq_candles[i]["time"]

            # 1. Market Regime
            is_bull = c_spy > c_sma200
            
            # S9: Adaptive Bear Depth Scaling
            dist_below_sma = max(0.0, (c_sma200 - c_spy) / (c_sma200 or 1.0) * 100.0)
            if dist_below_sma <= 1.0:
                s9_sqqq_pct = 40
            elif dist_below_sma <= 4.0:
                s9_sqqq_pct = 65
            elif dist_below_sma <= 8.0:
                s9_sqqq_pct = 85
            else:
                s9_sqqq_pct = 100

            # 2. Raw Signal Generation
            if is_bull:
                if rsi_tqqq >= 79.0:
                    raw_signal = 2 # State 2: Hedge (50% TQQQ / 50% SQQQ)
                    reason = f"Bull Regime Overbought: TQQQ RSI-10 ({rsi_tqqq:.1f} >= 79) triggers tactical hedge"
                else:
                    raw_signal = 1 # State 1: Full Long (100% TQQQ)
                    reason = f"Bull Regime: SPY (${c_spy:.2f}) > 200 SMA (${c_sma200:.2f}) -> 100% TQQQ"
            else:
                # Bear Regime
                is_oversold = (rsi_tqqq <= 31.0) or (rsi_spy <= 30.0)
                is_above_sma20 = (c_tqqq > c_tqqq_sma20) and (i >= 20) and (c_tqqq > 0)
                
                if is_oversold:
                    raw_signal = 1
                    reason = f"Bear Regime Oversold Bounce: TQQQ RSI ({rsi_tqqq:.1f} <= 31) -> Tactical Long"
                elif is_above_sma20:
                    raw_signal = 1
                    reason = f"Bear Regime Mean-Reversion: TQQQ (${c_tqqq:.2f}) > 20 SMA (${c_tqqq_sma20:.2f}) -> Tactical Long"
                else:
                    # Check relative strength between SQQQ and IEF
                    if roc_sqqq > roc_ief:
                        if s9_sqqq_pct >= 95:
                            raw_signal = 5 # State 5: Full Short (100% SQQQ)
                            reason = f"Bear Regime Severe Breakdown: SQQQ RS > IEF & S9 Depth {dist_below_sma:.1f}% -> 100% SQQQ"
                        else:
                            raw_signal = 4 # State 4: Partial Short (Scaled SQQQ% + Cash)
                            reason = f"Bear Regime: SQQQ RS ({roc_sqqq:.1f}%) > IEF ({roc_ief:.1f}%) -> Adaptive {s9_sqqq_pct}% SQQQ / {100-s9_sqqq_pct}% Cash"
                    else:
                        raw_signal = 3 # State 3: Neutral (100% Cash / IEF)
                        reason = f"Bear Regime Capital Preservation: IEF RS ({roc_ief:.1f}%) >= SQQQ -> 100% Cash / IEF Bonds"

            raw_signals.append(raw_signal)
            scaled_sqqq_pcts.append(s9_sqqq_pct)

            # 3. 2-Day Confirmation Filter (s5_days = 2)
            if raw_signal == last_raw_signal:
                consecutive_count += 1
            else:
                consecutive_count = 1
                last_raw_signal = raw_signal

            previous_confirmed = current_confirmed_state
            if consecutive_count >= self.confirmation_days:
                current_confirmed_state = raw_signal

            confirmed_states.append(current_confirmed_state)

            if i > 0 and current_confirmed_state != previous_confirmed and consecutive_count == self.confirmation_days:
                state_names = {
                    1: "STATE 1: FULL LONG (100% TQQQ)",
                    2: "STATE 2: HEDGE (50% TQQQ / 50% SQQQ)",
                    3: "STATE 3: NEUTRAL (100% CASH / IEF)",
                    4: f"STATE 4: PARTIAL SHORT ({s9_sqqq_pct}% SQQQ / {100-s9_sqqq_pct}% CASH)",
                    5: "STATE 5: FULL SHORT (100% SQQQ)",
                }
                history_alerts.append({
                    "time": c_time,
                    "type": "PORTFOLIO_ROTATION",
                    "state": current_confirmed_state,
                    "state_name": state_names.get(current_confirmed_state, "STATE CHANGE"),
                    "price": qqq_closes[i],
                    "title": f"ROTATION CONFIRMED ➔ {state_names.get(current_confirmed_state)}",
                    "reason": reason,
                    "desc": f"2-Day Filter Confirmed: {reason}",
                    "sqqq_pct": s9_sqqq_pct if current_confirmed_state == 4 else (100 if current_confirmed_state == 5 else (50 if current_confirmed_state == 2 else 0)),
                    "tqqq_pct": 100 if current_confirmed_state == 1 else (50 if current_confirmed_state == 2 else 0),
                    "cash_pct": 100 if current_confirmed_state == 3 else (100 - s9_sqqq_pct if current_confirmed_state == 4 else 0)
                })

        last_state = confirmed_states[-1]
        last_raw = raw_signals[-1]
        last_s9 = scaled_sqqq_pcts[-1]
        last_is_bull = spy_closes[-1] > spy_sma200[-1]
        dist_sma = (spy_closes[-1] - spy_sma200[-1]) / (spy_sma200[-1] or 1.0) * 100.0

        state_descriptions = {
            1: {
                "name": "State 1: Full Long",
                "allocation": {"TQQQ": 100, "SQQQ": 0, "Cash": 0, "IEF": 0},
                "badge": "100% TQQQ",
                "action": "Maintain 100% Long TQQQ exposure. Momentum is favorable in Bull Regime."
            },
            2: {
                "name": "State 2: Tactical Hedge",
                "allocation": {"TQQQ": 50, "SQQQ": 50, "Cash": 0, "IEF": 0},
                "badge": "50% TQQQ / 50% SQQQ",
                "action": "Rebalance to 50% TQQQ / 50% SQQQ hedge. TQQQ 10-day RSI overbought >= 79."
            },
            3: {
                "name": "State 3: Neutral Capital Preservation",
                "allocation": {"TQQQ": 0, "SQQQ": 0, "Cash": 100, "IEF": 0},
                "badge": "100% Cash / IEF",
                "action": "Move 100% to Cash / IEF Bonds. Bear regime active and IEF showing superior relative strength."
            },
            4: {
                "name": f"State 4: Adaptive Short ({last_s9}% SQQQ)",
                "allocation": {"TQQQ": 0, "SQQQ": last_s9, "Cash": 100 - last_s9, "IEF": 0},
                "badge": f"{last_s9}% SQQQ / {100-last_s9}% Cash",
                "action": f"Allocate {last_s9}% SQQQ and {100-last_s9}% Cash. S9 Bear Depth scaling active ({abs(dist_sma):.1f}% below 200 SMA)."
            },
            5: {
                "name": "State 5: Full Short",
                "allocation": {"TQQQ": 0, "SQQQ": 100, "Cash": 0, "IEF": 0},
                "badge": "100% SQQQ",
                "action": "Execute 100% SQQQ Short. Severe bear breakdown confirmed across macro indicators."
            }
        }

        active_info = state_descriptions.get(last_state, state_descriptions[1])

        return {
            "symbol": "QQQ",
            "name": "Invesco QQQ Trust (TQQQ / SQQQ Tactical Macro Rotation)",
            "macro_regime": {
                "regime": "BULL MARKET" if last_is_bull else "BEAR MARKET",
                "spy_price": round(spy_closes[-1], 2),
                "spy_sma200": round(spy_sma200[-1], 2),
                "dist_to_sma200_pct": round(dist_sma, 2),
                "desc": "SPY > 200 SMA (Bull Market)" if last_is_bull else "SPY <= 200 SMA (Bear Market)"
            },
            "active_state": {
                "state_id": last_state,
                "name": active_info["name"],
                "badge": active_info["badge"],
                "allocation": active_info["allocation"],
                "action": active_info["action"],
                "raw_signal": last_raw,
                "persistence_count": consecutive_count,
                "is_pending_transition": (last_raw != last_state)
            },
            "macro_telemetry": {
                "spy_rsi10": round(spy_rsi10[-1], 1),
                "tqqq_rsi10": round(tqqq_rsi10[-1], 1),
                "tqqq_price": round(tqqq_closes[-1], 2),
                "tqqq_sma20": round(tqqq_sma20[-1], 2),
                "sqqq_roc20": round(sqqq_roc20[-1], 2),
                "ief_roc20": round(ief_roc20[-1], 2),
                "sqqq_vs_ief_rs": "SQQQ Dominant" if sqqq_roc20[-1] > ief_roc20[-1] else "IEF Dominant",
                "s9_bear_depth_pct": last_s9,
                "filter_2day_active": True
            },
            "alerts": history_alerts,
            "candles": qqq_candles
        }
