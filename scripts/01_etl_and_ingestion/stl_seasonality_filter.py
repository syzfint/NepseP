#!/usr/bin/env python3
"""
scripts/01_etl_and_ingestion/stl_seasonality_filter.py

APEXMARKETENGINE — STL CALENDAR SEASONALITY & TREND ISOLATION FILTER
====================================================================
Decomposes sovereign NEPSE price & turnover time series into:
Price(t) = Trend(t) + Seasonal(t) + Residual(t)

Specialized for NEPSE Macro-Calendar Quirks:
1. Dashain / Tihar Festival Drains (Ashwin/Kartik, Sept/Oct):
   - Retail investors liquidate equity holdings for festival spending and bank bonuses.
   - Causes an artificial 15%–25% turnover contraction and short-term price dip.
2. Fiscal Year-End Tax Squaring (Asar / mid-July):
   - BFIs and corporate treasuries recall margin credit to square audited balance sheets.
3. Post-AGM Dividend / Bonus Book-Closure Dilution:
   - Annual dividend seasonality.

Outputs:
- Deseasonalized Trend series fed into Chronos-Bolt and LightGBM models,
  preventing false breakdown signals during known festival/tax cycles.
"""

import sys
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [STLSeasonality] %(message)s"
)
logger = logging.getLogger("STLSeasonality")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class STLDecompositionResult:
    symbol: str
    sample_count: int
    seasonal_strength: float       # Scale 0.0 - 1.0
    trend_strength: float          # Scale 0.0 - 1.0
    festival_cycle_active: bool    # True during Ashwin/Kartik (Dashain/Tihar)
    fiscal_close_active: bool      # True during Asar (July)
    latest_observed_price: float
    latest_deseasonalized_trend: float
    seasonal_distortion_pct: float
    status: str


class STLCalendarSeasonalityFilter:
    """Isolates cyclical calendar seasonality from structural price trends."""

    def __init__(self, seasonal_period_sessions: int = 50):
        # ~50 trading sessions corresponds to quarterly / seasonal festival cycles
        self.period = seasonal_period_sessions

    def is_festival_window(self, dt: pd.Timestamp) -> bool:
        """Dashain/Tihar retail withdrawal window generally falls between Sept 20 and Nov 10."""
        month = dt.month
        day = dt.day
        if month == 9 and day >= 20:
            return True
        if month == 10:
            return True
        if month == 11 and day <= 10:
            return True
        return False

    def is_fiscal_year_end(self, dt: pd.Timestamp) -> bool:
        """Nepalese fiscal year ends in mid-July (Asar 31), causing liquidity lockups."""
        return bool(dt.month == 7 and dt.day <= 20)

    def decompose_series(
        self,
        symbol: str,
        dates: List[Any],
        prices: np.ndarray
    ) -> Tuple[pd.DataFrame, STLDecompositionResult]:
        """
        Executes robust STL decomposition on 1D price series.
        Returns a DataFrame with [date, price, trend, seasonal, resid] and summary metrics.
        """
        if len(prices) < self.period * 2:
            # Fallback for short histories: return raw price as trend
            dts = pd.to_datetime(dates)
            df_res = pd.DataFrame({
                "date": dts,
                "price": prices,
                "trend": prices,
                "seasonal": np.zeros(len(prices)),
                "residual": np.zeros(len(prices))
            })
            summary = STLDecompositionResult(
                symbol=symbol,
                sample_count=len(prices),
                seasonal_strength=0.0,
                trend_strength=1.0,
                festival_cycle_active=self.is_festival_window(dts[-1]),
                fiscal_close_active=self.is_fiscal_year_end(dts[-1]),
                latest_observed_price=float(prices[-1]),
                latest_deseasonalized_trend=float(prices[-1]),
                seasonal_distortion_pct=0.0,
                status="INSUFFICIENT_HISTORY_FALLBACK"
            )
            return df_res, summary

        dts = pd.to_datetime(dates)
        ser = pd.Series(prices, index=dts)

        # Run STL decomposition
        stl = STL(ser, period=self.period, robust=True)
        res = stl.fit()

        trend = res.trend.values
        seasonal = res.seasonal.values
        resid = res.resid.values

        # Strength of seasonality: Var(Resid) / Var(Seasonal + Resid)
        var_resid = np.var(resid)
        var_seas_resid = np.var(seasonal + resid)
        seas_strength = max(0.0, min(1.0, 1.0 - (var_resid / var_seas_resid))) if var_seas_resid > 0 else 0.0

        # Strength of trend: Var(Resid) / Var(Trend + Resid)
        var_trend_resid = np.var(trend + resid)
        trend_strength = max(0.0, min(1.0, 1.0 - (var_resid / var_trend_resid))) if var_trend_resid > 0 else 1.0

        latest_dt = dts[-1]
        cur_p = float(prices[-1])
        cur_t = float(trend[-1])
        distortion_pct = round(((cur_p - cur_t) / cur_t) * 100.0, 2) if cur_t > 0 else 0.0

        df_out = pd.DataFrame({
            "date": dts,
            "price": prices,
            "trend": trend,
            "seasonal": seasonal,
            "residual": resid
        })

        summary = STLDecompositionResult(
            symbol=symbol,
            sample_count=len(prices),
            seasonal_strength=round(float(seas_strength), 4),
            trend_strength=round(float(trend_strength), 4),
            festival_cycle_active=self.is_festival_window(latest_dt),
            fiscal_close_active=self.is_fiscal_year_end(latest_dt),
            latest_observed_price=round(cur_p, 2),
            latest_deseasonalized_trend=round(cur_t, 2),
            seasonal_distortion_pct=distortion_pct,
            status="STL_DECOMPOSED_SUCCESS"
        )

        return df_out, summary


if __name__ == "__main__":
    filter_engine = STLCalendarSeasonalityFilter(seasonal_period_sessions=50)

    # Simulate 200 trading sessions with a seasonal dip during festival period
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=200, freq="B")
    base_trend = 500.0 + np.linspace(0, 50, 200)
    # Seasonal festival cycle: sinusoidal variation
    seasonal_pattern = 15.0 * np.sin(np.linspace(0, 4 * np.pi, 200))
    noise = np.random.normal(0, 3, 200)
    synthetic_prices = base_trend + seasonal_pattern + noise

    df_decomp, res = filter_engine.decompose_series("NEPSE_INDEX", dates, synthetic_prices)
    print("\n" + "=" * 70)
    print("      STL SEASONAL-TREND DECOMPOSITION TEST (NEPSE CALENDAR)")
    print("=" * 70)
    print(f"Target Symbol:            {res.symbol}")
    print(f"Observed Price:           {res.latest_observed_price:.2f}")
    print(f"Deseasonalized Trend:     {res.latest_deseasonalized_trend:.2f}")
    print(f"Seasonal Distortion:      {res.seasonal_distortion_pct:+.2f}%")
    print(f"Seasonal Strength:        {res.seasonal_strength:.4f}")
    print(f"Trend Strength:           {res.trend_strength:.4f}")
    print(f"Festival Window Active:   {res.festival_cycle_active}")
    print(f"Fiscal Close Active:      {res.fiscal_close_active}")
    print("=" * 70)
