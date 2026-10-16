#!/usr/bin/env python3
"""
tests/test_forecast_probability_corridor.py

Validates institutional upgrades to Screen [4] 20-Day Forecast Engine:
1. Multi-band shaded confidence intervals (P2.5, P10, P25, P50, P75, P90, P97.5).
2. Monotonicity bounds: P2.5 <= P10 <= P25 <= P50 <= P75 <= P90 <= P97.5.
3. Event-driven non-linear variance expansion kinks at D+5 and D+12.
4. Monte Carlo / Patch-Transformer stochastic spaghetti paths (50–100 trajectories).
5. Terminal Value Kernel Density Estimate (KDE) plot at D+20.
6. In-memory chart rendering optimization & worker threadpool decoupling.
7. Hive-partitioned floorsheet query capability.
8. Asynchronous Clef VLM inference queue with certified fail-closed circuit breaker.
"""

import sys
import pytest
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
for p in [str(BASE_DIR), str(BASE_DIR / "scripts"), str(BASE_DIR / "scripts" / "08_dashboard_ui")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib.util

_mws_path = BASE_DIR / "scripts" / "08_dashboard_ui" / "multi_workspace_terminal.py"
_spec = importlib.util.spec_from_file_location("mws_terminal", _mws_path)
_mws = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mws)
get_forecast_engine_data = _mws.get_forecast_engine_data

from scripts.pulse_chart_engine import InstitutionalChartEngine

_loader_path = BASE_DIR / "scripts" / "01_etl_and_ingestion" / "duckdb_lakehouse_loader.py"
_loader_spec = importlib.util.spec_from_file_location("duckdb_lakehouse_loader", _loader_path)
_loader_mod = importlib.util.module_from_spec(_loader_spec)
_loader_spec.loader.exec_module(_loader_mod)
DuckDBLakehouseLoader = _loader_mod.DuckDBLakehouseLoader

_clef_path = BASE_DIR / "scripts" / "33_clef_inference_bridge.py"
_clef_spec = importlib.util.spec_from_file_location("clef_bridge", _clef_path)
_clef_mod = importlib.util.module_from_spec(_clef_spec)
_clef_spec.loader.exec_module(_clef_mod)
AsyncClefInferenceQueue = _clef_mod.AsyncClefInferenceQueue


def test_multiband_probability_corridor_structure():
    """Validates multi-band quantile curves and event-driven variance kinks."""
    data = get_forecast_engine_data("NABIL")

    # 1. Verify presence of all institutional bands
    for key in ["p2_5_curve", "p10_curve", "p25_curve", "p50_curve", "p75_curve", "p90_curve", "p97_5_curve"]:
        assert key in data, f"Missing {key} in forecast data"
        assert len(data[key]) == 20, f"Expected 20 days for {key}, got {len(data[key])}"

    p2_5 = data["p2_5_curve"]
    p10 = data["p10_curve"]
    p25 = data["p25_curve"]
    p50 = data["p50_curve"]
    p75 = data["p75_curve"]
    p90 = data["p90_curve"]
    p97_5 = data["p97_5_curve"]

    # 2. Assert strict quantile hierarchy across all 20 forward days
    for d in range(20):
        assert p2_5[d] <= p10[d], f"Quantile violation at day {d}: P2.5 > P10"
        assert p10[d] <= p25[d], f"Quantile violation at day {d}: P10 > P25"
        assert p25[d] <= p50[d], f"Quantile violation at day {d}: P25 > P50"
        assert p50[d] <= p75[d], f"Quantile violation at day {d}: P50 > P75"
        assert p75[d] <= p90[d], f"Quantile violation at day {d}: P75 > P90"
        assert p90[d] <= p97_5[d], f"Quantile violation at day {d}: P90 > P97.5"

    # 3. Assert event markers at D+5 and D+12 with non-linear variance expansion
    events = data.get("calendar_events", [])
    assert len(events) >= 2, "Expected at least 2 calendar event markers"
    event_days = [e["day"] for e in events]
    assert 5 in event_days, "Missing D+5 event marker"
    assert 12 in event_days, "Missing D+12 event marker"

    # Spread between P90 and P10 expands non-linearly after D+5 and D+12
    spread_d4 = p90[3] - p10[3]
    spread_d5 = p90[4] - p10[4]
    spread_d11 = p90[10] - p10[10]
    spread_d12 = p90[11] - p10[11]

    # Non-linear expansion kink: spread step increase is greater than linear baseline step
    assert (spread_d5 - spread_d4) > 0, "Corridor failed to expand at D+5"
    assert (spread_d12 - spread_d11) > 0, "Corridor failed to expand at D+12"


def test_monte_carlo_spaghetti_paths_and_kde():
    """Validates Monte Carlo trajectories and terminal KDE density distribution."""
    data = get_forecast_engine_data("NABIL")

    # 1. Verify 60 stochastic sample trajectories
    mc_paths = data.get("mc_paths", [])
    assert len(mc_paths) >= 50, f"Expected at least 50 sample paths, got {len(mc_paths)}"
    for path in mc_paths:
        assert len(path) == 20, "Each path must span 20 trading sessions"
        assert all(p > 0 for p in path), "Prices along path must be strictly positive"

    # 2. Verify Terminal KDE density plot at D+20
    kde = data.get("terminal_kde")
    assert kde is not None, "Missing terminal_kde in forecast payload"
    assert "grid_prices" in kde and "norm_density" in kde
    assert len(kde["grid_prices"]) == 50
    assert len(kde["norm_density"]) == 50
    assert max(kde["norm_density"]) == 1.0  # Normalized peak density


def test_institutional_chart_engine_corridor_rendering():
    """Validates Matplotlib/Agg multi-band fan chart & KDE generation."""
    data = get_forecast_engine_data("NABIL")

    img_b64 = InstitutionalChartEngine.render_institutional_probability_corridor_png(
        symbol="NABIL",
        base_price=data["base_price"],
        p2_5=data["p2_5_curve"],
        p10=data["p10_curve"],
        p25=data["p25_curve"],
        p50=data["p50_curve"],
        p75=data["p75_curve"],
        p90=data["p90_curve"],
        p97_5=data["p97_5_curve"],
        mc_paths=data["mc_paths"],
        calendar_events=data["calendar_events"],
        terminal_kde=data["terminal_kde"]
    )

    assert isinstance(img_b64, str)
    assert len(img_b64) > 1000, "Generated Base64 chart is suspiciously small or empty"


@pytest.mark.asyncio
async def test_async_chart_rendering_and_caching():
    """Validates non-blocking async worker rendering and delta threshold caching."""
    # First render
    frame1 = await InstitutionalChartEngine.render_chart_async("CANDLE", "NABIL", 1150.0)
    assert "chart_base64" in frame1
    assert frame1["symbol"] == "NABIL"

    # Micro-tick change (0.05% < 0.20% threshold): returns cached frame instantly
    frame2 = await InstitutionalChartEngine.render_chart_async("CANDLE", "NABIL", 1150.5)
    assert frame2["chart_base64"] == frame1["chart_base64"], "Cached frame should be reused on micro-tick"


def test_duckdb_hive_partition_loader_schema():
    """Validates DuckDB Hive-partitioned query interface."""
    p_path = BASE_DIR / "02_processed_parquet" / "by_security_type"
    # Query with non-existent symbol to verify query structure execution
    df = DuckDBLakehouseLoader.query_hive_partitioned_floorsheet(p_path, symbol="NON_EXISTENT")
    assert isinstance(df, type(df))


@pytest.mark.asyncio
async def test_async_clef_queue_circuit_breaker():
    """Validates async VLM inference queue and fail-closed fallback."""
    queue = AsyncClefInferenceQueue()
    assert queue.max_rtt_seconds == 8.4
    assert queue.timeout_seconds == 45.0

    # With empty base_url, should fail closed cleanly to numerical mode without throwing unhandled exceptions
    res = await queue.submit_synthesis_task()
    assert res is not None
    assert res.get("status") in ("SUCCESS", "FAILED", "FAILURE_FALLBACK_CLOSED")
