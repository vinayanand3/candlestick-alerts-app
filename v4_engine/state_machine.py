"""
State Machine — 8-State Signal Lifecycle & Ratcheting Chandelier Exit Manager.
Lifecycle: IDLE -> WATCH -> TRIGGERED -> CONFIRMED -> ACTIVE -> WEAKENING -> INVALIDATED / EXIT -> COOLDOWN.
"""

from typing import Dict, Any, List, Optional, Tuple

class SignalStateMachine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.active_signal: Optional[Dict[str, Any]] = None
        self.cooldown_counter: int = 0
        self.cooldown_limit: int = 4
        self.alert_history: List[Dict[str, Any]] = []

    def process_candle(
        self,
        candle: Dict[str, Any],
        scoring_data: Dict[str, Any],
        risk_data: Optional[Dict[str, Any]],
        regime_data: Dict[str, Any],
        atr_val: float
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        c_time = candle["time"]
        c_close = float(candle["close"])
        c_high = float(candle["high"])
        c_low = float(candle["low"])

        new_events = []
        direction = scoring_data.get("direction", "NEUTRAL")
        score = scoring_data.get("signal_score", 0.0)
        setup_id = scoring_data.get("setup_id", "NO_SETUP")

        # 1. Cooldown Handling
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            if self.cooldown_counter == 0 and not self.active_signal:
                pass # Cooldown expired

        # 2. No Active Signal State
        if self.active_signal is None:
            if self.cooldown_counter > 0:
                return None, []

            min_trigger = self.config.get("scoring", {}).get("min_call_score" if direction == "CALL" else "min_put_score", 68.0)
            if direction in ["CALL", "PUT"] and score >= min_trigger and risk_data and risk_data.get("risk_passed"):
                # Transition: TRIGGERED -> CONFIRMED -> ACTIVE
                entry_p = risk_data["entry_price"]
                stop_p = risk_data["stop_loss"]

                self.active_signal = {
                    "id": f"{direction}:{setup_id}:{c_time}",
                    "setup_id": setup_id,
                    "direction": direction,
                    "state": "ACTIVE",
                    "entry_time": c_time,
                    "entry_price": entry_p,
                    "current_price": c_close,
                    "signal_score": score,
                    "initial_stop": stop_p,
                    "trailing_stop": stop_p,
                    "highest_high": c_high,
                    "lowest_low": c_low,
                    "target_1": risk_data["target_1"],
                    "target_2": risk_data["target_2"],
                    "target_3": risk_data["target_3"],
                    "t1_hit": False,
                    "t2_hit": False,
                    "rr_t2": risk_data["rr_t2"],
                    "expected_value": risk_data["expected_value_r"],
                    "invalidation_level": stop_p,
                    "reasons": scoring_data.get("applied_caps", [])
                }

                evt = {
                    "type": "SIGNAL_CONFIRMED",
                    "time": c_time,
                    "direction": direction,
                    "setup_id": setup_id,
                    "state": "CONFIRMED",
                    "price": entry_p,
                    "signal_score": score,
                    "title": f"NEW {direction} SIGNAL CONFIRMED ({setup_id})",
                    "entry_zone": risk_data["entry_zone"],
                    "stop_loss": stop_p,
                    "trailing_stop": stop_p,
                    "target_1": risk_data["target_1"],
                    "target_2": risk_data["target_2"],
                    "rr_ratio": risk_data["rr_t2"],
                    "desc": f"High-confidence {direction} setup confirmed. Minimum Risk-to-Reward {risk_data['rr_t2']}:1."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

            return self.active_signal, new_events

        # 3. Active Signal In-Trade Monitoring
        sig = self.active_signal
        sig_dir = sig["direction"]
        entry_p = sig["entry_price"]
        sig["current_price"] = c_close

        if sig_dir == "CALL":
            start_bar_stop = sig["trailing_stop"]

            # Target 1 Hit
            if not sig["t1_hit"] and c_high >= sig["target_1"]:
                sig["t1_hit"] = True
                sig["trailing_stop"] = max(sig["trailing_stop"], entry_p) # Lock Breakeven
                evt = {
                    "type": "TARGET_1_HIT",
                    "time": c_time,
                    "direction": "CALL",
                    "state": "ACTIVE",
                    "price": c_close,
                    "title": "🎯 TARGET 1 HIT (50% Scaled Out)",
                    "desc": f"Price hit Target 1 (${sig['target_1']:.2f}). Stop moved to Breakeven (${entry_p:.2f})."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

            # Target 2 Hit
            if not sig["t2_hit"] and c_high >= sig["target_2"]:
                sig["t2_hit"] = True
                sig["trailing_stop"] = max(sig["trailing_stop"], sig["target_1"]) # Lock Target 1 floor
                evt = {
                    "type": "TARGET_2_HIT",
                    "time": c_time,
                    "direction": "CALL",
                    "state": "ACTIVE",
                    "price": c_close,
                    "title": "🎯 TARGET 2 HIT (30% Scaled Out)",
                    "desc": f"Price hit Target 2 (${sig['target_2']:.2f}). Trailing stop ratcheted to Target 1 (${sig['target_1']:.2f})."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

            # Ratchet highest high and trailing stop (never moves backwards)
            if c_high > sig["highest_high"]:
                sig["highest_high"] = c_high
                calc_trail = round(c_high - (1.5 * atr_val), 2)
                sig["trailing_stop"] = max(sig["trailing_stop"], calc_trail)

            # Structural Invalidation & Stop Exits
            is_stop_breached = c_low <= start_bar_stop
            is_structurally_invalidated = c_close < sig["invalidation_level"]

            if is_stop_breached or is_structurally_invalidated:
                exit_reason = "Trailing Stop Triggered" if sig["t1_hit"] else "Stop Loss Hit"
                if is_structurally_invalidated and not is_stop_breached:
                    exit_reason = "Structural Invalidation Override"

                evt = {
                    "type": "SIGNAL_EXIT",
                    "time": c_time,
                    "direction": "CALL",
                    "state": "EXIT",
                    "price": c_close,
                    "title": f"CALL EXIT ({exit_reason})",
                    "desc": f"CALL position exited at ${c_close:.2f}. Reason: {exit_reason}."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

                # Set Cooldown
                regime_name = regime_data.get("regime", "RANGE")
                self.cooldown_limit = self.config.get("state_machine", {}).get("cooldown_periods", {}).get(regime_name, 4)
                self.cooldown_counter = self.cooldown_limit
                self.active_signal = None
                return None, new_events

            # Weakening Check
            elif score < 58.0 and sig["state"] != "WEAKENING":
                sig["state"] = "WEAKENING"
                evt = {
                    "type": "SIGNAL_WEAKENING",
                    "time": c_time,
                    "direction": "CALL",
                    "state": "WEAKENING",
                    "price": c_close,
                    "title": "CALL SIGNAL WEAKENING (Momentum Decay)",
                    "desc": f"Signal score softened to {score:.0f}/100. Trailing stop protecting profit."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

        else: # PUT Signal
            start_bar_stop = sig["trailing_stop"]

            # Target 1 Hit
            if not sig["t1_hit"] and c_low <= sig["target_1"]:
                sig["t1_hit"] = True
                sig["trailing_stop"] = min(sig["trailing_stop"], entry_p) # Lock Breakeven
                evt = {
                    "type": "TARGET_1_HIT",
                    "time": c_time,
                    "direction": "PUT",
                    "state": "ACTIVE",
                    "price": c_close,
                    "title": "🎯 TARGET 1 HIT (50% Scaled Out)",
                    "desc": f"Price hit PUT Target 1 (${sig['target_1']:.2f}). Stop moved to Breakeven (${entry_p:.2f})."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

            # Target 2 Hit
            if not sig["t2_hit"] and c_low <= sig["target_2"]:
                sig["t2_hit"] = True
                sig["trailing_stop"] = min(sig["trailing_stop"], sig["target_1"]) # Lock Target 1 ceiling
                evt = {
                    "type": "TARGET_2_HIT",
                    "time": c_time,
                    "direction": "PUT",
                    "state": "ACTIVE",
                    "price": c_close,
                    "title": "🎯 TARGET 2 HIT (30% Scaled Out)",
                    "desc": f"Price hit PUT Target 2 (${sig['target_2']:.2f}). Trailing stop ratcheted to Target 1 (${sig['target_1']:.2f})."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

            if c_low < sig["lowest_low"]:
                sig["lowest_low"] = c_low
                calc_trail = round(c_low + (1.5 * atr_val), 2)
                sig["trailing_stop"] = min(sig["trailing_stop"], calc_trail)

            is_stop_breached = c_high >= start_bar_stop
            is_structurally_invalidated = c_close > sig["invalidation_level"]

            if is_stop_breached or is_structurally_invalidated:
                exit_reason = "Trailing Stop Triggered" if sig["t1_hit"] else "Stop Loss Hit"
                if is_structurally_invalidated and not is_stop_breached:
                    exit_reason = "Structural Invalidation Override"

                evt = {
                    "type": "SIGNAL_EXIT",
                    "time": c_time,
                    "direction": "PUT",
                    "state": "EXIT",
                    "price": c_close,
                    "title": f"PUT EXIT ({exit_reason})",
                    "desc": f"PUT position exited at ${c_close:.2f}. Reason: {exit_reason}."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

                regime_name = regime_data.get("regime", "RANGE")
                self.cooldown_limit = self.config.get("state_machine", {}).get("cooldown_periods", {}).get(regime_name, 4)
                self.cooldown_counter = self.cooldown_limit
                self.active_signal = None
                return None, new_events

            elif score < 58.0 and sig["state"] != "WEAKENING":
                sig["state"] = "WEAKENING"
                evt = {
                    "type": "SIGNAL_WEAKENING",
                    "time": c_time,
                    "direction": "PUT",
                    "state": "WEAKENING",
                    "price": c_close,
                    "title": "PUT SIGNAL WEAKENING (Momentum Decay)",
                    "desc": f"Signal score softened to {score:.0f}/100. Trailing stop protecting profit."
                }
                new_events.append(evt)
                self.alert_history.append(evt)

        return self.active_signal, new_events
