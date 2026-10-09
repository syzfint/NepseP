#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/sample_uniqueness_labeler.py

APEXMARKETENGINE — SAMPLE UNIQUENESS WEIGHTING & CONCURRENCY CALCULATOR
========================================================================
Implements Marcos López de Prado's Sample Uniqueness Weighting (AFML, Chapter 4).

Mathematical Architecture:
1. Label Concurrency Matrix:
   Given N triple-barrier label spans [t_{i,0}, t_{i,1}], the concurrency c_t at time t is:
   c_t = sum_{i=1}^N 1_{t in [t_{i,0}, t_{i,1}]}
2. Sample Uniqueness u_{i,t}:
   u_{i,t} = 1 / c_t
   Average uniqueness of sample i over its holding span [t_{i,0}, t_{i,1}]:
   u_i = (1 / L_i) * sum_{t=t_{i,0}}^{t_{i,1}} (1 / c_t)
   where L_i is the span length in sessions.
3. LightGBM / Model Training Weight:
   w_i = (u_i / sum_j u_j) * N
   - Penalizes highly overlapping label clusters (e.g. 5-day bars during crash regimes)
   - Eliminates redundant sample correlation and out-of-sample overconfidence.
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SampleUniqueness] %(message)s"
)
logger = logging.getLogger("SampleUniqueness")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class UniquenessSummary:
    total_samples: int
    mean_concurrency: float
    max_concurrency: int
    mean_uniqueness: float           # In (0, 1]
    effective_sample_size: float     # sum(u_i)
    redundancy_reduction_pct: float  # (1 - mean_u) * 100%


class SampleUniquenessWeightingEngine:
    """Calculates concurrency and sample uniqueness weights for triple-barrier labels."""

    def __init__(self, default_horizon_days: int = 5):
        self.default_horizon = default_horizon_days

    def compute_concurrency_and_uniqueness(
        self,
        event_spans_df: pd.DataFrame
    ) -> Tuple[pd.Series, UniquenessSummary]:
        """
        Ingests a DataFrame with columns ['start_date', 'end_date']
        and returns a Series of sample uniqueness weights u_i.
        """
        if event_spans_df.empty or "start_date" not in event_spans_df.columns:
            return pd.Series(dtype=float), UniquenessSummary(0, 0.0, 0, 1.0, 0.0, 0.0)

        df = event_spans_df.copy()
        df["start_date"] = pd.to_datetime(df["start_date"])
        if "end_date" not in df.columns:
            df["end_date"] = df["start_date"] + pd.to_timedelta(self.default_horizon, unit="D")
        else:
            df["end_date"] = pd.to_datetime(df["end_date"])

        # Create global timeline of all active trading sessions
        all_dates = pd.date_range(df["start_date"].min(), df["end_date"].max(), freq="D")
        concurrency_series = pd.Series(0, index=all_dates)

        # Vectorized concurrency calculation
        for _, row in df.iterrows():
            s, e = row["start_date"], row["end_date"]
            concurrency_series.loc[s:e] += 1

        uniqueness_weights = []
        for _, row in df.iterrows():
            s, e = row["start_date"], row["end_date"]
            sub_c = concurrency_series.loc[s:e]
            # Avoid division by zero
            sub_u = 1.0 / np.maximum(sub_c.values, 1)
            u_i = float(np.mean(sub_u))
            uniqueness_weights.append(u_i)

        u_series = pd.Series(uniqueness_weights, index=df.index, name="sample_uniqueness")
        
        # Normalized sample weights centered around 1.0
        n_samples = len(df)
        sum_u = float(u_series.sum())
        norm_weights = (u_series / sum_u) * n_samples if sum_u > 0 else u_series

        mean_c = float(concurrency_series[concurrency_series > 0].mean()) if len(concurrency_series[concurrency_series > 0]) > 0 else 1.0
        max_c = int(concurrency_series.max())
        mean_u = float(u_series.mean())
        red_pct = round((1.0 - mean_u) * 100.0, 2)

        summary = UniquenessSummary(
            total_samples=n_samples,
            mean_concurrency=round(mean_c, 2),
            max_concurrency=max_c,
            mean_uniqueness=round(mean_u, 4),
            effective_sample_size=round(sum_u, 2),
            redundancy_reduction_pct=red_pct
        )

        return norm_weights, summary


if __name__ == "__main__":
    engine = SampleUniquenessWeightingEngine(default_horizon_days=5)

    # Simulate 20 daily overlapping events during high-volatility session
    base_dt = pd.to_datetime("2026-10-01")
    event_starts = [base_dt + pd.Timedelta(days=i) for i in range(20)]
    event_ends = [s + pd.Timedelta(days=5) for s in event_starts]

    test_df = pd.DataFrame({"start_date": event_starts, "end_date": event_ends})
    weights, summ = engine.compute_concurrency_and_uniqueness(test_df)

    print("\n" + "=" * 70)
    print("      SAMPLE UNIQUENESS WEIGHTING (LÓPEZ DE PRADO) TEST")
    print("=" * 70)
    print(f"Total Labels:             {summ.total_samples}")
    print(f"Mean Concurrency c(t):    {summ.mean_concurrency:.2f} active overlapping windows")
    print(f"Max Concurrency:          {summ.max_concurrency} overlapping windows")
    print(f"Mean Uniqueness u_i:      {summ.mean_uniqueness:.4f} (Scale: 0.0 - 1.0)")
    print(f"Effective Sample Size:    {summ.effective_sample_size:.1f} / {summ.total_samples}")
    print(f"Redundancy Reduction:     {summ.redundancy_reduction_pct:.1f}%")
    print(f"Sample Weight Min / Max:  {weights.min():.2f} / {weights.max():.2f}")
    print("=" * 70)
