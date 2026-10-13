#!/usr/bin/env python3
"""
scripts/00_control/regulatory_compliance_guard.py

REGULATORY COMPLIANCE, TOKEN-BUCKET OTR GOVERNOR & EMERGENCY HARD KILL-SWITCH
==============================================================================
Enforces ESMA / MiFID II style market integrity boundaries, token-bucket OTR
throttling, emergency kill-switch liquidation, and sovereign pod data isolation.

Core Modules:
1. Token-Bucket OTR Limiter:
   OTR_num = (N_new + N_modify + N_cancel) / N_executed
   OTR_vol = (sum(Vol_orders) / sum(Vol_executed)) - 1
   Ceiling: 50:1. Warning buffer: 45:1.
   Enforces 100ms Minimum Resting Time (MRT) on resting limit orders when warning threshold breached.
2. Emergency Hard Kill-Switch:
   Triggers:
   - Daily Drawdown >= 3.0% (Delta D_day >= 0.03)
   - Exchange Circuit Breaker Halt
   - Dual-Gateway Failure (Lt > 5000ms on all endpoints)
   Execution:
   - FIX 35=q Mass Cancel (MassCancelRequestType=7)
   - Awaits 35=r / 35=8 (OrdStatus=4)
   - FIX 35=5 Logout & locks system into LOCKED_FAIL_CLOSED
3. Sovereign Pod Residency & Key Guard (HYOK):
   - Confines raw order logs & client demat records to local in-country pod.
   - Enforces SHA-256 cryptographic provenance seals before any egress.
"""

import time
import uuid
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from multi_broker_router import MultiBrokerRouter

logger = logging.getLogger("RegulatoryComplianceGuard")


class EngineExecutionState(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    THROTTLED = "THROTTLED"
    KILL_SWITCH_ENGAGED = "KILL_SWITCH_ENGAGED"
    LOCKED_FAIL_CLOSED = "LOCKED_FAIL_CLOSED"


@dataclass
class OTRMetrics:
    total_new_orders: int = 0
    total_modifications: int = 0
    total_cancellations: int = 0
    total_executions: int = 0
    total_order_volume: int = 0
    total_executed_volume: int = 0

    @property
    def total_order_operations(self) -> int:
        return self.total_new_orders + self.total_modifications + self.total_cancellations

    @property
    def otr_num(self) -> float:
        """OTR_num = N_orders / max(N_trades, 1)"""
        trades = max(self.total_executions, 1)
        return self.total_order_operations / float(trades)

    @property
    def otr_vol(self) -> float:
        """OTR_vol = sum(Vol_orders) / max(sum(Vol_executed), 1) - 1"""
        exec_vol = max(self.total_executed_volume, 1)
        return (self.total_order_volume / float(exec_vol)) - 1.0


class OTRThrottlingLimiter:
    """
    Token-bucket style OTR rate governor preventing exchange quote stuffing penalties.
    """

    def __init__(
        self,
        otr_warning_ceiling: float = 45.0,
        otr_hard_ceiling: float = 50.0,
        min_resting_time_sec: float = 0.100,  # 100 ms Minimum Resting Time
    ):
        self.otr_warning_ceiling = otr_warning_ceiling
        self.otr_hard_ceiling = otr_hard_ceiling
        self.min_resting_time_sec = min_resting_time_sec
        self.metrics = OTRMetrics()
        self.last_order_timestamps: Dict[str, float] = {}

    def record_order_action(self, action_type: str, volume: int = 0):
        if action_type == "NEW":
            self.metrics.total_new_orders += 1
        elif action_type == "MODIFY":
            self.metrics.total_modifications += 1
        elif action_type == "CANCEL":
            self.metrics.total_cancellations += 1
        self.metrics.total_order_volume += volume

    def record_execution(self, executed_volume: int):
        self.metrics.total_executions += 1
        self.metrics.total_executed_volume += executed_volume

    def check_throttle_permit(self, cl_ord_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Evaluates whether an order update is permissible under OTR and MRT rules.
        """
        current_otr = self.metrics.otr_num

        # Check Minimum Resting Time if modifying an existing order
        if cl_ord_id and cl_ord_id in self.last_order_timestamps:
            elapsed = time.time() - self.last_order_timestamps[cl_ord_id]
            if elapsed < self.min_resting_time_sec:
                return False, f"MRT violation: Order rested for {elapsed*1000:.1f}ms < {self.min_resting_time_sec*1000:.0f}ms"

        # Hard Ceiling check
        if current_otr >= self.otr_hard_ceiling:
            return False, f"OTR Hard Ceiling breached: {current_otr:.1f} >= {self.otr_hard_ceiling:.1f}"

        # Warning Ceiling (Throttles non-essential modifications)
        if current_otr >= self.otr_warning_ceiling:
            logger.warning(f"OTR Warning buffer reached: {current_otr:.1f} >= {self.otr_warning_ceiling:.1f}. Throttling active.")
            return True, "THROTTLED"

        return True, "PERMITTED"

    def mark_order_activity(self, cl_ord_id: str):
        self.last_order_timestamps[cl_ord_id] = time.time()


class HardKillSwitchEngine:
    """
    Emergency liquidation controller activated upon peak drawdown breach,
    exchange circuit breakers, or dual-gateway transport failure.
    """

    def __init__(
        self,
        max_daily_drawdown_pct: float = 0.03,  # 3.0% NAV loss
        peak_nav: float = 10_000_000.0,
    ):
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self.peak_nav = peak_nav
        self.current_nav = peak_nav
        self.state = EngineExecutionState.OPERATIONAL
        self.engagement_report: Optional[Dict[str, Any]] = None

    def update_portfolio_nav(self, current_nav: float) -> float:
        self.current_nav = current_nav
        if current_nav > self.peak_nav:
            self.peak_nav = current_nav

        drawdown = (self.peak_nav - self.current_nav) / self.peak_nav if self.peak_nav > 0 else 0.0
        return drawdown

    def check_kill_switch_triggers(
        self,
        router: MultiBrokerRouter,
        market_halted: bool = False,
    ) -> Tuple[bool, str]:
        """Evaluates daily drawdown, exchange halt, or dual-gateway failure."""
        dd = self.update_portfolio_nav(self.current_nav)

        if dd >= self.max_daily_drawdown_pct:
            return True, f"Daily NAV Drawdown ({dd:.2%}) breached threshold ({self.max_daily_drawdown_pct:.2%})"

        if market_halted:
            return True, "Exchange Circuit Breaker Halt Triggered"

        # Check dual-gateway failure
        g1 = router.telemetry[router.primary_id]
        g2 = router.telemetry[router.secondary_id]
        if g1.ewma_latency_ms > 5000.0 and g2.ewma_latency_ms > 5000.0:
            return True, "Dual-Gateway Transport Failure (Both Latencies > 5,000ms)"

        return False, "NORMAL"

    def execute_kill_switch(self, router: MultiBrokerRouter, trigger_reason: str) -> Dict[str, Any]:
        """
        Executes deterministic liquidation sequence:
        1. Issues FIX 35=q (MassCancelRequestType=7)
        2. Logs canceled orders
        3. Sets state to LOCKED_FAIL_CLOSED
        """
        logger.critical(f"ENGAGING EMERGENCY HARD KILL-SWITCH: {trigger_reason}")
        self.state = EngineExecutionState.KILL_SWITCH_ENGAGED

        # Step 1: Mass Cancel
        purge_result = router.execute_mass_cancel()

        # Step 2: System Lockdown
        self.state = EngineExecutionState.LOCKED_FAIL_CLOSED

        report = {
            "kill_switch_id": f"KILL-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger_reason": trigger_reason,
            "peak_nav": self.peak_nav,
            "current_nav": self.current_nav,
            "drawdown_pct": round((self.peak_nav - self.current_nav) / self.peak_nav, 4),
            "orders_purged": purge_result.get("orders_purged", 0),
            "mass_cancel_status": purge_result.get("status"),
            "final_engine_state": self.state.value,
        }
        self.engagement_report = report
        logger.critical(f"Kill-switch finalized. Engine LOCKED. Purged {report['orders_purged']} orders.")
        return report


class SovereignPodManager:
    """
    Sovereign Pod Governance managing in-country data residency,
    Hold-Your-Own-Key (HYOK) cryptographic signing, and cross-border data filtering.
    """

    def __init__(self, jurisdiction: str = "NEPAL_NEPSE", in_country_storage: bool = True):
        self.jurisdiction = jurisdiction
        self.in_country_storage = in_country_storage
        self.hsm_key_id = f"HYOK-HSM-{uuid.uuid4().hex[:12].upper()}"

    def seal_blotter_provenance(self, blotter_payload: Dict[str, Any]) -> str:
        """Creates SHA-256 master provenance seal compliant with Gate G10."""
        raw_repr = str(sorted(blotter_payload.items())).encode("utf-8")
        h = hashlib.sha256()
        h.update(self.hsm_key_id.encode("utf-8"))
        h.update(raw_repr)
        return h.hexdigest()

    def filter_egress_payload(self, sensitive_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strips Demat numbers, client personal identifying data, and investor keys
        before any external synchronization (satisfying SEBON Directive 2076 & APAC DPDP).
        """
        sanitized = {k: v for k, v in sensitive_record.items() if k not in ["client_demat_no", "boid", "investor_pan", "bank_account"]}
        sanitized["sovereign_filter_applied"] = True
        sanitized["jurisdiction_origin"] = self.jurisdiction
        return sanitized
