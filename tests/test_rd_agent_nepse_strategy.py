#!/usr/bin/env python3
"""
Test Suite for RD-Agent & Qlib Strategy at NEPSE Scale
======================================================
Validates AlphaNEPSE 12-factor calculation, rolling adaptive forecasting,
Gate G4 conviction filtering, and pipeline artifact generation.
"""

import importlib
import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

# Dynamic import to support numbered module paths
alpha_mod = importlib.import_module("scripts.02_modeling_and_calculations.alphanepse_engine")
forecaster_mod = importlib.import_module("scripts.02_modeling_and_calculations.adaptive_quant_forecaster")
pipeline_mod = importlib.import_module("scripts.02_modeling_and_calculations.run_rd_agent_nepse_pipeline")

AlphaNEPSEEngine = alpha_mod.AlphaNEPSEEngine
AdaptiveQuantForecaster = forecaster_mod.AdaptiveQuantForecaster
run_pipeline = pipeline_mod.run_pipeline


@pytest.fixture
def mock_market_panel():
    """Generates synthetic market data simulating NEPSE trading."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=150)
    rets = np.random.normal(0.001, 0.018, 150)
    prices = 100.0 * np.exp(np.cumsum(rets))
    vols = np.random.lognormal(11.0, 0.5, 150)

    return pd.DataFrame({
        "open": prices * (1.0 + np.random.normal(0, 0.002, 150)),
        "high": prices * 1.015,
        "low": prices * 0.985,
        "close": prices,
        "volume": vols,
    }, index=dates)


def test_alphanepse_engine_12_factors(mock_market_panel):
    """Verifies that all 12 AlphaNEPSE factors are computed cleanly without NaNs or Infs."""
    engine = AlphaNEPSEEngine()
    factors = engine.compute_all_factors(mock_market_panel)

    assert len(factors.columns) == 12
    for col in engine.factor_names:
        assert col in factors.columns
        assert not factors[col].isna().any(), f"NaN detected in {col}"
        assert not np.isinf(factors[col]).any(), f"Inf detected in {col}"


def test_adaptive_quant_forecaster_rolling(mock_market_panel):
    """Verifies rolling walk-forward training, T+2 embargo, and Gate G4 meta-probabilities."""
    forecaster = AdaptiveQuantForecaster(train_window=60, forward_horizon=5, embargo_days=2)
    res = forecaster.train_and_forecast_rolling(mock_market_panel)

    assert res["n_forecasts"] > 50
    assert -1.0 <= res["rank_ic"] <= 1.0
    assert 0.0 <= res["baseline_hit_rate_pct"] <= 100.0
    assert res["g4_certified_trades"] >= 0
    assert 0.0 <= res["g4_certified_hit_rate_pct"] <= 100.0
    assert 0.0 <= res["latest_meta_prob"] <= 1.0


def test_pipeline_execution_and_artifacts():
    """Verifies end-to-end pipeline run and presence of output artifacts."""
    results = run_pipeline()

    assert "factor_results" in results
    assert "forecast_results" in results
    assert "risk_results" in results
    assert "zoo_manifest" in results

    # Verify manifest file exists
    zoo_path = Path("static_data/alphanepse_zoo.json")
    assert zoo_path.exists()
    with open(zoo_path, "r") as f:
        manifest = json.load(f)
    assert manifest["status"] == "CERTIFIED"
    assert manifest["alphanepse_feature_count"] == 12

    # Verify report file exists
    report_path = Path("RD_AGENT_NEPSE_STRATEGY_REPORT.md")
    assert report_path.exists()
    with open(report_path, "r", encoding="utf-8") as f:
        report_text = f.read()
    assert "[RD-Agent & Qlib at NEPSE Scale]" in report_text
    assert "Adaptive Quant Forecaster Performance" in report_text
