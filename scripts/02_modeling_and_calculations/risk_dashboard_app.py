#!/usr/bin/env python3
"""
TITAN COCKPIT: Sovereign Risk & Portfolio Analytics Engine
=========================================================
Web interface and REST API for real-time portfolio analytics,
multi-methodology VaR/ES, stress-testing simulations, and rolling Kupiec backtesting.
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, render_template_string

# Relative import compatibility
sys.path.insert(0, str(Path(__file__).resolve().parent))
from portfolio_risk_lab import QuantRiskLab, PortfolioAnalytics, ValueAtRiskEngine, StressTestingEngine, KupiecBacktester

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RiskDashboard")

BASE_DIR = Path(__file__).resolve().parents[2]
PARQUET_PATH = BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"

app = Flask(__name__)
lab = QuantRiskLab(trading_days=240, rf_rate=0.04)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN COCKPIT | Sovereign Risk & Portfolio Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .card { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; margin-bottom: 20px; }
        .card-header { background-color: #334155; color: #38bdf8; font-weight: 600; border-bottom: 1px solid #475569; }
        .stat-value { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
        .stat-label { font-size: 0.85rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
        .table { color: #f8fafc; }
        .table-dark th { background-color: #1e293b; color: #94a3b8; border-color: #334155; }
        .table-dark td { background-color: #0f172a; border-color: #334155; }
        .badge-pass { background-color: #10b981; color: white; padding: 6px 12px; border-radius: 6px; }
        .badge-fail { background-color: #ef4444; color: white; padding: 6px 12px; border-radius: 6px; }
        .stress-bar { height: 8px; border-radius: 4px; background: linear-gradient(90deg, #f59e0b, #ef4444); }
    </style>
</head>
<body class="p-4">
    <div class="container-fluid">
        <!-- Header -->
        <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
            <div>
                <h2 class="mb-1 text-light fw-bold">TITAN COCKPIT: Sovereign Portfolio Risk & Capital Preservation Engine</h2>
                <p class="text-secondary mb-0">Adhering to Harvard CS50x Quantitative Risk Architecture | NEPSE Microstructure Calibrated</p>
            </div>
            <div>
                <span class="badge bg-primary fs-6 px-3 py-2">NEPSE Active Regime</span>
            </div>
        </div>

        <!-- Portfolio KPI Cards -->
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="card p-3 shadow-sm">
                    <div class="stat-label">Annualized Expected Return</div>
                    <div class="stat-value text-success">+{{ data.portfolio_analytics.annualized_expected_return_pct }}%</div>
                    <small class="text-secondary">240 Trading Days Basis</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3 shadow-sm">
                    <div class="stat-label">Annualized Volatility</div>
                    <div class="stat-value text-warning">{{ data.portfolio_analytics.annualized_volatility_pct }}%</div>
                    <small class="text-secondary">Rolling Daily Dispersion</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3 shadow-sm">
                    <div class="stat-label">Sharpe Ratio (Rf=4.0%)</div>
                    <div class="stat-value text-info">{{ data.portfolio_analytics.sharpe_ratio }}</div>
                    <small class="text-secondary">NRB 91-Day T-Bill Benchmark</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3 shadow-sm">
                    <div class="stat-label">Maximum Drawdown</div>
                    <div class="stat-value text-danger">{{ data.portfolio_analytics.max_drawdown_pct }}%</div>
                    <small class="text-secondary">Peak-to-Trough Capital Loss</small>
                </div>
            </div>
        </div>

        <div class="row">
            <!-- Tail Risk Comparison Table -->
            <div class="col-lg-6">
                <div class="card shadow-sm h-100">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>1-Day Tail Risk: VaR vs Expected Shortfall</span>
                        <span class="badge bg-secondary">Confidence: 95%</span>
                    </div>
                    <div class="card-body">
                        <table class="table table-dark table-hover mb-0">
                            <thead>
                                <tr>
                                    <th>Methodology</th>
                                    <th class="text-end">Value at Risk (VaR)</th>
                                    <th class="text-end">Expected Shortfall (ES)</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td><strong>Historical Simulation</strong></td>
                                    <td class="text-end text-warning">{{ data.value_at_risk_and_expected_shortfall['95pct'].historical.var_pct }}%</td>
                                    <td class="text-end text-danger">{{ data.value_at_risk_and_expected_shortfall['95pct'].historical.expected_shortfall_pct }}%</td>
                                </tr>
                                <tr>
                                    <td><strong>Parametric Gaussian</strong></td>
                                    <td class="text-end text-warning">{{ data.value_at_risk_and_expected_shortfall['95pct'].parametric_gaussian.var_pct }}%</td>
                                    <td class="text-end text-danger">{{ data.value_at_risk_and_expected_shortfall['95pct'].parametric_gaussian.expected_shortfall_pct }}%</td>
                                </tr>
                                <tr>
                                    <td><strong>Monte Carlo Simulation</strong></td>
                                    <td class="text-end text-warning">{{ data.value_at_risk_and_expected_shortfall['95pct'].monte_carlo.var_pct }}%</td>
                                    <td class="text-end text-danger">{{ data.value_at_risk_and_expected_shortfall['95pct'].monte_carlo.expected_shortfall_pct }}%</td>
                                </tr>
                            </tbody>
                        </table>
                        <div class="mt-3 p-3 bg-black rounded text-secondary small">
                            <em>Note: VaR defines the loss threshold, while Expected Shortfall (CVaR) quantifies the average loss conditional on entering the tail beyond that threshold.</em>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Rolling Kupiec Backtest Results -->
            <div class="col-lg-6">
                <div class="card shadow-sm h-100">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>Rolling Kupiec POF Backtesting</span>
                        <span class="badge bg-success">Unconditional Coverage</span>
                    </div>
                    <div class="card-body">
                        <table class="table table-dark table-hover mb-0">
                            <thead>
                                <tr>
                                    <th>Model</th>
                                    <th class="text-center">Forecasts / Exceptions</th>
                                    <th class="text-center">Observed (Expected)</th>
                                    <th class="text-center">LR Stat (p-val)</th>
                                    <th class="text-end">Verdict</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for m_name, m_data in data.rolling_kupiec_backtesting.items() %}
                                <tr>
                                    <td><strong>{{ m_name.capitalize() }}</strong></td>
                                    <td class="text-center">{{ m_data.number_of_forecasts }} / {{ m_data.number_of_exceptions }}</td>
                                    <td class="text-center">{{ m_data.observed_exception_rate_pct }}% ({{ m_data.expected_exception_rate_pct }}%)</td>
                                    <td class="text-center">{{ m_data.kupiec_lr_statistic }} (p={{ m_data.kupiec_p_value }})</td>
                                    <td class="text-end">
                                        {% if m_data.unconditional_coverage_verdict == 'PASS' %}
                                        <span class="badge badge-pass">PASS</span>
                                        {% else %}
                                        <span class="badge badge-fail">FAIL</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        <div class="mt-3 p-3 bg-black rounded text-secondary small">
                            <em>Kupiec test evaluates unconditional coverage: whether observed frequency of exceptions is statistically consistent with the null hypothesis at &alpha;=0.05.</em>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Stress Testing Scenarios Table -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card shadow-sm">
                    <div class="card-header">
                        <span>Adverse Macro & NEPSE Structural Stress Scenarios</span>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-dark table-hover">
                                <thead>
                                    <tr>
                                        <th>Stress Scenario</th>
                                        <th>Description</th>
                                        <th class="text-end">Stressed VaR</th>
                                        <th class="text-end">&Delta; VaR (%)</th>
                                        <th class="text-end">Stressed ES</th>
                                        <th class="text-end">&Delta; ES (%)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for s_name, s_data in data.stress_testing.scenarios.items() %}
                                    <tr>
                                        <td><strong>{{ s_name }}</strong></td>
                                        <td class="text-secondary small">{{ s_data.description }}</td>
                                        <td class="text-end text-warning">{{ s_data.stressed_var_pct }}%</td>
                                        <td class="text-end text-danger">+{{ s_data.delta_var_pct }}%</td>
                                        <td class="text-end text-warning">{{ s_data.stressed_expected_shortfall_pct }}%</td>
                                        <td class="text-end text-danger">+{{ s_data.delta_expected_shortfall_pct }}%</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Portfolio Asset Weights -->
        <div class="row mt-2">
            <div class="col-12 text-secondary small">
                <strong>Portfolio Holdings:</strong>
                {% for sym, w in data.weights.items() %}
                <span class="badge bg-secondary me-1">{{ sym }}: {{ (w * 100)|round(1) }}%</span>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
"""


def load_nepse_portfolio_data() -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Loads historical data for NEPSE blue-chip universe or generates calibrated sample."""
    tickers = ["NABIL", "GBIME", "CHCL", "SHIVM", "CIT"]
    weights = {"NABIL": 0.25, "GBIME": 0.20, "CHCL": 0.20, "SHIVM": 0.15, "CIT": 0.20}

    if PARQUET_PATH.exists():
        try:
            logger.info(f"Loading NEPSE master parquet from {PARQUET_PATH}...")
            df_raw = pd.read_parquet(
                PARQUET_PATH,
                columns=["date", "ticker", "close"],
                filters=[("ticker", "in", tickers)],
            )
            df_pivot = df_raw.pivot(index="date", columns="ticker", values="close").sort_index()
            returns_df = df_pivot.pct_change().dropna()
            if len(returns_df) > 100:
                logger.info(f"Loaded {len(returns_df)} daily return bars from NEPSE Lakehouse.")
                return returns_df, weights
        except Exception as e:
            logger.warning(f"Could not load parquet: {e}. Falling back to calibrated simulator.")

    # Synthetic fallback calibrated to NEPSE parameters
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=320)
    data = {
        "NABIL": np.random.normal(0.0006, 0.015, 320),
        "GBIME": np.random.normal(0.0004, 0.016, 320),
        "CHCL": np.random.normal(0.0008, 0.024, 320),
        "SHIVM": np.random.normal(0.0005, 0.022, 320),
        "CIT": np.random.normal(0.0007, 0.014, 320),
    }
    return pd.DataFrame(data, index=dates), weights


@app.route("/")
def dashboard():
    """Interactive Flask dashboard view."""
    returns_df, weights = load_nepse_portfolio_data()
    results = lab.run_full_analysis(returns_df, weights, estimation_window=100)
    return render_template_string(HTML_TEMPLATE, data=results)


@app.route("/api/summary", methods=["GET"])
def api_summary():
    """Returns full portfolio analytics and tail risk summary as JSON."""
    returns_df, weights = load_nepse_portfolio_data()
    results = lab.run_full_analysis(returns_df, weights, estimation_window=100)
    return jsonify(results)


@app.route("/api/stress-test", methods=["GET", "POST"])
def api_stress_test():
    """Returns stress-testing analysis."""
    returns_df, weights = load_nepse_portfolio_data()
    port_ret = lab.analytics.compute_portfolio_returns(returns_df, weights)
    res = lab.stress_engine.run_stress_scenarios(port_ret, confidence_level=0.95)
    return jsonify(res)


@app.route("/api/backtest", methods=["GET"])
def api_backtest():
    """Returns rolling Kupiec backtesting results."""
    returns_df, weights = load_nepse_portfolio_data()
    port_ret = lab.analytics.compute_portfolio_returns(returns_df, weights)
    res = {}
    for m in ["historical", "parametric", "monte_carlo"]:
        res[m] = lab.backtester.run_rolling_backtest(
            port_ret, estimation_window=100, confidence_level=0.95, method=m
        )
    return jsonify(res)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    logger.info(f"Starting TITAN COCKPIT Sovereign Engine on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
