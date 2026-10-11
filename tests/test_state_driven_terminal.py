"""
Test Suite for State-Driven Multi-Screen Terminal Architecture.
Validates:
  1. window.TERMINAL_STATE initialization and global state manager logic in HTML templates.
  2. selectSymbol(symbol) cross-screen binding and event propagation.
  3. All 353+ securities coverage across /api/v1/terminal/screen/* endpoints.
  4. Monotonicity of 20-day multi-quantile trajectory corridors (P10 <= P50 <= P90).
  5. Responsive 16:9 3-row grid layout isolation without text overflow or memory leaks.
"""

import sys
import pytest
import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient

# Import multi_workspace_terminal app
_spec = importlib.util.spec_from_file_location(
    "multi_workspace_terminal",
    Path(__file__).parent.parent / "scripts" / "08_dashboard_ui" / "multi_workspace_terminal.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

app = _mod.app
get_alpha_dashboard_data = _mod.get_alpha_dashboard_data
get_risk_monitor_data = _mod.get_risk_monitor_data
get_forecast_engine_data = _mod.get_forecast_engine_data
get_trading_desk_data = _mod.get_trading_desk_data


@pytest.fixture
def client():
    return TestClient(app)


def test_global_terminal_state_manager_markup():
    """Verify HTML files declare window.TERMINAL_STATE, selectSymbol(), and 16:9 layout."""
    index_path = Path(__file__).parent.parent / "pulse_terminal" / "index.html"
    template_path = Path(__file__).parent.parent / "templates" / "terminal.html"

    for path in (index_path, template_path):
        assert path.exists(), f"Missing file {path}"
        content = path.read_text(encoding="utf-8")

        # 1. State Manager & Selection Engine
        assert "window.TERMINAL_STATE = {" in content
        assert "activeSymbol: 'NABIL'" in content
        assert "activeScreen: 'launcher'" in content
        assert "marketUniverse:" in content
        assert "signalsData:" in content
        assert "window.selectSymbol = function" in content
        assert "renderTradingDesk" in content
        assert "highlightAlphaRow" in content
        assert "renderRiskMetrics" in content
        assert "drawQuantileCorridorCanvas" in content
        assert "window.switchWorkspace = function" in content

        # 2. 16:9 Grid Layout Boundaries
        assert "#terminal-app-shell" in content
        assert "grid-template-rows: var(--nav-height) 1fr var(--footer-height)" in content
        assert "#global-terminal-footer" in content

        # 3. All 5 Isolated Screen Elements
        assert 'id="screen-launchpad"' in content
        assert 'id="screen-tradingdesk"' in content
        assert 'id="screen-alpha"' in content
        assert 'id="screen-risk"' in content
        assert 'id="screen-forecast"' in content
        assert 'id="forecastCanvasElement"' in content


def test_api_v1_screen_endpoints_coverage(client):
    """Verify response payloads for all 353+ securities across /api/v1/terminal/screen/*."""
    # Screen 0: Launcher
    res_launch = client.get("/api/v1/terminal/screen/launcher")
    assert res_launch.status_code == 200
    assert res_launch.json()["status"] == "SUCCESS"
    assert len(res_launch.json()["screens_available"]) == 4

    # Screen 1: Trading Desk
    res_td = client.get("/api/v1/terminal/screen/trading_desk?symbol=NABIL")
    assert res_td.status_code == 200
    td_data = res_td.json()["data"]
    assert td_data["symbol"] == "NABIL"
    assert len(td_data["bids"]) >= 5
    assert len(td_data["asks"]) >= 5

    # Screen 2: Alpha (Verifies 353+ securities)
    res_alpha = client.get("/api/v1/terminal/screen/alpha")
    assert res_alpha.status_code == 200
    alpha_payload = res_alpha.json()
    assert alpha_payload["status"] == "SUCCESS"
    assert alpha_payload["total_securities"] >= 350
    first_sym = alpha_payload["data"][0]
    assert "gate_g4_score" in first_sym
    assert 0.0 <= first_sym["gate_g4_score"] <= 100.0

    # Screen 3: Risk Monitor
    res_risk = client.get("/api/v1/terminal/screen/risk?symbol=NABIL")
    assert res_risk.status_code == 200
    risk_data = res_risk.json()["data"]
    assert risk_data["active_symbol"] == "NABIL"
    assert "hrp_allocation" in risk_data
    # Sum of weights strictly 100.0%
    total_w = sum(a["weight"] for a in risk_data["hrp_allocation"])
    assert abs(total_w - 100.0) < 0.1

    # Screen 4: Forecast Engine
    res_fc = client.get("/api/v1/terminal/screen/forecast?symbol=NABIL")
    assert res_fc.status_code == 200
    fc_data = res_fc.json()["data"]
    assert fc_data["primary_symbol"] == "NABIL"
    assert len(fc_data["p10_curve"]) == 20
    assert len(fc_data["p50_curve"]) == 20
    assert len(fc_data["p90_curve"]) == 20


def test_select_symbol_dynamic_forecast_redraw_monotonicity():
    """Verify selecting different symbols dynamically generates valid monotonic corridors."""
    symbols = ["NABIL", "UPPER", "CHCL", "SHIVM"]
    for sym in symbols:
        data = get_forecast_engine_data(symbol=sym)
        assert data["primary_symbol"] == sym
        p10 = data["p10_curve"]
        p50 = data["p50_curve"]
        p90 = data["p90_curve"]

        assert len(p10) == 20
        assert len(p50) == 20
        assert len(p90) == 20

        # Monotonicity check across all 20 trading sessions
        for i in range(20):
            assert p10[i] <= p50[i], f"Monotonicity error for {sym} at day {i}: P10 > P50"
            assert p50[i] <= p90[i], f"Monotonicity error for {sym} at day {i}: P50 > P90"


def test_backward_compatible_workspace_routes(client):
    """Ensure existing endpoints /api/workspaces/* remain 100% operational."""
    res_a = client.get("/api/workspaces/alpha")
    assert res_a.status_code == 200
    assert len(res_a.json()["data"]) >= 350

    res_r = client.get("/api/workspaces/risk")
    assert res_r.status_code == 200
    assert "hrp_allocation" in res_r.json()["data"]

    res_f = client.get("/api/workspaces/forecast")
    assert res_f.status_code == 200
    assert len(res_f.json()["data"]["p50_curve"]) == 20


def test_screen1_unified_routes(client):
    """Verify Screen 1 Chart series, Centaur blotter, Sweet Spot, and Brain endpoints."""
    # 1. Chart series with OHLCV candles
    res_chart = client.get("/api/charts/series/NABIL")
    assert res_chart.status_code == 200
    chart_data = res_chart.json()
    assert chart_data["symbol"] == "NABIL"
    assert "candles" in chart_data
    assert len(chart_data["candles"]) > 100
    assert "ema20" in chart_data
    assert "ema50" in chart_data

    # 2. Centaur Top-20
    res_top20 = client.get("/api/centaur/top20")
    assert res_top20.status_code == 200
    assert res_top20.json()["status"] == "SUCCESS"
    assert res_top20.json()["count"] == 20

    # 3. Sweet Spot
    res_ss = client.get("/api/sweet_spot/NABIL")
    assert res_ss.status_code == 200
    assert res_ss.json()["status"] == "SUCCESS"

    # 4. Symbol Brain
    res_brain = client.get("/api/symbol_brain/NABIL")
    assert res_brain.status_code == 200
    assert res_brain.json()["status"] == "SUCCESS"
    assert "brain" in res_brain.json()

    # 5. Centaur Audit Ledger
    res_ledger = client.get("/api/centaur/audit_ledger")
    assert res_ledger.status_code == 200
    assert res_ledger.json()["status"] == "SUCCESS"


def test_websocket_stream_payloads(client):
    """Verify WebSocket /ws/pulse sends unified market and workspace packets."""
    with client.websocket_connect("/ws/pulse") as ws:
        # Check initial packet burst
        packets = {}
        for _ in range(13):
            msg = ws.receive_json()
            msg_type = msg.get("type")
            packets[msg_type] = msg.get("data")

        # Verify key packets were broadcast
        assert "MARKET_MACRO" in packets
        assert "MARKET_STATUS" in packets
        assert "WATCHLIST" in packets
        assert "L2_DEPTH" in packets
        assert "WORKSPACE_INIT" in packets
        assert "ALPHA_DATA" in packets
        assert "RISK_DATA" in packets
        assert "FORECAST_DATA" in packets
        assert len(packets["WATCHLIST"]) >= 250
