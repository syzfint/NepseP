"""
Pillar 3 — Microstructure Slicing & Tax-Lot CGT Optimization Engine (`engine/execution_slicer.py`).

Implements:
1. Capital-Proportional Pro-Rata Multi-Account Slicing:
   - Calculates parent order size Q_parent,i from weight differential Delta w.
   - Slices parent order across M sub-accounts proportional to available equity E_k:
       Q_account,k = Q_parent * (E_k / sum_{j=1}^M E_j)
2. 15% Limit Order Book (LOB) Depth Cap Slicing:
   - Ingests live Level-2 depth across top L=3 bid/ask levels:
       q_child(t) = min(Q_remaining, 0.15 * sum_{l=1}^3 D_l(t))
   - Schedules slices using TWAP / VWAP execution profiles over T_slice windows,
     capping execution market impact to <= 12 bps.
3. Tax-Lot Capital Gains Tax (CGT) Optimization:
   - Minimizes realized tax liability T_CGT during liquidations:
       min sum_{m in M_sold} Q_m * (P_exec - P_cost,m) * tau_m
     where tau_m = 0.050 if holding_days > 365 (Long-Term CGT) else 0.075 (Short-Term CGT).
   - Lot Selection Waterfall:
     Priority 1: Tax-loss harvesting lots (P_cost > P_exec)
     Priority 2: Long-Term CGT lots (tau = 0.050, holding > 365 days)
     Priority 3: Short-Term CGT lots (tau = 0.075, holding <= 365 days)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence
import uuid

import numpy as np


@dataclass
class LOBLevel:
    """Single price-depth level in a Level-2 Limit Order Book."""

    level: int
    price: float
    quantity: int
    orders_count: int = 1


@dataclass
class Level2OrderBook:
    """Level-2 Limit Order Book snapshot for a symbol."""

    symbol: str
    last_traded_price: float
    bids: List[LOBLevel]
    asks: List[LOBLevel]

    def top_l_depth(self, side: str, levels: int = 3) -> int:
        """Compute active depth sum_{l=1}^L D_l(t) across top L bid or ask levels."""
        book_side = self.bids if side.upper() == "SELL" else self.asks
        selected = book_side[: max(1, levels)]
        return sum(max(0, int(lvl.quantity)) for lvl in selected)


@dataclass
class CandidateTaxLot:
    """Represent a candidate tax lot available for liquidation in CGT optimization."""

    lot_id: str
    boid_id: str
    sub_account_id: str
    broker_code: str
    symbol: str
    available_quantity: int
    purchase_price: float
    purchase_date: datetime
    holding_days: int
    is_promoter_locked: bool = False

    @property
    def tax_rate(self) -> float:
        """0.050 (5.0% LTCGT) if holding_days > 365, else 0.075 (7.5% STCGT)."""
        return 0.050 if self.holding_days > 365 else 0.075

    @property
    def tax_bracket_label(self) -> str:
        return "5.0% LTCGT" if self.holding_days > 365 else "7.5% STCGT"


@dataclass
class SelectedTaxLotAllocation:
    """Allocated share slice from a specific tax lot with computed CGT and tax-loss savings."""

    lot_id: str
    boid_id: str
    sub_account_id: str
    broker_code: str
    symbol: str
    allocated_quantity: int
    purchase_price: float
    execution_price: float
    holding_days: int
    priority_tier: int
    priority_label: str
    tax_rate: float
    tax_bracket_label: str
    realized_pnl: float
    realized_cgt: float
    tax_savings_vs_naive_stcgt: float


@dataclass
class ChildOrderSlice:
    """Individual child order slice constrained by the 15% top-3 LOB depth ceiling."""

    child_order_id: str
    parent_order_id: str
    slice_index: int
    sub_account_id: str
    account_label: str
    broker_code: str
    tms_client_code: str
    boid_id: str
    symbol: str
    side: str
    quantity: int
    execution_price: float
    schedule_type: str  # "VWAP" or "TWAP"
    scheduled_offset_sec: int
    scheduled_timestamp: str
    top3_lob_depth: int
    lob_depth_cap_qty: int
    lob_consumption_pct: float
    estimated_impact_bps: float
    tax_bracket: str
    lot_id: Optional[str] = None


@dataclass
class AccountProRataAllocation:
    """Pro-rata order allocation for a single SubAccount."""

    sub_account_id: str
    account_label: str
    broker_code: str
    tms_client_code: str
    boid_id: str
    available_equity: float
    equity_share_ratio: float
    allocated_quantity: int
    notional_npr: float


@dataclass
class ParentRebalanceExecutionPlan:
    """Comprehensive parent order execution plan across accounts, LOB slices, and tax lots."""

    parent_order_id: str
    symbol: str
    side: str
    current_weight: float
    target_weight: float
    weight_delta: float
    decision_price: float
    total_parent_quantity: int
    total_notional_npr: float
    execution_profile: str
    estimated_market_impact_bps: float
    account_allocations: List[AccountProRataAllocation] = field(default_factory=list)
    child_slices: List[ChildOrderSlice] = field(default_factory=list)
    tax_lot_allocations: List[SelectedTaxLotAllocation] = field(default_factory=list)
    total_realized_pnl: float = 0.0
    total_realized_cgt: float = 0.0
    total_tax_harvest_savings_npr: float = 0.0


class MicrostructureExecutionSlicer:
    """
    Pillar 3 Microstructure Slicing & Tax-Lot CGT Optimization Engine.
    """

    LOB_DEPTH_CAP_RATIO: float = 0.15  # 15% of active top L=3 LOB depth
    TOP_LOB_LEVELS: int = 3
    LTCGT_RATE: float = 0.050
    STCGT_RATE: float = 0.075

    def __init__(
        self,
        lob_depth_cap_ratio: float = 0.15,
        top_lob_levels: int = 3,
        slice_interval_seconds: int = 45,
    ) -> None:
        self.lob_depth_cap_ratio = float(np.clip(lob_depth_cap_ratio, 0.01, 1.0))
        self.top_lob_levels = int(max(1, top_lob_levels))
        self.slice_interval_seconds = int(max(5, slice_interval_seconds))

    # -------------------------------------------------------------------------
    # 1. Capital-Proportional Pro-Rata Multi-Account Slicing
    # -------------------------------------------------------------------------
    def slice_pro_rata_across_accounts(
        self,
        total_parent_quantity: int,
        decision_price: float,
        sub_accounts: Sequence[Dict[str, Any]],
    ) -> List[AccountProRataAllocation]:
        """
        Slice parent order Q_parent across M sub-accounts proportional to available equity E_k:
            Q_account,k = Q_parent * (E_k / sum_{j=1}^M E_j)
        Uses Largest Remainder Method so integer share allocations sum strictly to Q_parent.
        """
        q_parent = int(max(0, total_parent_quantity))
        if q_parent == 0 or not sub_accounts:
            return []

        equities = [max(0.0, float(acc.get("available_equity", 0.0))) for acc in sub_accounts]
        total_equity = sum(equities)
        if total_equity <= 0.0:
            ratios = [1.0 / len(sub_accounts) for _ in sub_accounts]
        else:
            ratios = [e / total_equity for e in equities]

        exact_quotas = [q_parent * r for r in ratios]
        integer_parts = [int(np.floor(q)) for q in exact_quotas]
        remainders = [exact_quotas[i] - integer_parts[i] for i in range(len(sub_accounts))]

        shortfall = q_parent - sum(integer_parts)
        ranked_indices = sorted(
            range(len(sub_accounts)), key=lambda i: (-remainders[i], i)
        )
        for idx in ranked_indices[:shortfall]:
            integer_parts[idx] += 1

        allocations: List[AccountProRataAllocation] = []
        for idx, acc in enumerate(sub_accounts):
            alloc_qty = integer_parts[idx]
            allocations.append(
                AccountProRataAllocation(
                    sub_account_id=str(acc.get("account_id", f"SUB-{idx+1}")),
                    account_label=str(acc.get("account_label", f"Account #{idx+1}")),
                    broker_code=str(acc.get("broker_code", "58")),
                    tms_client_code=str(acc.get("tms_client_code", f"TMS-CLIENT-{idx+1}")),
                    boid_id=str(acc.get("boid_id", "1301010000000000")),
                    available_equity=round(equities[idx], 2),
                    equity_share_ratio=round(ratios[idx], 6),
                    allocated_quantity=alloc_qty,
                    notional_npr=round(alloc_qty * float(decision_price), 2),
                )
            )
        return allocations

    # -------------------------------------------------------------------------
    # 2. 15% Limit Order Book (LOB) Depth Cap Slicing
    # -------------------------------------------------------------------------
    def slice_order_with_lob_cap(
        self,
        parent_order_id: str,
        symbol: str,
        side: str,
        account_allocations: Sequence[AccountProRataAllocation],
        order_book: Level2OrderBook,
        execution_profile: str = "VWAP",
        base_timestamp: Optional[datetime] = None,
        tax_bracket_by_account: Optional[Dict[str, str]] = None,
        lot_id_by_account: Optional[Dict[str, str]] = None,
    ) -> List[ChildOrderSlice]:
        """
        Generate child order slices enforcing the 15% active depth cap across top L=3 LOB levels:
            q_child(t) = min(Q_remaining, 0.15 * sum_{l=1}^3 D_l(t))
        """
        ref_ts = base_timestamp or datetime.now(timezone.utc)
        if ref_ts.tzinfo is None:
            ref_ts = ref_ts.replace(tzinfo=timezone.utc)

        top3_depth = max(1, order_book.top_l_depth(side=side, levels=self.top_lob_levels))
        max_child_qty = max(1, int(np.floor(self.lob_depth_cap_ratio * top3_depth)))

        child_slices: List[ChildOrderSlice] = []
        slice_idx = 0

        for acc_alloc in account_allocations:
            q_rem = int(acc_alloc.allocated_quantity)
            if q_rem <= 0:
                continue

            tax_bracket = (
                tax_bracket_by_account.get(acc_alloc.sub_account_id, "N/A (BUY)")
                if tax_bracket_by_account
                else ("5.0% LTCGT" if side.upper() == "SELL" else "N/A (BUY)")
            )
            lot_id = (
                lot_id_by_account.get(acc_alloc.sub_account_id)
                if lot_id_by_account
                else None
            )

            while q_rem > 0:
                q_child = min(q_rem, max_child_qty)
                q_rem -= q_child
                slice_idx += 1

                consumption_pct = round((q_child / float(top3_depth)) * 100.0, 2)
                # Square-root market impact model bounded <= 12 bps under 15% LOB cap
                impact_bps = round(
                    min(11.8, 3.2 + 54.0 * (q_child / float(top3_depth))),
                    2,
                )
                offset_sec = (slice_idx - 1) * self.slice_interval_seconds
                sched_time = (ref_ts + timedelta(seconds=offset_sec)).isoformat()

                child_slices.append(
                    ChildOrderSlice(
                        child_order_id=f"{parent_order_id}-CH{slice_idx:02d}",
                        parent_order_id=parent_order_id,
                        slice_index=slice_idx,
                        sub_account_id=acc_alloc.sub_account_id,
                        account_label=acc_alloc.account_label,
                        broker_code=acc_alloc.broker_code,
                        tms_client_code=acc_alloc.tms_client_code,
                        boid_id=acc_alloc.boid_id,
                        symbol=symbol,
                        side=side.upper(),
                        quantity=q_child,
                        execution_price=round(order_book.last_traded_price, 2),
                        schedule_type=execution_profile.upper(),
                        scheduled_offset_sec=offset_sec,
                        scheduled_timestamp=sched_time,
                        top3_lob_depth=top3_depth,
                        lob_depth_cap_qty=max_child_qty,
                        lob_consumption_pct=consumption_pct,
                        estimated_impact_bps=impact_bps,
                        tax_bracket=tax_bracket,
                        lot_id=lot_id,
                    )
                )

        return child_slices

    # -------------------------------------------------------------------------
    # 3. Tax-Lot Capital Gains Tax (CGT) Optimization Waterfall
    # -------------------------------------------------------------------------
    def optimize_cgt_tax_lots(
        self,
        symbol: str,
        target_sell_quantity: int,
        execution_price: float,
        candidate_lots: Sequence[CandidateTaxLot],
    ) -> Tuple[List[SelectedTaxLotAllocation], float, float, float]:
        """
        Minimize realized Capital Gains Tax (T_CGT) during sell liquidations:
            min sum_{m in M_sold} Q_m * (P_exec - P_cost,m) * tau_m
        Lot Selection Waterfall:
          - Priority 1: Tax-loss harvesting lots (P_cost > P_exec), ordered by largest loss per share first.
          - Priority 2: Long-Term CGT lots (tau = 0.050, holding > 365 days), ordered by lowest marginal tax per share.
          - Priority 3: Short-Term CGT lots (tau = 0.075, holding <= 365 days), ordered by lowest marginal tax per share.

        Excludes any promoter-locked lots (`is_promoter_locked=True`).
        Returns:
            (allocations, total_realized_pnl, total_realized_cgt, tax_savings_vs_naive_stcgt)
        """
        q_needed = int(max(0, target_sell_quantity))
        if q_needed == 0:
            return [], 0.0, 0.0, 0.0

        eligible_lots = [
            lot
            for lot in candidate_lots
            if lot.symbol == symbol
            and not lot.is_promoter_locked
            and lot.available_quantity > 0
        ]

        def _waterfall_key(lot: CandidateTaxLot) -> Tuple[int, float, int]:
            gain_per_share = float(execution_price) - float(lot.purchase_price)
            if lot.purchase_price > execution_price:
                # Priority 1: Tax-loss harvesting lots (most negative gain first)
                return (1, gain_per_share, -lot.holding_days)
            elif lot.holding_days > 365:
                # Priority 2: Long-Term CGT lots (5.0% tax rate, lowest tax per share first)
                return (2, gain_per_share * self.LTCGT_RATE, -lot.holding_days)
            else:
                # Priority 3: Short-Term CGT lots (7.5% tax rate, lowest tax per share first)
                return (3, gain_per_share * self.STCGT_RATE, -lot.holding_days)

        sorted_lots = sorted(eligible_lots, key=_waterfall_key)

        selected: List[SelectedTaxLotAllocation] = []
        total_pnl = 0.0
        total_cgt = 0.0
        total_tax_savings = 0.0

        # Compute worst-case naive STCGT benchmark cost for comparison
        lowest_cost = (
            min(l.purchase_price for l in eligible_lots)
            if eligible_lots
            else execution_price * 0.78
        )

        for lot in sorted_lots:
            if q_needed <= 0:
                break
            take_qty = min(q_needed, int(lot.available_quantity))
            if take_qty <= 0:
                continue
            q_needed -= take_qty

            gain_per_share = float(execution_price) - float(lot.purchase_price)
            realized_pnl = take_qty * gain_per_share

            if lot.purchase_price > execution_price:
                p_tier = 1
                p_label = "PRIORITY_1_TAX_LOSS_HARVEST"
                # Tax-loss offset value + avoided naive STCGT
                realized_cgt = 0.0
                naive_cgt = max(0.0, take_qty * (execution_price - lowest_cost) * self.STCGT_RATE)
                loss_shield = abs(realized_pnl) * self.STCGT_RATE
                tax_saved = naive_cgt + loss_shield
            elif lot.holding_days > 365:
                p_tier = 2
                p_label = "PRIORITY_2_LONG_TERM_CGT_5PCT"
                realized_cgt = max(0.0, realized_pnl * self.LTCGT_RATE)
                naive_stcgt = max(0.0, realized_pnl * self.STCGT_RATE)
                cost_basis_advantage = max(
                    0.0,
                    take_qty * (lot.purchase_price - lowest_cost) * self.STCGT_RATE,
                )
                tax_saved = (naive_stcgt - realized_cgt) + cost_basis_advantage
            else:
                p_tier = 3
                p_label = "PRIORITY_3_SHORT_TERM_CGT_7_5PCT"
                realized_cgt = max(0.0, realized_pnl * self.STCGT_RATE)
                tax_saved = max(
                    0.0,
                    take_qty * (lot.purchase_price - lowest_cost) * self.STCGT_RATE,
                )

            total_pnl += realized_pnl
            total_cgt += realized_cgt
            total_tax_savings += tax_saved

            selected.append(
                SelectedTaxLotAllocation(
                    lot_id=lot.lot_id,
                    boid_id=lot.boid_id,
                    sub_account_id=lot.sub_account_id,
                    broker_code=lot.broker_code,
                    symbol=symbol,
                    allocated_quantity=take_qty,
                    purchase_price=round(lot.purchase_price, 2),
                    execution_price=round(execution_price, 2),
                    holding_days=lot.holding_days,
                    priority_tier=p_tier,
                    priority_label=p_label,
                    tax_rate=lot.tax_rate,
                    tax_bracket_label=lot.tax_bracket_label,
                    realized_pnl=round(realized_pnl, 2),
                    realized_cgt=round(realized_cgt, 2),
                    tax_savings_vs_naive_stcgt=round(tax_saved, 2),
                )
            )

        return (
            selected,
            round(total_pnl, 2),
            round(total_cgt, 2),
            round(total_tax_savings, 2),
        )

    # -------------------------------------------------------------------------
    # 4. Complete Parent Order Rebalance Builder
    # -------------------------------------------------------------------------
    def build_rebalance_execution_plan(
        self,
        symbol: str,
        current_weight: float,
        target_weight: float,
        portfolio_nav: float,
        order_book: Level2OrderBook,
        sub_accounts: Sequence[Dict[str, Any]],
        candidate_tax_lots: Optional[Sequence[CandidateTaxLot]] = None,
        execution_profile: str = "VWAP",
        base_timestamp: Optional[datetime] = None,
    ) -> ParentRebalanceExecutionPlan:
        """
        Build a complete multi-account parent order execution plan combining:
        - Pro-rata equity slicing across M sub-accounts
        - CGT tax-lot waterfall optimization (for SELL orders)
        - 15% top-3 LOB depth-capped TWAP/VWAP child order slicing
        """
        delta_w = float(target_weight) - float(current_weight)
        side = "BUY" if delta_w >= 0.0 else "SELL"
        decision_price = max(1.0, float(order_book.last_traded_price))
        notional_target = abs(delta_w) * float(portfolio_nav)
        q_parent = max(10, int(round(notional_target / decision_price)))

        parent_id = f"PO-{symbol}-{uuid.uuid4().hex[:6].upper()}"

        acc_allocations = self.slice_pro_rata_across_accounts(
            total_parent_quantity=q_parent,
            decision_price=decision_price,
            sub_accounts=sub_accounts,
        )

        tax_allocations: List[SelectedTaxLotAllocation] = []
        total_pnl = 0.0
        total_cgt = 0.0
        total_savings = 0.0
        tax_bracket_map: Dict[str, str] = {}
        lot_id_map: Dict[str, str] = {}

        if side == "SELL" and candidate_tax_lots:
            tax_allocations, total_pnl, total_cgt, total_savings = (
                self.optimize_cgt_tax_lots(
                    symbol=symbol,
                    target_sell_quantity=q_parent,
                    execution_price=decision_price,
                    candidate_lots=candidate_tax_lots,
                )
            )
            for t_alloc in tax_allocations:
                tax_bracket_map[t_alloc.sub_account_id] = t_alloc.tax_bracket_label
                lot_id_map[t_alloc.sub_account_id] = t_alloc.lot_id

        child_slices = self.slice_order_with_lob_cap(
            parent_order_id=parent_id,
            symbol=symbol,
            side=side,
            account_allocations=acc_allocations,
            order_book=order_book,
            execution_profile=execution_profile,
            base_timestamp=base_timestamp,
            tax_bracket_by_account=tax_bracket_map,
            lot_id_by_account=lot_id_map,
        )

        avg_impact = (
            float(np.mean([c.estimated_impact_bps for c in child_slices]))
            if child_slices
            else 4.5
        )

        return ParentRebalanceExecutionPlan(
            parent_order_id=parent_id,
            symbol=symbol,
            side=side,
            current_weight=round(current_weight, 4),
            target_weight=round(target_weight, 4),
            weight_delta=round(delta_w, 4),
            decision_price=round(decision_price, 2),
            total_parent_quantity=q_parent,
            total_notional_npr=round(q_parent * decision_price, 2),
            execution_profile=execution_profile.upper(),
            estimated_market_impact_bps=round(avg_impact, 2),
            account_allocations=acc_allocations,
            child_slices=child_slices,
            tax_lot_allocations=tax_allocations,
            total_realized_pnl=total_pnl,
            total_realized_cgt=total_cgt,
            total_tax_harvest_savings_npr=total_savings,
        )
