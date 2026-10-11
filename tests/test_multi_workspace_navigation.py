"""
Unit and integration tests for Multi-Workspace Launch Pad & 4-Screen Navigation.
Validates:
  1. Workspace API routes (/api/workspaces/alpha, /api/workspaces/risk, /api/workspaces/forecast).
  2. Data integrity across Screen [2] Alpha metrics (Gate G4 scores in 0-100%, Hawkes flags).
  3. Schur-RA-HRP allocation matrix weights sum strictly to 100.0%.
  4. Forecast engine 20-day multi-quantile trajectory monotonicity (P10 <= P50 <= P90).
"""

import sys
import pytest
import importlib.util
from pathlib import Path

# Dynamic import for multi_workspace_terminal
_spec = importlib.util.spec_from_file_location(
    "multi_workspace_terminal",
    Path(__file__).parent.parent / "scripts" / "08_dashboard_ui" / "multi_workspace_terminal.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

get_alpha_dashboard_data = _mod.get_alpha_dashboard_data
get_risk_monitor_data = _mod.get_risk_monitor_data
get_forecast_engine_data = _mod.get_forecast_engine_data


def test_alpha_dashboard_data_structure():
    """Verify Screen [2] Alpha Dashboard returns valid ranked securities with Gate G4 scores."""
    data = get_alpha_dashboard_data()
    assert len(data) > 0, "Alpha dashboard dataset is empty!"
    
    first = data[0]
    assert "symbol" in first
    assert "gate_g4_score" in first
    assert "hawkes_flag" in first
    assert "status" in first
    
    # Assert Gate G4 confidence bounds [0, 100]
    for row in data[:20]:
        score = row["gate_g4_score"]
        assert 0.0 <= score <= 100.0, f"Score out of bounds: {score}"
        assert row["status"] in ("BUY", "SELL", "NEUTRAL")


def test_risk_monitor_data_structure():
    """Verify Screen [3] Risk Monitor Schur-RA-HRP weights, VaR metrics, and HHI broker tables."""
    data = get_risk_monitor_data()
    assert "hrp_allocation" in data
    assert "broker_hhi" in data
    assert "cdsc_shield" in data
    assert "portfolio_var_95" in data

    # Verify HRP weights sum to 100%
    alloc = data["hrp_allocation"]
    total_w = sum(a["weight"] for a in alloc)
    assert abs(total_w - 100.0) < 0.1, f"HRP weights sum {total_w} != 100.0%"

    # Verify broker HHI table has top brokers (58, 45, 34, etc.)
    brokers = [b["broker_id"] for b in data["broker_hhi"]]
    assert "58" in brokers, "Broker 58 missing from HHI concentration table"


def test_forecast_engine_data_structure():
    """Verify Screen [4] 20D Forecast Engine P10/P50/P90 quantile monotonicity."""
    data = get_forecast_engine_data()
    assert "ranked_forecasts" in data
    assert "corridor_dates" in data
    assert "p10_curve" in data
    assert "p50_curve" in data
    assert "p90_curve" in data

    p10 = data["p10_curve"]
    p50 = data["p50_curve"]
    p90 = data["p90_curve"]

    assert len(p10) == 20
    assert len(p50) == 20
    assert len(p90) == 20

    # Assert P10 <= P50 <= P90 for all 20 sessions
    for i in range(20):
        assert p10[i] <= p50[i], f"Quantile violation at day {i}: P10 ({p10[i]}) > P50 ({p50[i]})"
        assert p50[i] <= p90[i], f"Quantile violation at day {i}: P50 ({p50[i]}) > P90 ({p90[i]})"


def test_terminal_html_contains_launchpad_and_all_screens():
    """Verify pulse_terminal/index.html includes all 4 screens and the launch pad."""
    html_path = Path(__file__).parent.parent / "pulse_terminal" / "index.html"
    assert html_path.exists(), f"Missing {html_path}"

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'id="screen-launchpad"' in content, "Missing Screen 0: Launch Pad"
    assert 'id="screen-tradingdesk"' in content, "Missing Screen 1: Trading Desk"
    assert 'id="screen-alpha"' in content, "Missing Screen 2: Alpha Dashboard"
    assert 'id="screen-risk"' in content, "Missing Screen 3: Risk Monitor"
    assert 'id="screen-forecast"' in content, "Missing Screen 4: 20D Forecast Engine"
    assert 'id="workspace-navbar"' in content, "Missing persistent workspace navbar"
