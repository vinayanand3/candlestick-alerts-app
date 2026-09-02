"""
Alert Filter — Deduplication & Anti-Spam Manager.
Creates unique setup identities (Symbol:Timeframe:Direction:Setup:Level) and suppresses redundant consecutive alerts.
"""

from typing import Dict, Any, List, Optional

class AlertDeduplicator:
    def __init__(self, score_refresh_delta: float = 8.0):
        self.score_refresh_delta = score_refresh_delta
        self.active_setup_identities: Dict[str, Dict[str, Any]] = {}

    def get_setup_identity(self, symbol: str, timeframe: str, direction: str, setup_id: str, key_level: float) -> str:
        return f"{symbol}:{timeframe}:{direction}:{setup_id}:{round(key_level, 1)}"

    def should_emit_alert(
        self,
        symbol: str,
        timeframe: str,
        event: Dict[str, Any]
    ) -> bool:
        evt_type = event.get("type")

        # Exits and Target Hits always emit
        if evt_type in ["SIGNAL_EXIT", "TARGET_1_HIT", "TARGET_2_HIT", "SIGNAL_WEAKENING", "PORTFOLIO_ROTATION"]:
            return True

        if evt_type == "SIGNAL_CONFIRMED":
            dirn = event.get("direction", "CALL")
            setup_id = event.get("setup_id", "SETUP")
            stop_loss = event.get("stop_loss", 0.0)
            score = event.get("signal_score", 75.0)

            identity = self.get_setup_identity(symbol, timeframe, dirn, setup_id, stop_loss)

            if identity in self.active_setup_identities:
                prev_record = self.active_setup_identities[identity]
                # Check if score improved by at least delta
                if score >= prev_record["score"] + self.score_refresh_delta:
                    self.active_setup_identities[identity]["score"] = score
                    return True # Significant score improvement
                return False # Duplicate active setup, suppress alert

            # New identity
            self.active_setup_identities[identity] = {
                "score": score,
                "time": event.get("time")
            }
            return True

        return True
