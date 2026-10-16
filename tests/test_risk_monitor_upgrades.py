"""
Unit and integration tests for Institutional Risk Monitor upgrades (Screen 3).
Validates:
  1. Copula Tail-Dependence & Block-Diagonal Heatmap with Dynamic Linkage Cut.
  2. Broker HHI Hawkes Self-Excitation Velocity & Stealth Iceberg (TWAP/VWAP) Tracking.
  3. Extreme Value Theory (EVT) Peak-Over-Threshold (POT) & Cornish-Fisher Tail Expansion.
  4. Dual-Axis Stress Contingency Grid (5x5 Sensitivity Matrix: Shock vs Liquidity).
"""

import math
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

get_risk_monitor_data = _mod.get_risk_monitor_data


def test_copula_tail_dependence_and_block_diagonal_matrix():
    """Verify copula lower-tail crash matrix, distance metrics, and dendrogram linkage tree."""
    data = get_risk_monitor_data("NABIL")
    
    assert "copula_matrix" in data
    assert "copula_symbols" in data
    assert "copula_distance_matrix" in data
    assert "dendrogram_tree" in data
    
    symbols = data["copula_symbols"]
    n = len(symbols)
    assert n == 7, f"Expected 7 assets in copula cluster, got {n}"
    
    copula_mat = data["copula_matrix"]
    dist_mat = data["copula_distance_matrix"]
    
    assert len(copula_mat) == n
    assert len(dist_mat) == n
    
    for i in range(n):
        assert len(copula_mat[i]) == n
        assert len(dist_mat[i]) == n
        
        # Diagonal assertions
        assert abs(copula_mat[i][i] - 1.0) < 1e-4, f"Diagonal copula must be 1.0, got {copula_mat[i][i]}"
        assert abs(dist_mat[i][i] - 0.0) < 1e-4, f"Diagonal distance must be 0.0, got {dist_mat[i][i]}"
        
        for j in range(n):
            # Symmetry assertion
            assert abs(copula_mat[i][j] - copula_mat[j][i]) < 1e-4, f"Copula matrix asymmetric at ({i},{j})"
            assert abs(dist_mat[i][j] - dist_mat[j][i]) < 1e-4, f"Distance matrix asymmetric at ({i},{j})"
            
            # Value bounds [0, 1]
            assert 0.0 <= copula_mat[i][j] <= 1.0, f"Copula dependence out of bounds [0,1]: {copula_mat[i][j]}"
            
            # Distance formula d_ij = sqrt(1 - lambda_L)
            expected_dist = round(math.sqrt(max(0.0, 1.0 - copula_mat[i][j])), 4)
            assert abs(dist_mat[i][j] - expected_dist) < 1e-3, f"Distance formula mismatch at ({i},{j})"

    # Dendrogram structure
    tree = data["dendrogram_tree"]
    assert "leaves" in tree
    assert tree["leaves"] == symbols
    assert "default_cut_height" in tree
    assert 0.1 <= tree["default_cut_height"] <= 0.9
    
    clusters = tree["clusters_at_cut"]
    assert len(clusters) >= 2
    total_cluster_w = sum(c["weight"] for c in clusters)
    assert abs(total_cluster_w - 100.0) < 0.2, f"Cluster weights sum to {total_cluster_w} != 100%"


def test_broker_hawkes_velocity_and_stealth_iceberg_tracking():
    """Verify Hawkes arrival intensity, branching ratio stability, and iceberg detection."""
    data = get_risk_monitor_data("NABIL")
    assert "broker_hhi" in data
    
    brokers = data["broker_hhi"]
    assert len(brokers) >= 4, f"Expected at least 4 top brokers, got {len(brokers)}"
    
    b58 = next((b for b in brokers if b["broker_id"] == "58"), None)
    assert b58 is not None, "Broker 58 Naasa Securities must be present"
    assert b58["action"] == "ACCUMULATING"
    
    for b in brokers:
        assert "hawkes_intensity" in b
        assert "hawkes_baseline_mu" in b
        assert "branching_ratio" in b
        assert "stealth_iceberg_index" in b
        assert "buyer_volume_hist" in b
        assert "seller_volume_hist" in b
        assert "flow_status" in b
        
        # Hawkes intensity >= baseline mu
        assert b["hawkes_intensity"] >= b["hawkes_baseline_mu"], "Hawkes intensity must exceed baseline arrival rate"
        
        # Branching ratio eta < 1.0 (subcritical, non-explosive process)
        assert 0.0 < b["branching_ratio"] < 1.0, f"Branching ratio {b['branching_ratio']} violates subcritical condition (< 1.0)"
        
        # Micro-histogram lengths
        assert len(b["buyer_volume_hist"]) == 10
        assert len(b["seller_volume_hist"]) == 10
        assert all(v >= 0 for v in b["buyer_volume_hist"])
        assert all(v >= 0 for v in b["seller_volume_hist"])
        
        # Valid flow status
        assert b["flow_status"] in (
            "AGGRESSIVE_BUYER_SWEEP",
            "AGGRESSIVE_SELLER_DUMP",
            "BALANCED_TWO_WAY",
            "PASSIVE_PROVISION"
        )

    # Broker 58 iceberg verification (stealth index > 2.5 flags iceberg TWAP)
    assert b58["stealth_iceberg_index"] >= 2.5
    assert "ICEBERG" in b58["stealth_flag"]


def test_extreme_value_theory_and_cornish_fisher_expansion():
    """Verify EVT GPD tail parameters, Cornish-Fisher expansion, and density points."""
    data = get_risk_monitor_data("NABIL")
    assert "evt_var_data" in data
    
    evt = data["evt_var_data"]
    
    # Skewness is negative (left tail crash risk) and excess kurtosis > 3
    assert evt["empirical_skewness"] < 0.0, "Expected negative skewness for NEPSE returns"
    assert evt["empirical_kurtosis"] > 3.0, "Expected fat-tailed excess kurtosis > 3"
    
    # Cornish-Fisher quantile z_CF must be more negative than Gaussian z_95 (-1.6449)
    assert evt["cornish_fisher_z95"] < evt["gaussian_z95"], (
        f"Cornish-Fisher z ({evt['cornish_fisher_z95']}) should be more extreme than Gaussian ({evt['gaussian_z95']})"
    )
    
    # Cornish-Fisher VaR must reflect greater loss than Gaussian VaR
    assert evt["var_95_cornish_fisher"] < evt["var_95_gaussian"], (
        f"CF VaR ({evt['var_95_cornish_fisher']}%) should be worse than Gaussian VaR ({evt['var_95_gaussian']}%)"
    )
    
    # CVaR (Expected Shortfall) must be worse than VaR
    assert evt["cvar_95"] < evt["var_95"], (
        f"CVaR 95% ({evt['cvar_95']}%) must be more severe than VaR 95% ({evt['var_95']}%)"
    )
    
    # GPD parameters
    assert evt["gpd_shape_xi"] > 0.0, "GPD shape parameter xi must be positive for heavy-tailed returns"
    assert evt["gpd_scale_beta"] > 0.0, "GPD scale parameter beta must be strictly positive"
    assert evt["gpd_threshold_u"] < 0.0, "EVT POT threshold u must be in the negative loss domain"
    
    # Density curve integrity
    density = evt["density_curve"]
    assert len(density) == 75, f"Expected 75 density curve points, got {len(density)}"
    for pt in density:
        assert "return_pct" in pt
        assert "density" in pt
        assert pt["density"] >= 0.0, f"Density cannot be negative: {pt['density']}"


def test_dual_axis_stress_contingency_grid():
    """Verify 5x5 stress matrix: Index Shocks (-2% to -10%) vs Liquidity Contractions (10% to 50%)."""
    data = get_risk_monitor_data("NABIL")
    assert "stress_contingency_grid" in data
    
    grid = data["stress_contingency_grid"]
    assert len(grid) == 5, f"Expected 5 shock rows, got {len(grid)}"
    
    expected_shocks = [-2.0, -4.0, -6.0, -8.0, -10.0]
    expected_liqs = [10.0, 20.0, 30.0, 40.0, 50.0]
    
    for r_idx, row in enumerate(grid):
        assert len(row) == 5, f"Expected 5 liquidity columns at row {r_idx}, got {len(row)}"
        for c_idx, cell in enumerate(row):
            assert cell["index_shock_pct"] == expected_shocks[r_idx]
            assert cell["liquidity_drop_pct"] == expected_liqs[c_idx]
            
            dd = cell["drawdown_pct"]
            cap = cell["capital_preserved_pct"]
            
            # Capital preservation identity
            assert abs((cap - (100.0 + dd))) < 1e-2, f"Capital preservation formula mismatch in cell ({r_idx},{c_idx})"
            assert cell["risk_tier"] in ("MANAGED", "ELEVATED", "CRITICAL")
            
            # Severe stress verification
            if expected_shocks[r_idx] <= -8.0 or (expected_shocks[r_idx] <= -6.0 and expected_liqs[c_idx] >= 40.0):
                assert cell["risk_tier"] in ("ELEVATED", "CRITICAL")

    # Monotonicity checks:
    # 1. Deeper index drop with fixed liquidity -> larger drawdown
    for c_idx in range(5):
        for r_idx in range(4):
            assert grid[r_idx][c_idx]["drawdown_pct"] > grid[r_idx + 1][c_idx]["drawdown_pct"], (
                f"Drawdown should worsen as index shock intensifies at col {c_idx}"
            )
            
    # 2. Deeper liquidity contraction with fixed shock -> larger drawdown
    for r_idx in range(5):
        for c_idx in range(4):
            assert grid[r_idx][c_idx]["drawdown_pct"] > grid[r_idx][c_idx + 1]["drawdown_pct"], (
                f"Drawdown should worsen as liquidity contracts at row {r_idx}"
            )
