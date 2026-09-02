"""
Candlestick Pattern Recognition Engine with Multi-Factor Confidence Scoring.
Filters patterns to emit alerts only when confidence is strictly >= 75%.
"""

import math
from typing import List, Dict, Any, Optional

def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average."""
    if not prices:
        return []
    if len(prices) < period:
        sma = sum(prices) / len(prices)
        return [sma] * len(prices)
    ema = []
    multiplier = 2 / (period + 1)
    sma = sum(prices[:period]) / period
    for _ in range(period - 1):
        ema.append(sma)
    ema.append(sma)
    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema

def calculate_sma(values: List[float], period: int) -> List[float]:
    """Calculate Simple Moving Average."""
    sma = []
    for i in range(len(values)):
        if i < period - 1:
            window = values[:i + 1]
        else:
            window = values[i - period + 1 : i + 1]
        sma.append(sum(window) / len(window) if window else 0.0)
    return sma

def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> List[float]:
    """Calculate Average True Range (ATR)."""
    tr_list = []
    for i in range(len(candles)):
        c = candles[i]
        high = float(c["high"])
        low = float(c["low"])
        if i == 0:
            tr = high - low
        else:
            prev_close = float(candles[i - 1]["close"])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return calculate_sma(tr_list, period)


class CandlestickDetector:
    def __init__(self, min_confidence: float = 75.0):
        self.min_confidence = min_confidence

    def analyze_candles(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Scans candle series and identifies candlestick patterns with confidence >= threshold.
        Returns a list of high-confidence alert objects.
        """
        if len(candles) < 3:
            return []

        closes = [float(c["close"]) for c in candles]
        opens = [float(c["open"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        volumes = [float(c.get("volume", 1.0)) for c in candles]
        
        # Technical indicators
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        vol_sma20 = calculate_sma(volumes, 20)
        atr14 = calculate_atr(candles, 14)

        alerts = []

        for i in range(1, len(candles)):
            c0 = candles[i]     # Current candle
            c1 = candles[i - 1] # 1 candle ago
            c2 = candles[i - 2] if i >= 2 else c1 # 2 candles ago

            curr_vol = volumes[i]
            avg_vol = vol_sma20[i] if vol_sma20[i] > 0 else 1.0
            vol_ratio = curr_vol / avg_vol
            curr_atr = atr14[i] if atr14[i] > 0 else (highs[i] - lows[i] or 1.0)

            # Trend calculation with safety check
            ref_idx = max(0, i - 4)
            prior_change = (closes[i - 1] - closes[ref_idx])
            pct_change = prior_change / (closes[ref_idx] or 1.0) * 100.0

            downtrend_context = (pct_change < -0.4) or (i >= 3 and closes[i - 1] < closes[i - 2] < closes[i - 3])
            uptrend_context = (pct_change > 0.4) or (i >= 3 and closes[i - 1] > closes[i - 2] > closes[i - 3])

            patterns_found = []

            # 1. Bullish Engulfing
            p_bull_eng = self._check_bullish_engulfing(c1, c0, downtrend_context, vol_ratio, curr_atr)
            if p_bull_eng:
                patterns_found.append(p_bull_eng)

            # 2. Bearish Engulfing
            p_bear_eng = self._check_bearish_engulfing(c1, c0, uptrend_context, vol_ratio, curr_atr)
            if p_bear_eng:
                patterns_found.append(p_bear_eng)

            # 3. Hammer (Bullish Reversal)
            p_hammer = self._check_hammer(c0, downtrend_context, vol_ratio, curr_atr)
            if p_hammer:
                patterns_found.append(p_hammer)

            # 4. Shooting Star (Bearish Reversal)
            p_star = self._check_shooting_star(c0, uptrend_context, vol_ratio, curr_atr)
            if p_star:
                patterns_found.append(p_star)

            # 3-Candle Patterns (Require i >= 2)
            if i >= 2:
                # 5. Morning Star
                p_morning_star = self._check_morning_star(c2, c1, c0, downtrend_context, vol_ratio, curr_atr)
                if p_morning_star:
                    patterns_found.append(p_morning_star)

                # 6. Evening Star
                p_evening_star = self._check_evening_star(c2, c1, c0, uptrend_context, vol_ratio, curr_atr)
                if p_evening_star:
                    patterns_found.append(p_evening_star)

                # 7. Three White Soldiers
                p_white_soldiers = self._check_three_white_soldiers(c2, c1, c0, vol_ratio, curr_atr)
                if p_white_soldiers:
                    patterns_found.append(p_white_soldiers)

                # 8. Three Black Crows
                p_black_crows = self._check_three_black_crows(c2, c1, c0, vol_ratio, curr_atr)
                if p_black_crows:
                    patterns_found.append(p_black_crows)

            # 9. Piercing Line
            p_piercing = self._check_piercing_line(c1, c0, downtrend_context, vol_ratio, curr_atr)
            if p_piercing:
                patterns_found.append(p_piercing)

            # 10. Dark Cloud Cover
            p_dark_cloud = self._check_dark_cloud(c1, c0, uptrend_context, vol_ratio, curr_atr)
            if p_dark_cloud:
                patterns_found.append(p_dark_cloud)

            # 11. Dragonfly / Gravestone Doji
            p_doji = self._check_doji(c0, downtrend_context, uptrend_context, vol_ratio, curr_atr)
            if p_doji:
                patterns_found.append(p_doji)

            # Filter for confidence strictly >= min_confidence
            for pat in patterns_found:
                if pat["confidence"] >= self.min_confidence:
                    alert = {
                        "index": i,
                        "time": c0["time"],
                        "price": float(c0["close"]),
                        "pattern": pat["name"],
                        "direction": pat["direction"],
                        "confidence": round(pat["confidence"], 1),
                        "reasons": pat["reasons"],
                        "description": pat["description"]
                    }
                    alerts.append(alert)

        return alerts

    def _candle_props(self, c: Dict[str, Any]):
        o = float(c["open"])
        h = float(c["high"])
        l = float(c["low"])
        cl = float(c["close"])
        body = abs(cl - o)
        total_range = h - l if (h - l) > 0 else 0.00001
        upper_wick = h - max(o, cl)
        lower_wick = min(o, cl) - l
        is_bullish = cl >= o
        return o, h, l, cl, body, total_range, upper_wick, lower_wick, is_bullish

    # --- PATTERN CHECKERS ---

    def _check_bullish_engulfing(self, c1, c0, downtrend, vol_ratio, atr):
        o1, h1, l1, cl1, body1, range1, u1, l1_w, bull1 = self._candle_props(c1)
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        if bull1 or not bull0:
            return None

        if o0 <= cl1 and cl0 > o1 and body0 > body1 * 1.05:
            score = 36.0
            reasons = ["Green body fully engulfs previous red candle body"]

            if h0 >= h1 and l0 <= l1:
                score += 8.0
                reasons.append("Complete high/low range engulfment")

            if downtrend:
                score += 24.0
                reasons.append("Formed at bottom of clear downtrend (High Reversal Prob)")
            else:
                score += 5.0

            if vol_ratio >= 1.5:
                score += 18.0
                reasons.append(f"Strong volume expansion ({vol_ratio:.1f}x 20MA)")
            elif vol_ratio >= 1.2:
                score += 10.0
                reasons.append("Above average volume")

            if range0 >= 0.85 * atr:
                score += 10.0
                reasons.append("Candle range significant vs ATR")

            return {
                "name": "Bullish Engulfing",
                "direction": "Bullish",
                "confidence": min(98.0, score),
                "reasons": reasons,
                "description": "Strong bullish reversal pattern where a large green candle completely engulfs the prior red candle."
            }
        return None

    def _check_bearish_engulfing(self, c1, c0, uptrend, vol_ratio, atr):
        o1, h1, l1, cl1, body1, range1, u1, l1_w, bull1 = self._candle_props(c1)
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        if not bull1 or bull0:
            return None

        if o0 >= cl1 and cl0 < o1 and body0 > body1 * 1.05:
            score = 36.0
            reasons = ["Red body fully engulfs previous green candle body"]

            if h0 >= h1 and l0 <= l1:
                score += 8.0
                reasons.append("Complete high/low range engulfment")

            if uptrend:
                score += 24.0
                reasons.append("Formed at peak of clear uptrend (High Reversal Prob)")
            else:
                score += 5.0

            if vol_ratio >= 1.5:
                score += 18.0
                reasons.append(f"Strong volume expansion ({vol_ratio:.1f}x 20MA)")
            elif vol_ratio >= 1.2:
                score += 10.0
                reasons.append("Above average volume")

            if range0 >= 0.85 * atr:
                score += 10.0
                reasons.append("Candle range significant vs ATR")

            return {
                "name": "Bearish Engulfing",
                "direction": "Bearish",
                "confidence": min(98.0, score),
                "reasons": reasons,
                "description": "Strong bearish reversal pattern where a large red candle completely engulfs the prior green candle."
            }
        return None

    def _check_hammer(self, c0, downtrend, vol_ratio, atr):
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        if l0_w >= 2.0 * body0 and u0 <= 0.2 * range0 and body0 > 0.05 * range0:
            score = 34.0
            reasons = ["Long lower shadow with small body at upper extreme (Rejection of lows)"]

            if l0_w >= 3.0 * body0:
                score += 8.0
                reasons.append("Extra-long lower wick (>3x body)")

            if bull0:
                score += 6.0
                reasons.append("Bullish green close")

            if downtrend:
                score += 24.0
                reasons.append("Formed at bottom of clear downtrend")
            else:
                score += 4.0

            if vol_ratio >= 1.4:
                score += 18.0
                reasons.append(f"Heavy buying volume spike ({vol_ratio:.1f}x 20MA)")
            elif vol_ratio >= 1.15:
                score += 10.0
                reasons.append("Above average volume")

            if range0 >= 0.8 * atr:
                score += 8.0

            return {
                "name": "Hammer",
                "direction": "Bullish",
                "confidence": min(98.0, score),
                "reasons": reasons,
                "description": "Bullish reversal pattern indicating buyers strongly rejected lower prices and pushed back up."
            }
        return None

    def _check_shooting_star(self, c0, uptrend, vol_ratio, atr):
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        if u0 >= 2.0 * body0 and l0_w <= 0.2 * range0 and body0 > 0.05 * range0:
            score = 34.0
            reasons = ["Long upper shadow with body at lower extreme (Rejection of highs)"]

            if u0 >= 3.0 * body0:
                score += 8.0
                reasons.append("Extra-long upper wick (>3x body)")

            if not bull0:
                score += 6.0
                reasons.append("Bearish red close")

            if uptrend:
                score += 24.0
                reasons.append("Formed at peak of clear uptrend")
            else:
                score += 4.0

            if vol_ratio >= 1.4:
                score += 18.0
                reasons.append(f"Heavy selling volume spike ({vol_ratio:.1f}x 20MA)")
            elif vol_ratio >= 1.15:
                score += 10.0
                reasons.append("Above average volume")

            if range0 >= 0.8 * atr:
                score += 8.0

            return {
                "name": "Shooting Star",
                "direction": "Bearish",
                "confidence": min(98.0, score),
                "reasons": reasons,
                "description": "Bearish reversal pattern indicating sellers aggressively rejected higher price levels."
            }
        return None

    def _check_morning_star(self, c2, c1, c0, downtrend, vol_ratio, atr):
        o2, h2, l2, cl2, body2, range2, u2, l2_w, bull2 = self._candle_props(c2)
        o1, h1, l1, cl1, body1, range1, u1, l1_w, bull1 = self._candle_props(c1)
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        if not bull2 and bull0 and body1 < body2 * 0.45 and body0 > body2 * 0.5:
            midpoint2 = (o2 + cl2) / 2.0
            if cl0 > midpoint2:
                score = 38.0
                reasons = ["3-candle bullish reversal: Strong red -> Indecision star -> Strong green close >50%"]

                if cl0 > o2:
                    score += 8.0
                    reasons.append("Green candle completely eclipsed initial red open")

                if downtrend:
                    score += 24.0
                    reasons.append("Confirmed bottoming structure after downtrend")
                else:
                    score += 5.0

                if vol_ratio >= 1.3:
                    score += 18.0
                    reasons.append(f"Volume accumulation spike ({vol_ratio:.1f}x 20MA)")
                elif vol_ratio >= 1.1:
                    score += 8.0

                if range0 >= 0.8 * atr:
                    score += 8.0

                return {
                    "name": "Morning Star",
                    "direction": "Bullish",
                    "confidence": min(99.0, score),
                    "reasons": reasons,
                    "description": "Major 3-candlestick bullish bottom reversal signaling strong transition from bears to bulls."
                }
        return None

    def _check_evening_star(self, c2, c1, c0, uptrend, vol_ratio, atr):
        o2, h2, l2, cl2, body2, range2, u2, l2_w, bull2 = self._candle_props(c2)
        o1, h1, l1, cl1, body1, range1, u1, l1_w, bull1 = self._candle_props(c1)
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        if bull2 and not bull0 and body1 < body2 * 0.45 and body0 > body2 * 0.5:
            midpoint2 = (o2 + cl2) / 2.0
            if cl0 < midpoint2:
                score = 38.0
                reasons = ["3-candle bearish reversal: Strong green -> Indecision star -> Strong red close <50%"]

                if cl0 < o2:
                    score += 8.0
                    reasons.append("Red candle closed below initial green candle open")

                if uptrend:
                    score += 24.0
                    reasons.append("Confirmed top reversal structure after uptrend")
                else:
                    score += 5.0

                if vol_ratio >= 1.3:
                    score += 18.0
                    reasons.append(f"Volume selloff spike ({vol_ratio:.1f}x 20MA)")
                elif vol_ratio >= 1.1:
                    score += 8.0

                if range0 >= 0.8 * atr:
                    score += 8.0

                return {
                    "name": "Evening Star",
                    "direction": "Bearish",
                    "confidence": min(99.0, score),
                    "reasons": reasons,
                    "description": "Major 3-candlestick top reversal signaling sudden exhaustion of buyers and takeover by sellers."
                }
        return None

    def _check_three_white_soldiers(self, c2, c1, c0, vol_ratio, atr):
        o2, h2, l2, cl2, body2, range2, u2, l2_w, bull2 = self._candle_props(c2)
        o1, h1, l1, cl1, body1, range1, u1, l1_w, bull1 = self._candle_props(c1)
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        if bull2 and bull1 and bull0 and cl0 > cl1 > cl2 and o0 >= o1 and o1 >= o2:
            if u0 <= 0.25 * range0 and u1 <= 0.25 * range1 and u2 <= 0.25 * range2:
                score = 45.0
                reasons = ["Three consecutive strong green candles with high closes (White Soldiers)"]

                if vol_ratio >= 1.2:
                    score += 18.0
                    reasons.append("Consistent volume expansion")

                if body0 >= 0.6 * atr and body1 >= 0.6 * atr:
                    score += 16.0
                    reasons.append("Substantial body sizes above ATR")

                return {
                    "name": "Three White Soldiers",
                    "direction": "Bullish",
                    "confidence": min(98.0, score),
                    "reasons": reasons,
                    "description": "Powerful bullish continuation/reversal pattern showing relentless buyer domination over three periods."
                }
        return None

    def _check_three_black_crows(self, c2, c1, c0, vol_ratio, atr):
        o2, h2, l2, cl2, body2, range2, u2, l2_w, bull2 = self._candle_props(c2)
        o1, h1, l1, cl1, body1, range1, u1, l1_w, bull1 = self._candle_props(c1)
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        if not bull2 and not bull1 and not bull0 and cl0 < cl1 < cl2 and o0 <= o1 and o1 <= o2:
            if l0_w <= 0.25 * range0 and l1_w <= 0.25 * range1 and l2_w <= 0.25 * range2:
                score = 45.0
                reasons = ["Three consecutive heavy red candles with low closes (Black Crows)"]

                if vol_ratio >= 1.2:
                    score += 18.0
                    reasons.append("Consistent selling volume expansion")

                if body0 >= 0.6 * atr and body1 >= 0.6 * atr:
                    score += 16.0
                    reasons.append("Substantial body sizes above ATR")

                return {
                    "name": "Three Black Crows",
                    "direction": "Bearish",
                    "confidence": min(98.0, score),
                    "reasons": reasons,
                    "description": "Powerful bearish continuation/reversal pattern indicating heavy institutional liquidation."
                }
        return None

    def _check_piercing_line(self, c1, c0, downtrend, vol_ratio, atr):
        o1, h1, l1, cl1, body1, range1, u1, l1_w, bull1 = self._candle_props(c1)
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        midpoint1 = (o1 + cl1) / 2.0
        if not bull1 and bull0 and o0 <= l1 and cl0 > midpoint1 and cl0 <= o1:
            score = 36.0
            reasons = ["Green candle opened below prior low and pierced >50% into red body"]

            if downtrend:
                score += 24.0
                reasons.append("Preceded by downtrend momentum")
            else:
                score += 5.0

            if vol_ratio >= 1.3:
                score += 18.0
                reasons.append(f"Volume spike ({vol_ratio:.1f}x 20MA)")
            elif vol_ratio >= 1.1:
                score += 8.0

            if range0 >= 0.8 * atr:
                score += 10.0

            return {
                "name": "Piercing Line",
                "direction": "Bullish",
                "confidence": min(96.0, score),
                "reasons": reasons,
                "description": "Bullish 2-candle reversal where buyers violently reject a lower open and push deep into prior seller territory."
            }
        return None

    def _check_dark_cloud(self, c1, c0, uptrend, vol_ratio, atr):
        o1, h1, l1, cl1, body1, range1, u1, l1_w, bull1 = self._candle_props(c1)
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        midpoint1 = (o1 + cl1) / 2.0
        if bull1 and not bull0 and o0 >= h1 and cl0 < midpoint1 and cl0 >= o1:
            score = 36.0
            reasons = ["Red candle opened at new high and plunged >50% into green body"]

            if uptrend:
                score += 24.0
                reasons.append("Preceded by uptrend momentum")
            else:
                score += 5.0

            if vol_ratio >= 1.3:
                score += 18.0
                reasons.append(f"Volume spike ({vol_ratio:.1f}x 20MA)")
            elif vol_ratio >= 1.1:
                score += 8.0

            if range0 >= 0.8 * atr:
                score += 10.0

            return {
                "name": "Dark Cloud Cover",
                "direction": "Bearish",
                "confidence": min(96.0, score),
                "reasons": reasons,
                "description": "Bearish 2-candle reversal where an initial gap up is rejected and price closes deep into previous gain."
            }
        return None

    def _check_doji(self, c0, downtrend, uptrend, vol_ratio, atr):
        o0, h0, l0, cl0, body0, range0, u0, l0_w, bull0 = self._candle_props(c0)

        # Dragonfly Doji: open and close at/near high, very long lower shadow
        if body0 <= 0.08 * range0 and u0 <= 0.1 * range0 and l0_w >= 0.8 * range0:
            score = 34.0
            reasons = ["Dragonfly Doji: Long lower shadow with open=close near high"]
            if downtrend:
                score += 26.0
                reasons.append("Significant reversal location after downward trend")
            else:
                score += 4.0
            if vol_ratio >= 1.4:
                score += 18.0
                reasons.append(f"Volume rejection spike ({vol_ratio:.1f}x 20MA)")
            if range0 >= 0.8 * atr:
                score += 8.0

            return {
                "name": "Dragonfly Doji",
                "direction": "Bullish",
                "confidence": min(96.0, score),
                "reasons": reasons,
                "description": "Bullish indecision/reversal doji showing complete absorption of lower selling pressure."
            }

        # Gravestone Doji: open and close at/near low, very long upper shadow
        if body0 <= 0.08 * range0 and l0_w <= 0.1 * range0 and u0 >= 0.8 * range0:
            score = 34.0
            reasons = ["Gravestone Doji: Long upper shadow with open=close near low"]
            if uptrend:
                score += 26.0
                reasons.append("Significant reversal location at top of uptrend")
            else:
                score += 4.0
            if vol_ratio >= 1.4:
                score += 18.0
                reasons.append(f"Volume exhaustion spike ({vol_ratio:.1f}x 20MA)")
            if range0 >= 0.8 * atr:
                score += 8.0

            return {
                "name": "Gravestone Doji",
                "direction": "Bearish",
                "confidence": min(96.0, score),
                "reasons": reasons,
                "description": "Bearish indecision/reversal doji showing buyers were completely overwhelmed by overhead sellers."
            }

        return None
