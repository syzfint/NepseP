#!/usr/bin/env python3
"""
tests/test_rd_agent_live_execution.py

Test Suite for RD-Agent & Qlib Live Execution Bridge
=====================================================
Validates candidate conviction filtering, HRP risk allocation,
QuantRiskLab tail risk bounding, Dynamic POV order slicing, 15% depth caps,
and SHA-256 blotter signing for NEPSE TMS execution.
"""

import sys
import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import importlib

BASE_DIR = Path(__file__).resolve().parents[1]
for p in [str(BASE_DIR), str(BASE_DIR / "scripts"), str(BASE_DIR / "scripts" / "02_modeling_and_calculations"), str(BASE_DIR / "scripts" / "00_control")]:
    if p not in sys.path:
        sys.path.insert(0, p)

bridge_mod = importlib.import_module("scripts.02_modeling_and_calculations.rd_agent_live_execution_bridge")
RDAgentLiveExecutionBridge = bridge_mod.RDAgentLiveExecutionBridge


@pytest.fixture
def mock_candidates():
    return [
        {
            "symbol": "NABIL",
            "expected_return_5d": 0.032,
            "meta_probability": 0.65,
            "uncertainty_spread": 4.5,
            "latest_close": 530.0,
        },
        {
            "symbol": "CHCL",
            "expected_return_5d": 0.045,
            "meta_probability": 0.62,
            "uncertainty_spread": 5.8,
            "latest_close": 325.0,
        },
        {
            "symbol": "SHIVM",
            "expected_return_5d": -0.015,  # Negative return -> reject
            "meta_probability": 0.45,      # Low prob -> reject
            "uncertainty_spread": 6.2,
            "latest_close": 670.0,
        },
        {
            "symbol": "CORBL",
            "expected_return_5d": 0.080,
            "meta_probability": 0.70,
            "vpin": 0.85,                  # Toxic VPIN -> reject
            "uncertainty_spread": 12.0,
            "latest_close": 740.0,
        },
    ]


@pytest.fixture
def mock_returns_panel():
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=100)
    rets = {
        "NABIL": np.random.normal(0.001, 0.015, 100),
        "CHCL": np.random.normal(0.0015, 0.020, 100),
        "SHIVM": np.random.normal(-0.0005, 0.018, 100),
        "CORBL": np.random.normal(0.002, 0.035, 100),
    }
    return pd.DataFrame(rets, index=dates)


def test_candidate_filtering_and_ranking(mock_candidates):
    bridge = RDAgentLiveExecutionBridge(min_meta_prob=0.60, vpin_toxic_threshold=0.70)
    certified = bridge.filter_and_rank_candidates(mock_candidates)

    # SHIVM rejected (negative ret + low prob), CORBL rejected (toxic VPIN 0.85)
    symbols = [c["symbol"] for c in certified]
    assert "NABIL" in symbols
    assert "CHCL" in symbols
    assert "SHIVM" not in symbols
    assert "CORBL" not in symbols

    # Check descending order by alpha_score
    assert certified[0]["alpha_score"] >= certified[1]["alpha_score"]


def test_hrp_weights_allocation(mock_candidates, mock_returns_panel):
    bridge = RDAgentLiveExecutionBridge()
    certified = bridge.filter_and_rank_candidates(mock_candidates)
    weights = bridge.allocate_hrp_weights(certified, mock_returns_panel)

    assert "CASH" in weights
    assert weights["CASH"] >= 0.09  # At least cash buffer (~10%)
    total_w = sum(weights.values())
    assert abs(total_w - 1.0) <= 0.05

    for sym in ["NABIL", "CHCL"]:
        assert sym in weights
        assert weights[sym] >= 0.03  # Min weight
        assert weights[sym] <= 0.60  # Feasible allocation in concentrated 2-asset basket


def test_tail_risk_defense_adjustment(mock_candidates, mock_returns_panel):
    # Set tight VaR limit to force risk scaling
    tight_bridge = RDAgentLiveExecutionBridge(max_portfolio_var_95=0.010, max_portfolio_es_95=0.015)
    certified = tight_bridge.filter_and_rank_candidates(mock_candidates)
    raw_weights = tight_bridge.allocate_hrp_weights(certified, mock_returns_panel)

    adj_weights, risk_summary = tight_bridge.screen_and_adjust_tail_risk(raw_weights, mock_returns_panel)

    assert risk_summary["risk_adjusted"] is True
    # Cash allocation should have increased to derisk
    assert adj_weights["CASH"] > raw_weights["CASH"]


def test_dynamic_pov_slicing_and_depth_cap(mock_candidates):
    bridge = RDAgentLiveExecutionBridge()
    certified = bridge.filter_and_rank_candidates(mock_candidates)

    target_weights = {"NABIL": 0.15, "CHCL": 0.12, "CASH": 0.73}
    market_depths = {
        "NABIL": {"top3_ask_vol": 2000, "top3_bid_vol": 2500, "prev_close": 530.0},
        "CHCL": {"top3_ask_vol": 5000, "top3_bid_vol": 5500, "prev_close": 325.0},
    }

    blotter = bridge.stage_execution_blotter(
        target_weights=target_weights,
        candidates=certified,
        total_capital_npr=5_000_000.0,
        current_holdings={"NABIL": 0, "CHCL": 0},
        market_depths=market_depths,
    )

    assert blotter["total_staged_orders"] > 0
    assert blotter["compliance_passed"] is True
    assert len(blotter["integrity_hash"]) == 64  # SHA-256

    for t in blotter["tickets"]:
        # 10-unit board lot check
        assert t["quantity"] % 10 == 0
        assert t["quantity"] > 0
        # 15% depth cap check
        assert t["lob_depth_share_pct"] <= 15.1
        # Circuit limit check
        assert t["circuit_min"] <= t["limit_price"] <= t["circuit_max"]
        assert t["status"] == "STAGED"


def test_end_to_end_bridge_pipeline(mock_candidates, mock_returns_panel):
    bridge = RDAgentLiveExecutionBridge()
    res = bridge.run_bridge_pipeline(
        candidates=mock_candidates,
        returns_df=mock_returns_panel,
        total_capital_npr=10_000_000.0,
    )

    assert "certified_candidates" in res
    assert "hrp_weights" in res
    assert "tail_risk_adjusted_weights" in res
    assert "risk_summary" in res
    assert "execution_blotter" in res
    assert res["execution_blotter"]["compliance_passed"] is True


def test_mbor_dispatch_integration(mock_candidates, mock_returns_panel):
    bridge = RDAgentLiveExecutionBridge()
    res = bridge.run_bridge_pipeline(
        candidates=mock_candidates,
        returns_df=mock_returns_panel,
        total_capital_npr=10_000_000.0,
    )
    blotter = res["execution_blotter"]
    mbor_result = bridge.route_blotter_via_mbor(blotter)
    assert mbor_result["routed_count"] > 0
    assert mbor_result["active_gateway"] == "GATEWAY_PRIMARY_YCO"
    assert len(mbor_result["provenance_seal"]) == 64

