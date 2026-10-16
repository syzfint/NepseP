#!/usr/bin/env python3
"""
tests/test_execution_cost_model.py

Unit tests for Dynamic Implementation Shortfall (IS) decomposition
and Append-Only Merkle Audit Chain integrity.
"""

import pytest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CONTROL_DIR = BASE_DIR / "scripts" / "00_control"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from execution_cost_model import (
    DynamicImplementationShortfallEngine,
    AppendOnlyMerkleAuditChain,
    ImplementationShortfallBreakdown
)


def test_broker_commission_tiers():
    engine = DynamicImplementationShortfallEngine()
    
    # Tier 1: <= 50k (0.40%)
    c1 = engine.compute_broker_commission(40_000)
    assert c1 == 160.0  # 40000 * 0.004

    # Tier 2: 50k - 500k (0.37%)
    c2 = engine.compute_broker_commission(200_000)
    assert c2 == 740.0  # 200000 * 0.0037

    # Tier 3: 500k - 2M (0.34%)
    c3 = engine.compute_broker_commission(1_000_000)
    assert c3 == 3400.0  # 1000000 * 0.0034

    # Tier 4: 2M - 10M (0.30%)
    c4 = engine.compute_broker_commission(5_000_000)
    assert c4 == 15000.0  # 5000000 * 0.0030

    # Tier 5: > 10M (0.27%)
    c5 = engine.compute_broker_commission(20_000_000)
    assert c5 == 54000.0  # 20000000 * 0.0027


def test_implementation_shortfall_decomposition():
    engine = DynamicImplementationShortfallEngine()

    breakdown = engine.evaluate_implementation_shortfall(
        symbol="NABIL",
        target_shares=1000,
        executed_shares=800,
        decision_price=500.0,
        execution_price=501.5,
        final_price=503.0,
        bid_price=499.5,
        ask_price=501.5,
        adv_20d=40_000,
        side="BUY"
    )

    # 1. Total IS must equal sum of constituent costs
    expected_sum = (
        breakdown.spread_cost_npr +
        breakdown.market_impact_npr +
        breakdown.opportunity_cost_npr +
        breakdown.fixed_fees_npr
    )
    assert abs(breakdown.total_is_npr - round(expected_sum, 2)) <= 0.02

    # 2. Opportunity cost check: 200 unexecuted shares * (503.0 - 500.0) = 600 NPR
    assert breakdown.opportunity_cost_npr == 600.0

    # 3. Spread cost check: 800 shares * 501.5 NPR * (2.0 / (2 * 500.5))
    assert breakdown.spread_cost_npr > 0.0

    # 4. Market impact check: square root law
    assert breakdown.market_impact_npr > 0.0

    # 5. Fixed fees include commission, SEBON, CDSC DP
    assert breakdown.fixed_fees_npr > breakdown.broker_commission_npr


def test_merkle_audit_chain_integrity():
    chain = AppendOnlyMerkleAuditChain(secret_key="TEST-SECRET-AUDIT-KEY")

    # Append sequential events
    chain.append_event("SIGNAL_GENERATED", {"symbol": "NABIL", "action": "BUY", "shares": 500})
    chain.append_event("ORDER_STAGED", {"ticket_id": "TKT-NABIL-01", "limit_price": 502.0})
    chain.append_event("ORDER_FILLED", {"ticket_id": "TKT-NABIL-01", "filled_shares": 500, "fill_price": 501.8})

    is_valid, err = chain.verify_chain_integrity()
    assert is_valid is True
    assert err is None
    assert len(chain.entries) == 3


def test_merkle_audit_chain_tamper_detection():
    chain = AppendOnlyMerkleAuditChain(secret_key="TEST-SECRET-AUDIT-KEY")

    chain.append_event("SIGNAL", {"symbol": "NABIL", "qty": 100})
    chain.append_event("SIGNAL", {"symbol": "GBIME", "qty": 200})
    chain.append_event("SIGNAL", {"symbol": "SHIVM", "qty": 300})

    # Tamper with the 2nd event payload hash
    chain.entries[1].payload_hash = "deadbeef" * 8

    is_valid, err = chain.verify_chain_integrity()
    assert is_valid is False
    assert "tampering detected" in err.lower()
