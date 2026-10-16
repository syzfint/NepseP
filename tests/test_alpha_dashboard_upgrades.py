"""
Unit and integration tests for Institutional Alpha Dashboard upgrades (Screen 2).
Validates:
  1. Multi-Level Deep OFI (K=5 levels, decay weights w_k = exp(-0.4*(k-1))) & Cross-Sectional Z-Score.
  2. Hawkes Self-Excitation Branching Ratio (n = alpha / beta) & sweep regime transitions.
  3. CPCV Triple-Barrier Probability Distribution (P(Target), P(Stop), P(Time)) & Deflated Sharpe Ratio (DSR).
  4. SHAP 5-Axis Non-Linear Feature Attribution Radar & Exponential Promoter Lock-In Decay Surface.
  5. Almgren-Chriss Optimal Execution Vector (slices, TWAP window, half-life tau, impact bps).
"""

import math
import numpy as np
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


def test_multi_depth_ofi_vector_and_cross_sectional_z_score():
    """Verify 5-level depth vector, queue distance decay weighting, and cross-sectional normalization."""
    data = get_alpha_dashboard_data()
    assert len(data) > 0, "Universe is empty"

    gamma = 0.4
    weights = [math.exp(-gamma * k) for k in range(5)]
    w_sum = sum(weights)

    z_scores = []
    for item in data:
        assert "ofi_levels" in item
        assert "ofi_k5" in item
        assert "ofi_z_score" in item

        levels = item["ofi_levels"]
        assert len(levels) == 5, f"Expected 5 OFI levels, got {len(levels)}"

        # Verify composite weighted OFI formula
        expected_k5 = round(sum(weights[k] * levels[k] for k in range(5)) / w_sum, 3)
        assert abs(item["ofi_k5"] - expected_k5) < 1e-2, (
            f"OFI K=5 calculation mismatch: {item['ofi_k5']} vs expected {expected_k5}"
        )

        z_scores.append(item["ofi_z_score"])
        assert -3.5 <= item["ofi_z_score"] <= 3.5, f"Z-score out of bounds: {item['ofi_z_score']}"

    # Cross-sectional statistical properties across the full universe (mean ~ 0, std ~ 1)
    mean_z = np.mean(z_scores)
    std_z = np.std(z_scores)
    assert abs(mean_z) < 0.25, f"Cross-sectional mean z-score {mean_z} diverges from 0"
    assert 0.7 <= std_z <= 1.3, f"Cross-sectional std z-score {std_z} diverges from 1"


def test_hawkes_branching_ratio_and_regime_classification():
    """Verify dynamic branching ratio n = alpha/beta and subcritical/near-critical regime tagging."""
    data = get_alpha_dashboard_data()

    for item in data:
        assert "hawkes_branching_ratio" in item
        assert "hawkes_intensity" in item
        assert "hawkes_regime" in item

        n = item["hawkes_branching_ratio"]
        # Subcritical stability condition
        assert 0.0 < n < 1.0, f"Branching ratio {n} violates stability condition (< 1.0)"

        intensity = item["hawkes_intensity"]
        assert intensity > 0.0, f"Arrival intensity must be positive: {intensity}"

        regime = item["hawkes_regime"]
        assert regime in ("SWEEP", "FEEDBACK", "ORGANIC")

        # Threshold consistency
        if n >= 0.70:
            assert regime == "SWEEP", f"Expected SWEEP regime for n={n}, got {regime}"
        elif n >= 0.50:
            assert regime == "FEEDBACK", f"Expected FEEDBACK regime for n={n}, got {regime}"
        else:
            assert regime == "ORGANIC", f"Expected ORGANIC regime for n={n}, got {regime}"


def test_cpcv_triple_barrier_probabilities_and_deflated_sharpe_ratio():
    """Verify CPCV target/stop/time probabilities sum to 100% and DSR adjusts for backtest overfitting."""
    data = get_alpha_dashboard_data()

    for item in data:
        assert "cpcv_target_prob" in item
        assert "cpcv_stop_prob" in item
        assert "cpcv_time_prob" in item
        assert "cpcv_max_dd" in item
        assert "deflated_sharpe_ratio" in item

        p_tgt = item["cpcv_target_prob"]
        p_stop = item["cpcv_stop_prob"]
        p_time = item["cpcv_time_prob"]

        assert 0.0 <= p_tgt <= 100.0
        assert 0.0 <= p_stop <= 100.0
        assert 0.0 <= p_time <= 100.0

        # Total probability sum must be 100.0%
        prob_sum = p_tgt + p_stop + p_time
        assert abs(prob_sum - 100.0) < 0.2, f"CPCV probabilities sum {prob_sum} != 100.0%"

        # Max drawdown must be negative
        assert item["cpcv_max_dd"] <= 0.0, f"Max expected drawdown must be negative: {item['cpcv_max_dd']}"

        # Deflated Sharpe Ratio bounds [0.0, 1.0]
        dsr = item["deflated_sharpe_ratio"]
        assert 0.0 <= dsr <= 1.0, f"Deflated Sharpe Ratio out of bounds: {dsr}"


def test_shap_radar_attribution_and_exponential_lockin_decay():
    """Verify 5-axis SHAP radar attribution and non-linear promoter lock-in decay surface."""
    data = get_alpha_dashboard_data()

    for item in data:
        assert "shap_radar" in item
        shap = item["shap_radar"]

        required_axes = [
            "alpha_momentum",
            "microstructure_ofi",
            "hawkes_intensity",
            "garch_regime",
            "event_lockin_shield"
        ]
        for axis in required_axes:
            assert axis in shap, f"Missing SHAP axis: {axis}"
            assert -1.0 <= shap[axis] <= 1.0, f"SHAP value {shap[axis]} out of bounds for {axis}"

        # Exponential Lock-in decay surface
        assert "lockin_decay_surface" in item
        surface = item["lockin_decay_surface"]
        assert len(surface) == 8, f"Expected 8 days grid points, got {len(surface)}"

        for pt in surface:
            assert "day" in pt
            assert "price_shock_pct" in pt
            assert pt["price_shock_pct"] <= 0.0, "Lock-in price shock must be negative or zero (dilution impact)"

        # Monotonicity of decay: shock at day 0 should be >= shock at day 30 (more negative / severe)
        shock_d30 = surface[0]["price_shock_pct"]
        shock_d0 = surface[-1]["price_shock_pct"]
        assert shock_d0 <= shock_d30, f"Day 0 shock ({shock_d0}) should be more severe than Day 30 ({shock_d30})"


def test_almgren_chriss_optimal_execution_vector():
    """Verify Almgren-Chriss pre-calculated parameters for Trading Desk order routing."""
    data = get_alpha_dashboard_data()

    for item in data:
        assert "almgren_chriss" in item
        ac = item["almgren_chriss"]

        assert "slices" in ac
        assert "twap_window_min" in ac
        assert "half_life_min" in ac
        assert "impact_bps" in ac
        assert "risk_aversion_lambda" in ac

        assert ac["slices"] >= 1
        assert ac["twap_window_min"] > 0
        assert ac["half_life_min"] > 0
        assert ac["impact_bps"] > 0
        assert ac["risk_aversion_lambda"] > 0
