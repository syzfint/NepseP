#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/cpcv_backtester.py

APEXMARKETENGINE — COMBINATORIAL PURGED CROSS-VALIDATION (CPCV) ENGINE
======================================================================
Replaces single-path historical backtests with Marcos López de Prado's
Combinatorial Purged Cross-Validation (AFML, Chapter 12).

Mathematical Architecture:
1. Combinatorial Grouping:
   Divides history into N contiguous chronological blocks (e.g., N = 6).
   Generates C(N, k) combinatorial splits where k blocks form the test fold
   (e.g., C(6, 2) = 15 test combinations).
2. Purging & Embargoing:
   - Purge: Removes training observations whose label horizon overlaps test set bounds.
   - Embargo: Removes h sessions (default h = 2 trading days) immediately following test
     periods to eliminate T+2 settlement autoregressive leakage.
3. Sharpe Ratio Distribution & PBO:
   Calculates Sharpe ratio across all combinatorial test paths to obtain:
   - Median Sharpe, 5th percentile (downside VaR), 95th percentile
   - Probability of Backtest Overfitting (PBO): P(Sharpe_OOS <= 0)
"""

import sys
import json
import logging
from itertools import combinations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [CPCVBacktester] %(message)s"
)
logger = logging.getLogger("CPCVBacktester")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class CPCVSplit:
    split_id: int
    train_indices: np.ndarray
    test_indices: np.ndarray
    purged_count: int
    embargoed_count: int


@dataclass
class CPCVBacktestSummary:
    n_splits: int
    n_blocks: int
    k_test_blocks: int
    sharpe_mean: float
    sharpe_median: float
    sharpe_5th_percentile: float
    sharpe_95th_percentile: float
    probability_of_backtest_overfitting: float  # PBO in [0, 1]
    is_overfitting_controlled: bool             # True if PBO < 0.05
    all_path_sharpes: List[float]


class CombinatorialPurgedCrossValidation:
    """Generates purged, embargoed combinatorial cross-validation splits and evaluates paths."""

    def __init__(
        self,
        n_blocks: int = 6,
        k_test_blocks: int = 2,
        embargo_pct: float = 0.015,
        label_horizon_sessions: int = 5
    ):
        self.n_blocks = n_blocks
        self.k_test_blocks = k_test_blocks
        self.embargo_pct = embargo_pct
        self.label_horizon = label_horizon_sessions

    def generate_splits(self, n_samples: int) -> List[CPCVSplit]:
        """Generates all C(N, k) purged and embargoed train/test index splits."""
        indices = np.arange(n_samples)
        block_size = n_samples // self.n_blocks
        blocks = []
        for i in range(self.n_blocks):
            start = i * block_size
            end = n_samples if i == self.n_blocks - 1 else (i + 1) * block_size
            blocks.append(indices[start:end])

        embargo_samples = max(2, int(n_samples * self.embargo_pct))
        comb_test_groups = list(combinations(range(self.n_blocks), self.k_test_blocks))

        splits: List[CPCVSplit] = []
        for split_idx, test_group in enumerate(comb_test_groups):
            test_idx = np.concatenate([blocks[b] for b in test_group])
            train_candidates = np.concatenate([blocks[b] for b in range(self.n_blocks) if b not in test_group])

            # Apply Purging: remove training samples whose forward label enters any test block
            purged = []
            for t_block in test_group:
                t_start = blocks[t_block][0]
                t_end = blocks[t_block][-1]
                # Any train sample within [t_start - horizon, t_start] is purged
                purge_range = set(range(max(0, t_start - self.label_horizon), t_start))
                purged.extend(purge_range)

            # Apply Embargo: remove training samples within [t_end + 1, t_end + embargo_samples]
            embargoed = []
            for t_block in test_group:
                t_end = blocks[t_block][-1]
                embargo_range = set(range(t_end + 1, min(n_samples, t_end + 1 + embargo_samples)))
                embargoed.extend(embargo_range)

            excluded = set(purged).union(set(embargoed)).union(set(test_idx))
            final_train = np.array([idx for idx in train_candidates if idx not in excluded])

            splits.append(CPCVSplit(
                split_id=split_idx,
                train_indices=final_train,
                test_indices=np.sort(test_idx),
                purged_count=len(purged),
                embargoed_count=len(embargoed)
            ))

        return splits

    def evaluate_strategy_returns(
        self,
        session_returns: np.ndarray
    ) -> CPCVBacktestSummary:
        """Evaluates simulated returns across all combinatorial paths to compute PBO."""
        splits = self.generate_splits(len(session_returns))
        path_sharpes = []

        for sp in splits:
            test_rets = session_returns[sp.test_indices]
            if len(test_rets) > 10 and np.std(test_rets) > 0:
                ann_sharpe = float((np.mean(test_rets) / np.std(test_rets)) * np.sqrt(252.0))
                path_sharpes.append(round(ann_sharpe, 3))
            else:
                path_sharpes.append(0.0)

        sharpe_arr = np.array(path_sharpes)
        mean_s = float(np.mean(sharpe_arr))
        median_s = float(np.median(sharpe_arr))
        p5_s = float(np.percentile(sharpe_arr, 5))
        p95_s = float(np.percentile(sharpe_arr, 95))

        # Probability of Backtest Overfitting (fraction of paths with Sharpe <= 0)
        pbo = round(float(np.mean(sharpe_arr <= 0.0)), 4)
        is_safe = bool(pbo < 0.05)

        return CPCVBacktestSummary(
            n_splits=len(splits),
            n_blocks=self.n_blocks,
            k_test_blocks=self.k_test_blocks,
            sharpe_mean=round(mean_s, 2),
            sharpe_median=round(median_s, 2),
            sharpe_5th_percentile=round(p5_s, 2),
            sharpe_95th_percentile=round(p95_s, 2),
            probability_of_backtest_overfitting=pbo,
            is_overfitting_controlled=is_safe,
            all_path_sharpes=path_sharpes
        )


if __name__ == "__main__":
    cpcv = CombinatorialPurgedCrossValidation(n_blocks=6, k_test_blocks=2)

    # Simulate 500 trading sessions of a profitable quant strategy (mean daily return 0.08%, vol 1.1%)
    np.random.seed(42)
    daily_rets = np.random.normal(0.0008, 0.011, 500)

    summary = cpcv.evaluate_strategy_returns(daily_rets)
    print("\n" + "=" * 70)
    print("      COMBINATORIAL PURGED CROSS-VALIDATION (CPCV) TEST")
    print("=" * 70)
    print(f"Total Combinatorial Paths: {summary.n_splits} splits (C({summary.n_blocks}, {summary.k_test_blocks}))")
    print(f"Mean Sharpe Ratio:         {summary.sharpe_mean:.2f}")
    print(f"Median Sharpe Ratio:       {summary.sharpe_median:.2f}")
    print(f"5th Percentile Sharpe:     {summary.sharpe_5th_percentile:.2f} (Downside Tail)")
    print(f"95th Percentile Sharpe:    {summary.sharpe_95th_percentile:.2f} (Upside Ceiling)")
    print(f"PBO (Overfitting Risk):    {summary.probability_of_backtest_overfitting * 100:.1f}% (Threshold: < 5%)")
    print(f"PBO Guard Passed:          {summary.is_overfitting_controlled}")
    print("=" * 70)
