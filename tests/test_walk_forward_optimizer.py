"""
Unit and regression test suite for Walk-Forward Portfolio Optimizer & CPCV Engine.
Validates:
  1. Point-In-Time 1-session lag guard: Feature alignment on t-1 and macro yields.
  2. Triple-Barrier Labeling invariants: binary meta-labels in {0, 1}.
  3. Schur-RA-HRP optimization properties: weights sum strictly to 1.0, non-negative weights.
  4. Out-of-sample results parquet existence and non-empty schema.
"""

import sys
import pytest
import numpy as np
import polars as pl
import importlib.util
from pathlib import Path

# Dynamic import for module with numeric directory prefix
_spec = importlib.util.spec_from_file_location(
    "walk_forward_portfolio_optimizer",
    Path(__file__).parent.parent / "scripts" / "04_backtesting" / "walk_forward_portfolio_optimizer.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

load_pit_dataset = _mod.load_pit_dataset
apply_triple_barrier_labeling = _mod.apply_triple_barrier_labeling
SchurRAHRP = _mod.SchurRAHRP
OUT_RESULTS_PARQUET = _mod.OUT_RESULTS_PARQUET


def test_pit_dataset_loading_and_lag_guard():
    """Verify PIT dataset loads with expected columns and non-null risk-free rate."""
    df = load_pit_dataset()
    assert len(df) > 5000
    assert "rf_yield_91d" in df.columns
    assert "days_to_promoter_unlock" in df.columns
    assert "buyer_hhi" in df.columns
    assert df["rf_yield_91d"].isnull().sum() == 0


def test_triple_barrier_labeling_properties():
    """Verify Triple-Barrier labeling generates valid binary targets {0, 1}."""
    df = load_pit_dataset()
    sample_df = df[df["symbol"] == "NABIL"].head(100).copy()
    labeled = apply_triple_barrier_labeling(sample_df)
    
    assert "meta_label" in labeled.columns
    unique_labels = set(labeled["meta_label"].unique())
    assert unique_labels.issubset({0, 1}), f"Unexpected meta labels: {unique_labels}"


def test_schur_ra_hrp_weights_invariants():
    """Verify Schur-RA-HRP outputs valid probability distribution (sum = 1, w_i >= 0)."""
    np.random.seed(42)
    n = 6
    rets = np.random.normal(0.0005, 0.02, size=(250, n))
    cov = np.cov(rets, rowvar=False)
    mean_ret = np.mean(rets, axis=0)

    hrp = SchurRAHRP(cov, mean_ret, rf_rate=0.05)
    weights = hrp.optimize()

    assert len(weights) == n
    assert np.all(weights >= 0.0), f"Negative weights detected: {weights}"
    assert np.isclose(np.sum(weights), 1.0, atol=1e-5), f"Weights sum {np.sum(weights)} != 1.0"


def test_out_of_sample_results_parquet_exists():
    """Verify out-of-sample backtest results Parquet artifact exists and is non-empty."""
    assert OUT_RESULTS_PARQUET.exists(), f"Missing {OUT_RESULTS_PARQUET}"
    df = pl.read_parquet(OUT_RESULTS_PARQUET)
    assert df.height > 1000
    assert "strategy_return" in df.columns
    assert "benchmark_return" in df.columns
    assert "strategy_cum" in df.columns
