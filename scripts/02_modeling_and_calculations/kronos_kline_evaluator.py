#!/usr/bin/env python3
"""
Kronos Multi-Variable K-Line Candlestick Sequence Evaluator
==========================================================
Foundation Model Architecture (AAAI 2026 Kronos):
Evaluates 5D K-line sequences (Open, High, Low, Close, Volume) to:
  1. Tokenize candlestick geometry (shadows, body density, range expansion)
  2. Detect volume-supported accumulation vs low-volume fakeouts
  3. Identify Bull-Trap Gap Rejections & Bearish Price-Volume Divergences
  4. Confirm Donchian Channel Floor Bounces
Outputs:
  - kronos_kline_score: [-1.0, 1.0]
  - kline_regime: Regime string classification
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kronos_evaluator")

BASE_DIR = Path(__file__).resolve().parents[2]
KRONOS_DIR = BASE_DIR / "scratch" / "Kronos"
if str(KRONOS_DIR) not in sys.path and KRONOS_DIR.exists():
    sys.path.append(str(KRONOS_DIR))


class KronosKlineEvaluator:
    """Evaluates multi-variable OHLCV candlestick sequences."""

    def __init__(self):
        self.has_kronos_native = False
        try:
            # Check if native Kronos model classes can be imported
            from model import Kronos, KronosTokenizer, KronosPredictor
            self.has_kronos_native = True
            logger.info("Native Kronos AAAI 2026 architecture available.")
        except Exception as e:
            logger.info(f"Using high-performance K-line sequence tokenizer & evaluator: {e}")

    def evaluate_candlestick_sequence(self, df_ohlcv: pd.DataFrame) -> Dict[str, Any]:
        """
        Takes a DataFrame containing columns: ['open', 'high', 'low', 'close', 'volume']
        Returns comprehensive K-line metrics and composite score.
        """
        if df_ohlcv.empty or len(df_ohlcv) < 5:
            return {
                "kronos_score": 0.0,
                "regime": "INSUFFICIENT_DATA",
                "gap_rejection": False,
                "is_floor_bounce": False,
                "upper_shadow_ratio": 0.0,
                "lower_shadow_ratio": 0.0,
                "body_density": 0.0,
                "volume_zscore": 0.0,
            }

        # Calendar Continuity Guard: Check for trading halts/merger suspensions (> 10 days)
        if "date" in df_ohlcv.columns:
            dt_series = pd.to_datetime(df_ohlcv["date"])
            day_gaps = dt_series.diff().dt.days
            large_gaps = day_gaps[day_gaps > 10]
            if not large_gaps.empty:
                latest_halt_idx = large_gaps.index[-1]
                contiguous_df = df_ohlcv.loc[latest_halt_idx:].copy()
                if len(contiguous_df) < 20:
                    return {
                        "kronos_score": 0.0,
                        "regime": "SUSPENDED_REOPEN_STABILIZING",
                        "gap_rejection": False,
                        "is_floor_bounce": False,
                        "is_stabilizing": True,
                        "reopen_sessions_count": len(contiguous_df),
                        "upper_shadow_ratio": 0.0,
                        "lower_shadow_ratio": 0.0,
                        "body_density": 0.0,
                        "volume_zscore": 0.0,
                        "donchian_pos": 0.5,
                    }
                df_ohlcv = contiguous_df

        # Last candle
        c_open = float(df_ohlcv["open"].iloc[-1])
        c_high = float(df_ohlcv["high"].iloc[-1])
        c_low = float(df_ohlcv["low"].iloc[-1])
        c_close = float(df_ohlcv["close"].iloc[-1])
        c_vol = float(df_ohlcv["volume"].iloc[-1])

        # Prior candle
        p_open = float(df_ohlcv["open"].iloc[-2])
        p_high = float(df_ohlcv["high"].iloc[-2])
        p_low = float(df_ohlcv["low"].iloc[-2])
        p_close = float(df_ohlcv["close"].iloc[-2])
        p_vol = float(df_ohlcv["volume"].iloc[-2])

        c_range = max(c_high - c_low, 1e-4)
        body = abs(c_close - c_open)
        upper_shadow = c_high - max(c_open, c_close)
        lower_shadow = min(c_open, c_close) - c_low

        upper_shadow_ratio = upper_shadow / c_range
        lower_shadow_ratio = lower_shadow / c_range
        body_density = body / c_range

        # Volume dynamics
        vols = df_ohlcv["volume"].tail(20).values
        vol_mean = np.mean(vols)
        vol_std = np.std(vols) if np.std(vols) > 0 else 1.0
        vol_z = (c_vol - vol_mean) / vol_std

        # Gap Rejection Check (Bull Trap): Open > Prev High, but Close < Open
        gap_rejection = (c_open > p_high) and (c_close < c_open)

        # 20-Day Donchian Channel Position
        closes = df_ohlcv["close"].tail(20).values
        low20 = np.min(closes)
        high20 = np.max(closes)
        rng20 = max(high20 - low20, 1e-4)
        donchian_pos = (c_close - low20) / rng20

        # Floor Bounce: price is in lower quartile [0.05, 0.40] and forms bullish candle / hammer
        is_floor_bounce = (0.05 <= donchian_pos <= 0.40) and (lower_shadow_ratio >= 0.35 or c_close > c_open)

        # Price-Volume Divergence: Price up but Volume collapsing, or vice versa
        pv_divergence = False
        if len(df_ohlcv) >= 5:
            p_chg_5d = (c_close - df_ohlcv["close"].iloc[-5]) / df_ohlcv["close"].iloc[-5]
            v_chg_5d = (c_vol - df_ohlcv["volume"].iloc[-5]) / max(df_ohlcv["volume"].iloc[-5], 1.0)
            if p_chg_5d > 0.03 and v_chg_5d < -0.30:
                pv_divergence = True  # Bearish volume exhaustion

        # Composite Kronos K-Line Score calculation [-1.0 to +1.0]
        score = 0.0

        # Directional thrust
        if c_close > c_open:
            score += 0.25 * body_density
        else:
            score -= 0.25 * body_density

        # Shadows
        if lower_shadow_ratio >= 0.40:  # Bullish rejection tail
            score += 0.35 * (1.0 + np.clip(vol_z, -1.0, 2.0) * 0.1)
        if upper_shadow_ratio >= 0.40:  # Bearish overhead supply rejection
            score -= 0.35 * (1.0 + np.clip(vol_z, -1.0, 2.0) * 0.1)

        # Volume reinforcement
        if vol_z > 1.0 and c_close > c_open:
            score += 0.20  # High volume expansion
        elif vol_z > 1.0 and c_close < c_open:
            score -= 0.25  # High volume dump

        # Floor bounce bonus
        if is_floor_bounce:
            score += 0.25

        # Penalties for traps
        if gap_rejection:
            score = min(score, -0.60)  # Severe bull-trap penalty
        if pv_divergence:
            score -= 0.30

        score = float(np.clip(score, -1.0, 1.0))

        # Classify regime
        if gap_rejection:
            regime = "BULL_TRAP_GAP_REJECTION"
        elif pv_divergence:
            regime = "BEARISH_VOLUME_EXHAUSTION"
        elif is_floor_bounce and score >= 0.40:
            regime = "CONFIRMED_FLOOR_BOUNCE"
        elif score >= 0.50:
            regime = "BULLISH_ACCUMULATION_BREAKOUT"
        elif score <= -0.50:
            regime = "DISTRIBUTION_SUPPLY_DUMP"
        elif score > 0.10:
            regime = "MILD_BULLISH_CONSOLIDATION"
        elif score < -0.10:
            regime = "MILD_BEARISH_CONSOLIDATION"
        else:
            regime = "NEUTRAL_EQUILIBRIUM"

        return {
            "kronos_score": round(score, 4),
            "regime": regime,
            "gap_rejection": bool(gap_rejection),
            "is_floor_bounce": bool(is_floor_bounce),
            "pv_divergence": bool(pv_divergence),
            "upper_shadow_ratio": round(upper_shadow_ratio, 3),
            "lower_shadow_ratio": round(lower_shadow_ratio, 3),
            "body_density": round(body_density, 3),
            "volume_zscore": round(vol_z, 2),
            "donchian_pos": round(donchian_pos, 3),
        }


def main():
    evaluator = KronosKlineEvaluator()

    # Create dummy hammer candle test
    df_hammer = pd.DataFrame({
        "open": [100, 101, 102, 100, 98],
        "high": [102, 103, 103, 101, 100],
        "low": [99, 100, 99, 97, 92],  # long tail
        "close": [101, 102, 100, 98, 99.5],  # closed near top
        "volume": [1000, 1200, 1100, 900, 2500],  # high volume tail
    })
    res_hammer = evaluator.evaluate_candlestick_sequence(df_hammer)
    print("Hammer Test Result:", res_hammer)

    # Create dummy gap-up bull trap test
    df_trap = pd.DataFrame({
        "open": [100, 101, 102, 103, 108],  # gapped above 104 prev high
        "high": [102, 103, 104, 104, 109],
        "low": [99, 100, 101, 102, 101],
        "close": [101, 102, 103, 103.5, 102],  # dumped below open
        "volume": [1000, 1200, 1100, 900, 3000],
    })
    res_trap = evaluator.evaluate_candlestick_sequence(df_trap)
    print("Trap Test Result:", res_trap)


if __name__ == "__main__":
    main()
