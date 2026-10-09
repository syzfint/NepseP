#!/usr/bin/env python3
"""
Test Suite for RD-Agent-NEPSE Factor Factory
=============================================
Validates factor registration, Qlib-standard Rank IC & ICIR evaluation,
NEPSE transaction cost haircuts, governance gating, and R&D memory graph.
"""

import importlib
import pytest
import numpy as np
import pandas as pd

# Dynamic import to support numbered module paths
factor_mod = importlib.import_module("scripts.02_modeling_and_calculations.rd_agent_nepse_factor_factory")

RDAgentNEPSEFactory = factor_mod.RDAgentNEPSEFactory
NEPSEFactorEvaluator = factor_mod.NEPSEFactorEvaluator
NEPSEFactorDefinition = factor_mod.NEPSEFactorDefinition
FactorEvaluationResult = factor_mod.FactorEvaluationResult


@pytest.fixture
def mock_market_data():
    """Generates synthetic market data with both trending and mean-reverting properties."""
    np.random.seed(101)
    dates = pd.date_range("2024-01-01", periods=200)
    rets = np.random.normal(0.001, 0.02, 200)
    prices = 100.0 * np.exp(np.cumsum(rets))
    vols = np.random.lognormal(10.0, 0.5, 200)

    return pd.DataFrame({
        "open": prices * (1.0 + np.random.normal(0, 0.003, 200)),
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": vols,
    }, index=dates)


def test_factor_registration():
    """Verifies that factors register cleanly into the catalog."""
    factory = RDAgentNEPSEFactory()
    assert len(factory.factor_catalog) == 0

    factory.load_canonical_nepse_factors()
    assert len(factory.factor_catalog) == 5
    assert "BrokerSyndicateHerdingFactor" in factory.factor_catalog
    assert "PreOpenSpoofReversalFactor" in factory.factor_catalog


def test_factor_evaluator_metrics():
    """Verifies mathematical validity of Rank IC, ICIR, and monotonicity."""
    evaluator = NEPSEFactorEvaluator(transaction_cost_pct=0.0085, min_ic=0.03, min_net_sharpe=0.5)

    np.random.seed(42)
    n = 100
    # Create a synthetic factor with known positive correlation to forward return
    fwd_ret = pd.Series(np.random.normal(0.002, 0.02, n))
    perfect_factor = fwd_ret + np.random.normal(0, 0.005, n)

    res = evaluator.evaluate_factor(
        factor_series=perfect_factor,
        forward_returns=fwd_ret,
    )

    assert res.rank_ic > 0.50  # Strong positive correlation
    assert res.monotonicity_spread > 0  # Top quintile beats bottom
    assert res.passed_governance is True


def test_factor_governance_rejection():
    """Verifies that poor or inverted factors are rejected by governance gates."""
    evaluator = NEPSEFactorEvaluator(min_ic=0.05, min_net_sharpe=1.0)

    n = 100
    fwd_ret = pd.Series(np.random.normal(0.001, 0.02, n))
    # Inverted noise factor
    bad_factor = -fwd_ret + np.random.normal(0, 0.01, n)

    res = evaluator.evaluate_factor(
        factor_series=bad_factor,
        forward_returns=fwd_ret,
    )

    assert not res.passed_governance
    assert res.rejection_reason is not None


def test_rd_memory_graph_accumulation(mock_market_data):
    """Verifies that R&D lessons are accumulated in the memory graph."""
    factory = RDAgentNEPSEFactory()
    factory.load_canonical_nepse_factors()

    results = factory.run_mining_and_evaluation_cycle(mock_market_data)

    assert len(results["rd_memory_graph"]) == 5
    report = factory.generate_rd_report()
    assert "[RD-Agent-NEPSE]" in report
    assert "R&D Memory Graph" in report


def test_nepse_transaction_cost_drag():
    """Tests that high-turnover factors face realistic transaction drag under NEPSE 0.85% fees."""
    evaluator_cheap = NEPSEFactorEvaluator(transaction_cost_pct=0.0010)
    evaluator_nepse = NEPSEFactorEvaluator(transaction_cost_pct=0.0085)

    np.random.seed(42)
    n = 100
    fwd_ret = pd.Series(np.random.normal(0.001, 0.02, n))
    factor = pd.Series(np.random.normal(0, 1, n))

    res_cheap = evaluator_cheap.evaluate_factor(factor, fwd_ret)
    res_nepse = evaluator_nepse.evaluate_factor(factor, fwd_ret)

    # Higher NEPSE transaction cost must yield lower net Sharpe
    assert res_nepse.net_sharpe_after_costs <= res_cheap.net_sharpe_after_costs
