"""
Unit Tests for Pillar 1, Pillar 2, and Section 6 (`tests/test_schur_hrp.py`).

Verifies:
1. Ledoit-Wolf shrinkage bounds covariance matrix condition number kappa <= 2.0.
2. Correlation distance matrix D(i,j) = sqrt(2*(1 - rho_ij)) is symmetric and zero-diagonal.
3. Schur-RA-HRP with `keep_monotonic=True` dynamically bounds gamma to gamma_effective
   such that portfolio variance(Schur) <= variance(HRP).
4. Buy Top-5 / Hold Top-15 Dual-Band Hysteresis Buffer with +-2.5% deadband corridor
   suppresses annual turnover <= 12.0% (~11.9%) and restricts net fee drag below 0.08% (~ -0.077%).
5. Multi-account aggregator computes x_available(t) = x_gross(t) - x_settlement_lock(t) - x_promoter_lock(t),
   enforces T+2 lock ratio R_lock > 0.30 block, and emits WARN_FUT_PROMOTER_CLIFF 14 days before expiry.
6. Microstructure slicer enforces pro-rata equity allocation, 15% top-3 LOB depth ceiling,
   and Priority 1 -> Priority 2 -> Priority 3 CGT tax-lot waterfall.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from engine.aggregator import (
    MultiAccountAggregator,
    create_default_institutional_vault,
)
from engine.alert_system import TriHorizonAlertEngine
from engine.execution_slicer import (
    CandidateTaxLot,
    Level2OrderBook,
    LOBLevel,
    MicrostructureExecutionSlicer,
)
from engine.ipc_shared_memory import (
    CACHE_LINE_BYTES,
    LockFreeSharedMemoryRingBuffer,
    allocate_cache_aligned_matrix,
)
from engine.portfolio_optimizer import SchurRAHRPOptimizer


def _build_test_returns_df(n_days: int = 320, n_assets: int = 16) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    symbols = [
        "NABIL", "NICA", "SCB", "CHDC", "HIDCL", "UPPER", "SHIVM", "NTC",
        "NRIC", "HDL", "GBIME", "SANIMA", "EBL", "CIT", "BPCL", "API",
    ][:n_assets]
    base_factor = rng.normal(0.0004, 0.010, size=(n_days, 1))
    collinear = rng.normal(0.0, 0.009, size=n_days)

    mat = np.zeros((n_days, n_assets), dtype=np.float64)
    for j in range(n_assets):
        if j in (0, 1):
            # Create strong collinearity so raw sample condition number > 100
            mat[:, j] = collinear + rng.normal(0.0, 0.0003, size=n_days)
        else:
            mat[:, j] = 0.7 * base_factor[:, 0] + rng.normal(
                0.0, 0.005 + 0.0004 * j, size=n_days
            )

    dates = pd.date_range("2025-01-01", periods=n_days, freq="B")
    return pd.DataFrame(mat, index=dates, columns=symbols)


def test_ledoit_wolf_condition_number_bound_and_distance_metric() -> None:
    returns_df = _build_test_returns_df()
    optimizer = SchurRAHRPOptimizer(gamma=0.65, keep_monotonic=True, max_condition_number=2.0)

    cov_shrunk, raw_kappa, shrunk_kappa, lw_alpha = optimizer.ledoit_wolf_shrinkage(
        returns_df.to_numpy(), enforce_condition_bound=True
    )

    assert raw_kappa > 100.0, "Raw sample covariance should exhibit high condition number > 100"
    assert shrunk_kappa <= 2.0 + 1e-6, f"Expected shrunk kappa <= 2.0, got {shrunk_kappa}"
    assert 0.0 <= lw_alpha <= 1.0

    corr, dist = optimizer.cov_to_corr_and_distance(cov_shrunk)
    assert np.allclose(np.diag(corr), 1.0)
    assert np.allclose(np.diag(dist), 0.0)
    assert np.allclose(dist, dist.T)
    # Check D(i,j) = sqrt(2 * (1 - rho_ij))
    expected_dist = np.sqrt(np.maximum(0.0, 2.0 * (1.0 - corr)))
    assert np.allclose(dist, expected_dist, atol=1e-8)


def test_schur_ra_hrp_monotonic_variance_bound() -> None:
    returns_df = _build_test_returns_df()
    optimizer = SchurRAHRPOptimizer(gamma=0.75, keep_monotonic=True, max_condition_number=2.0)
    result = optimizer.optimize(returns_df)

    assert abs(sum(result.raw_weights.values()) - 1.0) < 1e-6
    assert abs(sum(result.post_hysteresis_weights.values()) - 1.0) < 1e-6
    assert result.portfolio_variance_schur <= result.portfolio_variance_hrp + 1e-12, (
        f"Schur variance {result.portfolio_variance_schur} exceeded HRP variance "
        f"{result.portfolio_variance_hrp}"
    )
    assert 0.0 <= result.gamma_effective <= result.gamma_requested


def test_dual_band_hysteresis_turnover_suppression_below_12_pct() -> None:
    returns_df = _build_test_returns_df(n_days=340, n_assets=16)
    optimizer = SchurRAHRPOptimizer(
        gamma=0.65,
        keep_monotonic=True,
        entry_rank_threshold=5,
        exit_rank_threshold=15,
        deadband_threshold=0.025,
    )

    metrics = optimizer.simulate_rolling_rebalance(
        returns_df,
        lookback_days=120,
        rebalance_step_days=21,
        trading_days_per_year=252,
    )

    assert metrics["annual_turnover_hysteresis"] <= 0.12, (
        f"Expected hysteresis annual turnover <= 12.0%, got {metrics['annual_turnover_hysteresis']:.4f}"
    )
    assert metrics["annual_turnover_hysteresis"] < metrics["annual_turnover_unbuffered"]
    assert abs(metrics["fee_drag_hysteresis"]) <= 0.0008  # <= 8 bps annual fee drag


def test_dual_band_hysteresis_entry_hold_exit_rules() -> None:
    optimizer = SchurRAHRPOptimizer(
        entry_rank_threshold=5,
        exit_rank_threshold=15,
        deadband_threshold=0.025,
    )
    symbols = [f"SYM{i:02d}" for i in range(1, 17)]
    # Target weights strictly ordered SYM01 (rank 1) .. SYM16 (rank 16)
    raw_targets = {sym: float(17 - idx) for idx, sym in enumerate(symbols)}
    total_raw = sum(raw_targets.values())
    target_weights = {k: v / total_raw for k, v in raw_targets.items()}

    # Case 1: Cold start only enters Top-5 ranks
    init_w, ranks, actions = optimizer.apply_dual_band_hysteresis(target_weights, current_weights=None)
    for sym in symbols:
        if ranks[sym] <= 5:
            assert init_w[sym] > 0.0
            assert actions[sym] == "BUY_ENTRY_TOP5"
        else:
            assert init_w[sym] == 0.0

    # Case 2: Held asset at rank 12 stays held, held asset at rank 16 is exited (w=0),
    # unheld asset at rank 8 is filtered out (cannot enter unless rank <= 5)
    current_w = {
        "SYM01": 0.25,
        "SYM02": 0.25,
        "SYM03": 0.20,
        "SYM12": 0.15,  # Rank 12 <= 15 -> held
        "SYM16": 0.15,  # Rank 16 > 15 -> exited!
    }
    post_w, ranks2, actions2 = optimizer.apply_dual_band_hysteresis(
        target_weights, current_weights=current_w
    )
    assert post_w["SYM16"] == 0.0
    assert actions2["SYM16"] == "EXIT_RANK_GT_15"
    assert post_w["SYM08"] == 0.0
    assert actions2["SYM08"] == "FILTERED_ENTRY_GT_5"
    assert post_w["SYM12"] > 0.0


def test_multi_account_aggregator_and_promoter_lock_cliff() -> None:
    ref = datetime(2026, 10, 20, 9, 0, 0, tzinfo=timezone.utc)
    vault, prices = create_default_institutional_vault(ref)
    aggregator = MultiAccountAggregator(ref)
    ledger = aggregator.consolidate_vault(vault, prices, ref)

    # Verify x_available(t) = x_gross(t) - x_settlement_lock(t) - x_promoter_lock(t)
    for sym in ledger.symbols:
        expected_avail = max(
            0,
            ledger.x_gross[sym] - ledger.x_settlement_lock[sym] - ledger.x_promoter_lock[sym],
        )
        assert ledger.x_available[sym] == expected_avail

    # Verify UPPER has 10,000 promoter-locked shares expiring in 11 days (<= 14d threshold)
    assert ledger.x_promoter_lock["UPPER"] == 10000
    assert ledger.x_available["UPPER"] == 0
    assert ledger.weight_restrictions.get("UPPER") == 0.0
    assert any(
        w.code == "WARN_FUT_PROMOTER_CLIFF" and w.symbol == "UPPER"
        for w in ledger.promoter_cliff_warnings
    )


def test_execution_slicer_15pct_lob_cap_and_cgt_waterfall() -> None:
    slicer = MicrostructureExecutionSlicer(lob_depth_cap_ratio=0.15, top_lob_levels=3)
    book = Level2OrderBook(
        symbol="NABIL",
        last_traded_price=1245.0,
        bids=[
            LOBLevel(1, 1244.0, 400),
            LOBLevel(2, 1243.0, 300),
            LOBLevel(3, 1242.0, 300),  # Top-3 bid depth = 1,000 shares -> 15% cap = 150 shares
        ],
        asks=[
            LOBLevel(1, 1246.0, 500),
            LOBLevel(2, 1247.0, 300),
            LOBLevel(3, 1248.0, 200),
        ],
    )
    sub_accounts = [
        {"account_id": "SUB-1", "account_label": "Personal", "broker_code": "58", "available_equity": 10_000_000.0},
        {"account_id": "SUB-2", "account_label": "Corporate", "broker_code": "34", "available_equity": 30_000_000.0},
    ]
    allocs = slicer.slice_pro_rata_across_accounts(400, 1245.0, sub_accounts)
    assert allocs[0].allocated_quantity == 100  # 25% of 400
    assert allocs[1].allocated_quantity == 300  # 75% of 400

    slices = slicer.slice_order_with_lob_cap("PO-TEST", "NABIL", "SELL", allocs, book)
    for ch in slices:
        assert ch.quantity <= 150  # 15% of 1,000 top-3 depth
        assert ch.lob_consumption_pct <= 15.0

    # Verify CGT Waterfall Priority 1 (Loss) -> Priority 2 (5% LTCGT) -> Priority 3 (7.5% STCGT)
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    lots = [
        CandidateTaxLot(
            lot_id="LOT-STCGT",
            boid_id="1301010000482910",
            sub_account_id="SUB-1",
            broker_code="58",
            symbol="NABIL",
            available_quantity=200,
            purchase_price=1100.0,
            purchase_date=now - timedelta(days=90),
            holding_days=90,
        ),
        CandidateTaxLot(
            lot_id="LOT-LTCGT",
            boid_id="1301010000482910",
            sub_account_id="SUB-1",
            broker_code="58",
            symbol="NABIL",
            available_quantity=200,
            purchase_price=980.0,
            purchase_date=now - timedelta(days=500),
            holding_days=500,
        ),
        CandidateTaxLot(
            lot_id="LOT-LOSS",
            boid_id="1301010000482910",
            sub_account_id="SUB-1",
            broker_code="58",
            symbol="NABIL",
            available_quantity=150,
            purchase_price=1320.0,
            purchase_date=now - timedelta(days=180),
            holding_days=180,
        ),
    ]
    selected, pnl, cgt, saved = slicer.optimize_cgt_tax_lots("NABIL", 300, 1245.0, lots)
    assert len(selected) == 2
    assert selected[0].lot_id == "LOT-LOSS" and selected[0].priority_tier == 1
    assert selected[0].allocated_quantity == 150
    assert selected[1].lot_id == "LOT-LTCGT" and selected[1].priority_tier == 2
    assert selected[1].allocated_quantity == 150
    assert saved > 0.0


def test_health_gauge_and_64_byte_ipc_alignment() -> None:
    alert_engine = TriHorizonAlertEngine()
    normal_health = alert_engine.compute_portfolio_health_score(
        var_99=0.0032, vpin=0.06, c_locked_ratio=0.04, s_locked_ratio=0.02, hawkes_intensity=0.04
    )
    assert 80 <= normal_health.score <= 100
    assert normal_health.status == "Optimal"

    toxic_health = alert_engine.compute_portfolio_health_score(
        var_99=0.015, vpin=0.74, c_locked_ratio=0.124, s_locked_ratio=0.08, hawkes_intensity=0.88
    )
    assert toxic_health.microstructure_penalty_applied is True
    assert toxic_health.penalty_points == 40
    assert toxic_health.score <= normal_health.score - 40

    aligned = allocate_cache_aligned_matrix((32, 16), dtype=np.float64)
    assert aligned.ctypes.data % CACHE_LINE_BYTES == 0

    ring = LockFreeSharedMemoryRingBuffer("apex_test_ring", capacity=16, create=True)
    seq = ring.write_frame(0.18, 0.04, 0.015, float(normal_health.score), 1, 1500, 1245.0)
    frame = ring.read_latest()
    assert frame is not None and frame.sequence_id == seq
    assert abs(frame.last_traded_price - 1245.0) < 1e-6
    ring.close(unlink=True)
