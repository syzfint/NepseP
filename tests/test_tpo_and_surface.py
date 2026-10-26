"""
tests/test_tpo_and_surface.py

Unit and integration test verifying:
1. 30-Minute Auction Bracketing & TPO Profile calculations (POC, VAH, VAL, Tails).
2. 2D Gaussian Kernel Smoothing & Dual Optimization Surface generation.
3. API endpoints /api/tpo/{symbol} and /api/surface/optimization.
4. Screen S04 TPO & Footprint DOM component integration.
5. Screen S10 MT5 Strategy Tester & Dual-Surface DOM component integration.
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scripts" / "02_modeling_and_calculations"))
sys.path.insert(0, str(BASE_DIR / "scripts" / "04_backtesting" / "sovereign_alpha_miner"))

from tpo_profile_calculator import TPOProfileEngine
from surface_smoother import gaussian_smooth_2d, generate_optimization_landscape
from apex_engine.main import app

client = TestClient(app)


def test_tpo_profile_calculation():
    engine = TPOProfileEngine(value_area_pct=0.70)
    profile = engine.compute_profile_from_trades("NICA", [])
    assert profile["symbol"] == "NICA"
    assert profile["poc_price"] > 0
    assert profile["vah_price"] >= profile["val_price"]
    assert len(profile["ladder"]) > 0
    assert "buying_tail" in profile
    assert "selling_tail" in profile


def test_surface_smoother_landscape():
    landscape = generate_optimization_landscape()
    assert landscape["x_param"] == "InpFastEMA"
    assert landscape["y_param"] == "InpSlowEMA"
    assert len(landscape["raw_surface"]) == 25
    assert len(landscape["smoothed_surface"]) == 25
    assert landscape["global_peak"]["smoothed_profit_factor"] > 1.8


def test_tpo_and_surface_api_routes():
    res_tpo = client.get("/api/tpo/NICA")
    assert res_tpo.status_code == 200
    data_tpo = res_tpo.json()
    assert "poc_price" in data_tpo

    res_surf = client.get("/api/surface/optimization")
    assert res_surf.status_code == 200
    data_surf = res_surf.json()
    assert "smoothed_surface" in data_surf


def test_screen_s04_tpo_dom_integration():
    res = client.get("/cockpit/ofi-depth")
    assert res.status_code == 200
    html = res.text
    assert "TPO MARKET PROFILE & FOOTPRINT" in html
    assert "tpo-view-container" in html
    assert "tpo-vah" in html
    assert "tpo-poc" in html
    assert "tpo-val" in html


def test_screen_s10_mt5_strategy_tester_dom_integration():
    res = client.get("/cockpit/merkle-lakehouse")
    assert res.status_code == 200
    html = res.text
    assert "OPTIMIZATION SURFACE (GENETIC ALGORITHM)" in html
    assert "Dual Surface (Raw vs Smoothed)" in html
    assert "equity-curve-canvas" in html
    assert "Backtest Statistics (Pass 143 Sweet Spot)" in html
    assert "Genetic Algorithm" in html
