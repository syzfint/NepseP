#!/usr/bin/env python3
"""
Test Suite for QuantRiskLab Portfolio Risk Engine
=================================================
Validates portfolio analytics, multi-methodology VaR/ES, stress-testing,
Kupiec Likelihood-Ratio (POF) unconditional coverage, and dashboard endpoints.
"""

import importlib
import pytest
import numpy as np
import pandas as pd
from scipy import stats

# Dynamic import to support numbered module paths
risk_lab_mod = importlib.import_module("scripts.02_modeling_and_calculations.portfolio_risk_lab")
dashboard_mod = importlib.import_module("scripts.02_modeling_and_calculations.risk_dashboard_app")

PortfolioAnalytics = risk_lab_mod.PortfolioAnalytics
ValueAtRiskEngine = risk_lab_mod.ValueAtRiskEngine
StressTestingEngine = risk_lab_mod.StressTestingEngine
KupiecBacktester = risk_lab_mod.KupiecBacktester
QuantRiskLab = risk_lab_mod.QuantRiskLab
PortfolioWeightsError = risk_lab_mod.PortfolioWeightsError
RiskModelError = risk_lab_mod.RiskModelError


@pytest.fixture
def sample_returns():
    """Generates synthetic multi-asset return series with known parameters."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=300)
    data = {
        "NABIL": np.random.normal(0.0006, 0.015, 300),
        "GBIME": np.random.normal(0.0004, 0.016, 300),
        "CHCL": np.random.normal(0.0008, 0.024, 300),
        "CIT": np.random.normal(0.0005, 0.014, 300),
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def sample_weights():
    return {"NABIL": 0.35, "GBIME": 0.25, "CHCL": 0.20, "CIT": 0.20}


def test_weights_validation_and_rejection():
    """Tests that weight constraints (sum=1, non-negative, dimension match) are strictly enforced."""
    analytics = PortfolioAnalytics()

    # Valid dictionary
    valid = {"A": 0.6, "B": 0.4}
    res = analytics.validate_weights(valid)
    assert abs(sum(res.values()) - 1.0) < 1e-6

    # Valid array with symbols
    res_arr = analytics.validate_weights([0.5, 0.5], symbols=["A", "B"])
    assert res_arr["A"] == 0.5 and res_arr["B"] == 0.5

    # Sum != 1.0
    with pytest.raises(PortfolioWeightsError):
        analytics.validate_weights({"A": 0.5, "B": 0.3})

    # Negative weight (NEPSE long-only violation)
    with pytest.raises(PortfolioWeightsError):
        analytics.validate_weights({"A": 1.2, "B": -0.2})

    # Missing symbols mismatch
    with pytest.raises(PortfolioWeightsError):
        analytics.validate_weights([0.5, 0.5], symbols=["A"])


def test_portfolio_analytics_metrics(sample_returns, sample_weights):
    """Verifies annualized return, volatility, Sharpe ratio, and drawdown calculations."""
    analytics = PortfolioAnalytics(trading_days=240, rf_rate=0.04)
    port_ret = analytics.compute_portfolio_returns(sample_returns, sample_weights)

    metrics = analytics.compute_metrics(port_ret)
    assert metrics["n_observations"] == 300
    assert metrics["annualized_expected_return"] > 0
    assert metrics["annualized_volatility"] > 0
    assert metrics["max_drawdown"] >= 0
    assert metrics["sharpe_ratio"] != 0

    # Mathematical identity check: annualized_vol = daily_std * sqrt(240)
    expected_ann_vol = port_ret.std(ddof=1) * np.sqrt(240)
    assert abs(metrics["annualized_volatility"] - expected_ann_vol) < 1e-5


def test_var_and_expected_shortfall_methodologies(sample_returns, sample_weights):
    """
    Verifies that:
      1. Expected Shortfall >= Value at Risk across all models (tail expectation property).
      2. Parametric Gaussian matches closed-form normal formulas.
      3. Monte Carlo estimates converge close to parametric.
    """
    analytics = PortfolioAnalytics()
    port_ret = analytics.compute_portfolio_returns(sample_returns, sample_weights)
    var_engine = ValueAtRiskEngine()

    conf = 0.95
    h_var, h_es = var_engine.historical_var_es(port_ret, confidence_level=conf)
    p_var, p_es = var_engine.parametric_var_es(port_ret, confidence_level=conf)
    mc_var, mc_es = var_engine.monte_carlo_var_es(port_ret, confidence_level=conf, n_simulations=20000, seed=42)

    # Property 1: Expected Shortfall is strictly >= VaR
    assert h_es >= h_var
    assert p_es > p_var
    assert mc_es > mc_var

    # Property 2: Parametric closed-form validation
    mu = float(port_ret.mean())
    sigma = float(port_ret.std(ddof=1))
    z_alpha = float(stats.norm.ppf(conf))
    expected_p_var = z_alpha * sigma - mu
    assert abs(p_var - expected_p_var) < 1e-4

    # Property 3: Monte Carlo convergence within 5% of parametric
    assert abs(mc_var - p_var) / p_var < 0.05
    assert abs(mc_es - p_es) / p_es < 0.05


def test_stress_testing_scenarios(sample_returns, sample_weights):
    """Verifies that adverse stress scenarios properly expand tail risk and Expected Shortfall."""
    analytics = PortfolioAnalytics()
    port_ret = analytics.compute_portfolio_returns(sample_returns, sample_weights)
    stress_engine = StressTestingEngine()

    stress_res = stress_engine.run_stress_scenarios(port_ret, confidence_level=0.95)
    base_var = stress_res["baseline"]["parametric_var"]
    base_es = stress_res["baseline"]["parametric_es"]

    scenarios = stress_res["scenarios"]
    required_scenarios = [
        "equity_crash",
        "interest_rate_shock",
        "liquidity_stress",
        "nepse_nrb_margin_cap",
        "nepse_monsoon_force_majeure",
        "nepse_promoter_lockin_flood",
    ]

    for sc in required_scenarios:
        assert sc in scenarios
        sc_data = scenarios[sc]
        # In all adverse scenarios, stressed VaR and ES must strictly exceed baseline
        assert sc_data["stressed_var"] > base_var
        assert sc_data["stressed_expected_shortfall"] > base_es
        assert sc_data["delta_var"] > 0
        assert sc_data["delta_expected_shortfall"] > 0


def test_kupiec_pof_likelihood_ratio_statistic():
    """
    Tests Kupiec Proportion-of-Failures (POF) Likelihood-Ratio calculation
    against textbook numerical benchmarks.
    """
    # Case 1: Well-calibrated model (N=250, x=12 exceptions at p=0.05)
    lr_stat, p_val = KupiecBacktester.calculate_lr_stat(n=250, x=12, p=0.05)
    assert lr_stat < 1.0
    assert p_val > 0.05  # Fail to reject H0 (PASS)

    # Case 2: Underestimating risk (N=250, x=30 exceptions at p=0.05)
    lr_stat_bad, p_val_bad = KupiecBacktester.calculate_lr_stat(n=250, x=30, p=0.05)
    assert lr_stat_bad > 15.0
    assert p_val_bad < 0.001  # Reject H0 (FAIL)

    # Case 3: Boundary case with 0 exceptions
    lr_zero, p_val_zero = KupiecBacktester.calculate_lr_stat(n=250, x=0, p=0.05)
    assert lr_zero > 0
    assert 0.0 <= p_val_zero <= 1.0


def test_rolling_kupiec_backtesting(sample_returns, sample_weights):
    """Tests rolling out-of-sample backtesting loop with zero lookahead bias."""
    analytics = PortfolioAnalytics()
    port_ret = analytics.compute_portfolio_returns(sample_returns, sample_weights)
    backtester = KupiecBacktester()

    # Estimation window = 100, leaving 200 out-of-sample forecast days
    bt_res = backtester.run_rolling_backtest(
        port_ret, estimation_window=100, confidence_level=0.95, method="historical"
    )

    assert bt_res["number_of_forecasts"] == 200
    assert bt_res["number_of_exceptions"] >= 0
    assert 0.0 <= bt_res["observed_exception_rate"] <= 1.0
    assert bt_res["expected_exception_rate"] == 0.05
    assert bt_res["unconditional_coverage_verdict"] in ["PASS", "FAIL"]


def test_quant_risk_lab_orchestrator(sample_returns, sample_weights):
    """Tests the top-level QuantRiskLab orchestrator and markdown audit generator."""
    lab = QuantRiskLab(trading_days=240, rf_rate=0.04)
    results = lab.run_full_analysis(sample_returns, sample_weights, estimation_window=100)

    assert "portfolio_analytics" in results
    assert "value_at_risk_and_expected_shortfall" in results
    assert "stress_testing" in results
    assert "rolling_kupiec_backtesting" in results

    report = lab.generate_markdown_report(results)
    assert "[QuantRiskLab] Institutional Portfolio Risk & Stress Report" in report
    assert "Historical Simulation" in report
    assert "Kupiec POF Unconditional Coverage" in report


def test_flask_dashboard_endpoints():
    """Tests that the Flask web dashboard and REST API endpoints return valid responses."""
    client = dashboard_mod.app.test_client()

    # 1. HTML Dashboard
    resp_html = client.get("/")
    assert resp_html.status_code == 200
    assert b"TITAN COCKPIT" in resp_html.data or b"QuantRiskLab" in resp_html.data

    # 2. JSON Summary API
    resp_summary = client.get("/api/summary")
    assert resp_summary.status_code == 200
    data = resp_summary.json
    assert "portfolio_analytics" in data
    assert "value_at_risk_and_expected_shortfall" in data

    # 3. Stress Test API
    resp_stress = client.get("/api/stress-test")
    assert resp_stress.status_code == 200
    assert "scenarios" in resp_stress.json

    # 4. Backtest API
    resp_bt = client.get("/api/backtest")
    assert resp_bt.status_code == 200
    assert "historical" in resp_bt.json
