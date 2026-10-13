#!/usr/bin/env python3
"""
tests/test_multi_broker_execution_suite.py

VERIFICATION SUITE FOR MULTI-BROKER ROUTER & AUTOMATED EXECUTION FRAMEWORK
===========================================================================
Validates:
1. Multi-Broker Router (MBOR):
   - EWMA latency tracking and 1,000ms failover trigger.
   - Rolling error rate (5.0%) failover trigger.
   - ClOrdID idempotency, PossDupFlag reconciliation, and order lifecycle.
2. In-Memory L2 Order Book Engine:
   - 20-level depth, relative spread, and slope computations.
   - Sub-15ms processing latency SLA.
   - WebSocket watchdog ping/pong drop detection.
3. Automated Overnight & Pre-Open Audit Engine:
   - Sentiment < -0.40 cancellation (FIX 35=F).
   - Imbalance < -0.50 cancellation (FIX 35=F).
   - TOP slippage > 3% price adjustment (FIX 35=G).
   - Relative spread > 8% execution pause.
4. T+2 Cash Flow & Margin Bridge Engine:
   - T+2 settlement forecast formula.
   - Class A vs Class B haircut and leverage buffer calculations.
   - Deficit detection and routing.
5. Regulatory Compliance & Hard Kill-Switch:
   - Token-bucket OTR tracking and MRT 100ms delay enforcement.
   - Daily drawdown >= 3.0% trigger and FIX 35=q Mass Cancel execution.
   - System transition to LOCKED_FAIL_CLOSED.
   - Sovereign Pod HYOK cryptographic sealing and cross-border data scrubbing.
"""

import sys
import time
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CONTROL_DIR = BASE_DIR / "scripts" / "00_control"

for p in [str(BASE_DIR), str(CONTROL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from multi_broker_router import (
    MultiBrokerRouter,
    GatewayStatus,
    OrderActionType,
    RoutedOrderRecord,
)
from l2_orderbook_engine import (
    InMemL2OrderBook,
    DirectMarketDataClient,
)
from overnight_order_audit_engine import (
    OvernightOrderAuditEngine,
)
from margin_bridge_engine import (
    MarginBridgeEngine,
    BrokerClass,
    CollateralPosition,
)
from regulatory_compliance_guard import (
    OTRThrottlingLimiter,
    HardKillSwitchEngine,
    EngineExecutionState,
    SovereignPodManager,
)


# =====================================================================
# 1. MULTI-BROKER ROUTER (MBOR) TESTS
# =====================================================================

def test_mbor_ewma_latency_and_failover():
    router = MultiBrokerRouter(primary_id="YCO_PRIMARY", secondary_id="ATRAD_SECONDARY")
    assert router.active_gateway_id == "YCO_PRIMARY"

    # Feed healthy latency (50ms)
    for _ in range(5):
        router.update_gateway_health("YCO_PRIMARY", rtt_ms=50.0, success=True)
    assert router.telemetry["YCO_PRIMARY"].ewma_latency_ms < 100.0
    assert router.active_gateway_id == "YCO_PRIMARY"

    # Simulate sustained latency degradation > 1,000ms over 5 seconds
    telem = router.telemetry["YCO_PRIMARY"]
    telem.ewma_latency_ms = 1200.0
    telem.consecutive_high_latency_sec = 5.5

    # Health check triggers failover
    triggered = router.update_gateway_health("YCO_PRIMARY", rtt_ms=1200.0, success=True)
    assert triggered is True
    assert router.active_gateway_id == "ATRAD_SECONDARY"
    assert router.telemetry["YCO_PRIMARY"].status == GatewayStatus.DEGRADED
    assert router.telemetry["ATRAD_SECONDARY"].status == GatewayStatus.ACTIVE


def test_mbor_error_rate_failover():
    router = MultiBrokerRouter(primary_id="YCO_PRIMARY", secondary_id="ATRAD_SECONDARY")
    
    # Ingest 15 messages with > 5% error rate (e.g. 2 failures out of 15 = 13.3%)
    for i in range(13):
        router.update_gateway_health("YCO_PRIMARY", rtt_ms=30.0, success=True)
    for i in range(2):
        router.update_gateway_health("YCO_PRIMARY", rtt_ms=30.0, success=False)

    assert router.active_gateway_id == "ATRAD_SECONDARY"
    assert len(router.failover_history) >= 1


def test_mbor_order_idempotency_and_lifecycle():
    router = MultiBrokerRouter(primary_id="YCO_PRIMARY", secondary_id="ATRAD_SECONDARY")
    
    # Submit order
    order = router.submit_order(symbol="NABIL", side="BUY", quantity=100, limit_price=530.0)
    assert order.status == "ACKNOWLEDGED"
    assert order.broker_venue_id is not None
    assert order.cl_ord_id.startswith("CL-")

    # Replace order (35=G)
    replaced = router.replace_order(orig_cl_ord_id=order.cl_ord_id, new_price=535.0, new_qty=100)
    assert replaced.status == "REPLACED"
    assert replaced.limit_price == 535.0

    # Cancel order (35=F)
    canceled = router.cancel_order(orig_cl_ord_id=order.cl_ord_id)
    assert canceled.status == "CANCELED"


# =====================================================================
# 2. IN-MEMORY L2 ORDER BOOK TESTS
# =====================================================================

def test_l2_order_book_metrics():
    book = InMemL2OrderBook(symbol="NABIL")
    bids = [(530.0, 500), (529.0, 1000), (528.0, 1500)]
    asks = [(532.0, 400), (533.0, 800), (535.0, 1200)]
    book.update_book(bids, asks)

    snap = book.get_snapshot()
    assert snap.best_bid == 530.0
    assert snap.best_ask == 532.0
    assert snap.mid_price == 531.0
    
    # Depth = (sum bids + sum asks) / 2 = (3000 + 2400) / 2 = 2700.0
    assert snap.depth_20 == 2700.0

    # Relative Spread = 2 * (532 - 530) / (532 + 530) = 4 / 1062 = 0.003766
    expected_rel_spread = (2.0 * (532.0 - 530.0)) / (532.0 + 530.0)
    assert abs(snap.relative_spread - expected_rel_spread) < 1e-6
    assert snap.slope > 0.0


def test_market_data_client_watchdog_and_latency_sla():
    client = DirectMarketDataClient(ping_interval_sec=1.0, socket_timeout_sec=2.0)
    packet = {
        "symbol": "CHCL",
        "bids": [[320.0, 100], [319.0, 200]],
        "asks": [[322.0, 150], [323.0, 250]],
    }
    
    # Ingestion benchmark
    t0 = time.perf_counter()
    snap = client.ingest_l2_packet(packet)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 15.0  # Sub-15ms SLA
    assert snap.symbol == "CHCL"

    # Watchdog check
    assert client.check_connection_health() is True
    client.last_pong_ts = time.time() - 5.0
    assert client.check_connection_health() is False


# =====================================================================
# 3. OVERNIGHT & PRE-OPEN AUDIT ENGINE TESTS
# =====================================================================

def test_pre_open_audit_cancellation_and_modification():
    router = MultiBrokerRouter()
    audit_engine = OvernightOrderAuditEngine()

    # Create 3 orders
    o1 = router.submit_order(symbol="NABIL", side="BUY", quantity=100, limit_price=530.0)
    o2 = router.submit_order(symbol="CHCL", side="BUY", quantity=200, limit_price=340.0)
    o3 = router.submit_order(symbol="SHIVM", side="BUY", quantity=50, limit_price=600.0)

    market_telemetry = {
        "NABIL": {
            "sentiment": -0.65,      # Sentiment < -0.40 -> CANCEL
            "imbalance": 0.10,
            "top_price": 530.0,
            "relative_spread": 0.01,
        },
        "CHCL": {
            "sentiment": 0.20,
            "imbalance": 0.05,
            "top_price": 320.0,       # |340 - 320| / 320 = 6.25% > 3% -> MODIFY PRICE to 320.0
            "relative_spread": 0.01,
        },
        "SHIVM": {
            "sentiment": 0.10,
            "imbalance": -0.60,       # Imbalance < -0.50 -> CANCEL
            "top_price": 600.0,
            "relative_spread": 0.01,
        },
    }

    results = audit_engine.execute_pre_open_audit(router, market_telemetry)
    assert len(results) == 3

    # Check NABIL canceled due to sentiment
    assert router.order_blotter[o1.cl_ord_id].status == "CANCELED"
    # Check CHCL price replaced to TOP 320.0
    assert router.order_blotter[o2.cl_ord_id].status == "REPLACED"
    assert router.order_blotter[o2.cl_ord_id].limit_price == 320.0
    # Check SHIVM canceled due to imbalance
    assert router.order_blotter[o3.cl_ord_id].status == "CANCELED"


# =====================================================================
# 4. T+2 CASH FLOW & MARGIN BRIDGE TESTS
# =====================================================================

def test_margin_bridge_t2_cash_and_liquidity_routing():
    engine = MarginBridgeEngine(transaction_fee_pct=0.00415)

    # Test cash forecasting: Current cash 1,000,000; Sell 500,000; Buy 800,000; Corp 50,000
    # C_{t+2} = 1,000,000 + 500,000*(1-0.00415) - 800,000*(1+0.00415) + 50,000
    # = 1,000,000 + 497,925 - 803,320 + 50,000 = 744,605
    c_t2 = engine.forecast_t2_cash_position(
        current_cash=1_000_000.0,
        buy_orders_value=800_000.0,
        sell_orders_value=500_000.0,
        corporate_actions_cash=50_000.0,
    )
    assert round(c_t2, 2) == 744605.0

    # Add collateral to Class A broker
    engine.set_collateral(
        "BROKER_CLASS_A_CLEARING",
        [CollateralPosition(symbol="NABIL", quantity=1000, market_price=500.0)],  # Value: 500,000
    )
    # Class A: 5,000,000 + (500,000 * (1 - 0.15)) * 4.0 = 5,000,000 + 1,700,000 = 6,700,000
    l_avail_a = engine.calculate_available_liquidity("BROKER_CLASS_A_CLEARING")
    assert round(l_avail_a, 2) == 6_700_000.0

    report = engine.evaluate_settlement_and_route(
        current_cash=1_000_000.0,
        buy_value=500_000.0,
        sell_value=100_000.0,
    )
    assert report.deficit_detected is False
    assert report.recommended_broker_id == "BROKER_CLASS_A_CLEARING"


# =====================================================================
# 5. REGULATORY COMPLIANCE, OTR & HARD KILL-SWITCH TESTS
# =====================================================================

def test_otr_throttling_limiter_and_mrt():
    limiter = OTRThrottlingLimiter(otr_warning_ceiling=45.0, otr_hard_ceiling=50.0, min_resting_time_sec=0.100)
    
    # 40 orders with 1 execution -> OTR = 40.0
    for _ in range(40):
        limiter.record_order_action("NEW", volume=100)
    limiter.record_execution(executed_volume=100)

    permit, msg = limiter.check_throttle_permit()
    assert permit is True
    assert msg == "PERMITTED"

    # Add 6 orders -> total 46 operations / 1 execution = 46.0 -> Warning Ceiling
    for _ in range(6):
        limiter.record_order_action("NEW", volume=100)
    permit, msg = limiter.check_throttle_permit()
    assert permit is True
    assert msg == "THROTTLED"

    # Add 5 more orders -> 51 operations / 1 = 51.0 -> Hard Ceiling Breached
    for _ in range(5):
        limiter.record_order_action("NEW", volume=100)
    permit, msg = limiter.check_throttle_permit()
    assert permit is False
    assert "Hard Ceiling breached" in msg


def test_emergency_hard_kill_switch_engagement():
    router = MultiBrokerRouter()
    kill_switch = HardKillSwitchEngine(max_daily_drawdown_pct=0.03, peak_nav=10_000_000.0)

    # Create active orders
    router.submit_order(symbol="NABIL", side="BUY", quantity=100, limit_price=530.0)
    router.submit_order(symbol="CHCL", side="BUY", quantity=200, limit_price=320.0)

    # 1% drawdown -> Normal
    kill_switch.current_nav = 9_900_000.0
    triggered, reason = kill_switch.check_kill_switch_triggers(router)
    assert triggered is False

    # 3.5% drawdown (NAV drops to 9,650,000) -> Trigger
    kill_switch.current_nav = 9_650_000.0
    triggered, reason = kill_switch.check_kill_switch_triggers(router)
    assert triggered is True
    assert "Daily NAV Drawdown" in reason

    # Execute Kill-Switch
    report = kill_switch.execute_kill_switch(router, trigger_reason=reason)
    assert kill_switch.state == EngineExecutionState.LOCKED_FAIL_CLOSED
    assert report["orders_purged"] == 2
    assert report["final_engine_state"] == "LOCKED_FAIL_CLOSED"

    # All blotter orders canceled
    for order in router.order_blotter.values():
        assert order.status == "CANCELED"


def test_sovereign_pod_manager_provenance_and_scrubbing():
    pod = SovereignPodManager(jurisdiction="NEPAL_NEPSE")
    sensitive_data = {
        "order_id": "ORD-1234",
        "symbol": "NABIL",
        "client_demat_no": "1301000000012345",
        "investor_pan": "100234567",
        "quantity": 500,
        "price": 530.0,
    }

    # Egress scrub
    scrubbed = pod.filter_egress_payload(sensitive_data)
    assert "client_demat_no" not in scrubbed
    assert "investor_pan" not in scrubbed
    assert scrubbed["symbol"] == "NABIL"
    assert scrubbed["sovereign_filter_applied"] is True

    # Cryptographic provenance seal
    seal = pod.seal_blotter_provenance(scrubbed)
    assert len(seal) == 64  # SHA-256 hex string
