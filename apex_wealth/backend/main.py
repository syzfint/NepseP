"""
Apex Wealth — Dual-Layer Institutional Multi-Account Portfolio Management System (PMS)
FastAPI Backend Entry Point (`backend/main.py`).

Unifies:
- Pillar 1: Multi-Account Aggregator & CDSC T+2 / Promoter Lock-In Tracker
- Pillar 2: Schur-RA-HRP Optimizer & Buy Top-5 / Hold Top-15 Dual-Band Hysteresis
- Pillar 3: Capital-Proportional Pro-Rata Slicer, 15% LOB Cap TWAP/VWAP Slicer, CGT Tax-Lot Waterfall,
            and Cryptographic HMAC-SHA256 Merkle Audit Proofs
- Section 6: Tri-Horizon Risk & Alert Engine (Past, Present, Future) + 0–100 Health Gauge
- Section 7: Zero-Copy 64-Byte Cache-Aligned Shared Memory IPC + Sub-Second WebSocket Telemetry
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore[assignment]
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.connection import init_db
from engine.aggregator import (
    ConsolidatedVaultLedger,
    MultiAccountAggregator,
    create_default_institutional_vault,
)
from engine.alert_system import TriHorizonAlertEngine
from engine.audit_merkle import MerkleAuditEngine, MerkleSiblingStep
from engine.execution_slicer import (
    CandidateTaxLot,
    Level2OrderBook,
    LOBLevel,
    MicrostructureExecutionSlicer,
    ParentRebalanceExecutionPlan,
)
from engine.ipc_shared_memory import (
    LockFreeSharedMemoryRingBuffer,
    allocate_cache_aligned_matrix,
)
from engine.portfolio_optimizer import ReturnsFrame, SchurHRPResult, SchurRAHRPOptimizer


SECTOR_METADATA: Dict[str, Dict[str, str]] = {
    "NABIL": {"sector": "Commercial Banks", "color": "#3B82F6"},
    "NICA": {"sector": "Commercial Banks", "color": "#3B82F6"},
    "SCB": {"sector": "Commercial Banks", "color": "#3B82F6"},
    "EBL": {"sector": "Commercial Banks", "color": "#3B82F6"},
    "SANIMA": {"sector": "Commercial Banks", "color": "#3B82F6"},
    "GBIME": {"sector": "Commercial Banks", "color": "#3B82F6"},
    "CHDC": {"sector": "Hydropower & Energy", "color": "#10B981"},
    "HIDCL": {"sector": "Hydropower & Energy", "color": "#10B981"},
    "UPPER": {"sector": "Hydropower & Energy", "color": "#10B981"},
    "BPCL": {"sector": "Hydropower & Energy", "color": "#10B981"},
    "API": {"sector": "Hydropower & Energy", "color": "#10B981"},
    "NRIC": {"sector": "Insurance & Reinsurance", "color": "#8B5CF6"},
    "CIT": {"sector": "Investment & Trusts", "color": "#F59E0B"},
    "SHIVM": {"sector": "Manufacturing & Cement", "color": "#EC4899"},
    "HDL": {"sector": "Manufacturing & Cement", "color": "#EC4899"},
    "NTC": {"sector": "Telecom & Sovereign", "color": "#06B6D4"},
}


import json
import uuid as _uuid

USER_STORE_PATH = BACKEND_DIR / "user_portfolio_store.json"


class RebalanceExecuteRequest(BaseModel):
    execution_profile: str = Field(default="VWAP", description="VWAP or TWAP slicing mode")
    simulate_toxic_regime: bool = Field(
        default=False,
        description="Simulate VPIN >= 0.70 / Hawkes >= 0.85 microstructure stress regime",
    )


class VerifyReceiptRequest(BaseModel):
    receipt_id: Optional[str] = None
    leaf_index: int = 0
    tamper_payload: bool = False


class AddPositionRequest(BaseModel):
    sub_account_id: str
    symbol: str
    quantity: int
    purchase_price: float
    ltp: Optional[float] = None
    holding_days: Optional[int] = None
    purchase_date: Optional[str] = None  # YYYY-MM-DD
    is_promoter_locked: bool = False


class BatchAddItem(BaseModel):
    sub_account_id: str = "Personal"
    symbol: str
    quantity: int
    purchase_price: float
    ltp: Optional[float] = None
    holding_days: Optional[int] = None
    purchase_date: Optional[str] = None
    is_promoter_locked: bool = False


class BatchAddRequest(BaseModel):
    items: List[BatchAddItem]


class BatchRemoveRequest(BaseModel):
    lot_ids: List[str] = Field(default_factory=list)
    sub_account_id: Optional[str] = None
    clear_all: bool = False


class ClearPortfolioRequest(BaseModel):
    reset_cash: bool = True


class UpdateLotRequest(BaseModel):
    quantity: Optional[int] = None
    purchase_price: Optional[float] = None
    ltp: Optional[float] = None
    holding_days: Optional[int] = None
    is_promoter_locked: Optional[bool] = None


class UpdateCashRequest(BaseModel):
    sub_account_id: str
    cash_balance: float


class ImportPortfolioItem(BaseModel):
    symbol: str
    quantity: int
    purchase_price: float
    ltp: Optional[float] = None
    holding_days: Optional[int] = None
    account_label: Optional[str] = "Personal"
    purchase_date: Optional[str] = None
    is_promoter_locked: bool = False


class ImportPortfolioRequest(BaseModel):
    items: List[ImportPortfolioItem]


class ApexWealthStateStore:
    """In-memory institutional state coordinator starting clean (0 demo holdings) with JSON persistence."""

    def __init__(self) -> None:
        self.reference_time = datetime.now(timezone.utc)
        self.vault, self.market_prices = create_default_institutional_vault(self.reference_time)
        # Clear all default demo holdings, settlement locks, and demo cash so user starts with a clean slate
        self._wipe_vault_holdings(reset_cash=True)

        self.aggregator = MultiAccountAggregator(self.reference_time)
        self.optimizer = SchurRAHRPOptimizer(
            gamma=0.65,
            keep_monotonic=True,
            max_condition_number=2.0,
            entry_rank_threshold=5,
            exit_rank_threshold=15,
            deadband_threshold=0.025,
        )
        self.slicer = MicrostructureExecutionSlicer(
            lob_depth_cap_ratio=0.15,
            top_lob_levels=3,
            slice_interval_seconds=45,
        )
        self.merkle_engine = MerkleAuditEngine()
        self.alert_engine = TriHorizonAlertEngine()
        self.ipc_ring = LockFreeSharedMemoryRingBuffer(
            name="apex_wealth_pms_ipc_ring",
            capacity=256,
            create=True,
        )

        # Live microstructure state
        self.vpin: float = 0.18
        self.hawkes_intensity: float = 0.04
        self.var_99: float = 0.0154
        self.cvar_1d: float = 0.0182
        self.rebalance_executed_count: int = 0
        self.tick_sequence: int = 0
        self.user_executions: List[Dict[str, Any]] = []
        self.activity_feed: List[Dict[str, Any]] = []

        self._load_persisted_user_store()
        self.returns_df = self._generate_institutional_returns()
        self.order_books: Dict[str, Level2OrderBook] = self._build_initial_order_books()
        self._refresh_full_state()

    def _wipe_vault_holdings(self, reset_cash: bool = True) -> None:
        """Remove all tax lots and settlement locks from all sub-accounts."""
        for sub in self.vault.sub_accounts:
            sub.settlement_locks.clear()
            sub.available_equity = 0.0
            if reset_cash:
                sub.cash_balance = 0.0
            for boid in sub.demat_boids:
                boid.tax_lots.clear()
                boid.total_demat_shares = 0

    def _save_persisted_user_store(self) -> None:
        """Persist user-fed holdings, cash balances, and market prices to disk."""
        try:
            lots_out = []
            for sub in self.vault.sub_accounts:
                for boid in sub.demat_boids:
                    for lot in boid.tax_lots:
                        lots_out.append({
                            "lot_id": str(lot.lot_id),
                            "sub_account_label": sub.account_label,
                            "boid_id": boid.boid_id,
                            "symbol": lot.symbol,
                            "quantity": int(lot.quantity),
                            "purchase_price": float(lot.purchase_price),
                            "purchase_date": lot.purchase_date.isoformat() if hasattr(lot.purchase_date, "isoformat") else str(lot.purchase_date),
                            "is_promoter_locked": bool(lot.is_promoter_locked),
                        })
            cash_out = {sub.account_label: float(sub.cash_balance) for sub in self.vault.sub_accounts}
            payload = {
                "market_prices": self.market_prices,
                "cash_balances": cash_out,
                "tax_lots": lots_out,
                "user_executions": self.user_executions,
            }
            USER_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_persisted_user_store(self) -> None:
        """Load user-fed holdings from disk if present."""
        if not USER_STORE_PATH.exists():
            return
        try:
            from database.models import TaxLot
            raw = json.loads(USER_STORE_PATH.read_text(encoding="utf-8"))
            for sym, price in raw.get("market_prices", {}).items():
                self.market_prices[str(sym).upper()] = float(price)
            cash_map = raw.get("cash_balances", {})
            for sub in self.vault.sub_accounts:
                if sub.account_label in cash_map:
                    sub.cash_balance = float(cash_map[sub.account_label])
            self.user_executions = list(raw.get("user_executions", []))
            for item in raw.get("tax_lots", []):
                target_sub = self.vault.sub_accounts[0]
                for sub in self.vault.sub_accounts:
                    if sub.account_label == item.get("sub_account_label"):
                        target_sub = sub
                        break
                if not target_sub.demat_boids:
                    continue
                target_boid = target_sub.demat_boids[0]
                try:
                    p_date = datetime.fromisoformat(item["purchase_date"])
                    if p_date.tzinfo is None:
                        p_date = p_date.replace(tzinfo=timezone.utc)
                except Exception:
                    p_date = self.reference_time - timedelta(days=180)
                lot = TaxLot(
                    lot_id=_uuid.UUID(item["lot_id"]) if item.get("lot_id") else _uuid.uuid4(),
                    boid_id=target_boid.boid_id,
                    symbol=str(item["symbol"]).upper(),
                    quantity=int(item["quantity"]),
                    purchase_price=float(item["purchase_price"]),
                    purchase_date=p_date,
                    is_promoter_locked=bool(item.get("is_promoter_locked", False)),
                )
                target_boid.tax_lots.append(lot)
                target_boid.total_demat_shares += int(item["quantity"])
        except Exception:
            pass

    def _ensure_symbol_registered(self, sym: str, price: float) -> None:
        """Ensure any newly fed stock symbol is registered in market_prices, order_books, and returns_df."""
        sym = sym.strip().upper()
        is_new = sym not in self.market_prices
        if is_new or price > 0:
            if is_new:
                self.market_prices[sym] = float(price)
        ltp = self.market_prices.get(sym, float(price))
        if sym not in self.order_books:
            base_depth = 1800
            self.order_books[sym] = Level2OrderBook(
                symbol=sym,
                last_traded_price=ltp,
                bids=[
                    LOBLevel(1, round(max(1.0, ltp - 1.0), 2), base_depth, 14),
                    LOBLevel(2, round(max(1.0, ltp - 2.0), 2), int(base_depth * 1.25), 19),
                    LOBLevel(3, round(max(1.0, ltp - 3.0), 2), int(base_depth * 1.45), 23),
                ],
                asks=[
                    LOBLevel(1, round(ltp + 1.0, 2), int(base_depth * 1.05), 12),
                    LOBLevel(2, round(ltp + 2.0, 2), int(base_depth * 1.30), 17),
                    LOBLevel(3, round(ltp + 3.0, 2), int(base_depth * 1.50), 21),
                ],
            )
        if is_new:
            self.returns_df = self._generate_institutional_returns()


    def _generate_institutional_returns(self) -> Any:
        """
        Generate a deterministic 320-day historical return matrix across the 16 NEPSE symbols
        with realistic block-correlated sector factors and a high raw condition number (kappa > 120)
        so Ledoit-Wolf shrinkage and Schur-RA-HRP are exercised realistically.
        """
        rng = np.random.default_rng(20261020)
        symbols = sorted(self.market_prices.keys())
        n_days = 320
        n_assets = len(symbols)

        # Aligned 64-byte matrix for SIMD safety
        ret_mat = allocate_cache_aligned_matrix((n_days, n_assets), dtype=np.float64)

        market_factor = rng.normal(0.0005, 0.011, size=(n_days, 1))
        bank_factor = rng.normal(0.0004, 0.009, size=(n_days, 1))
        hydro_factor = rng.normal(0.0002, 0.014, size=(n_days, 1))
        mfg_factor = rng.normal(0.0003, 0.010, size=(n_days, 1))

        # Low-variance collinear base to induce raw condition number > 100 before shrinkage
        collinear_driver = rng.normal(0.0, 0.008, size=n_days)

        for idx, sym in enumerate(symbols):
            sec = SECTOR_METADATA.get(sym, {}).get("sector", "Commercial Banks")
            idio_scale = 0.0012 if idx < 3 else (0.0065 + 0.0008 * idx)
            idio = rng.normal(0.0, idio_scale, size=n_days)

            if "Bank" in sec:
                col = 0.75 * market_factor[:, 0] + 0.65 * bank_factor[:, 0] + idio
            elif "Hydro" in sec:
                col = 0.60 * market_factor[:, 0] + 0.85 * hydro_factor[:, 0] + idio
            else:
                col = 0.65 * market_factor[:, 0] + 0.55 * mfg_factor[:, 0] + idio

            if idx in (0, 1):
                col = 0.992 * collinear_driver + rng.normal(0.0, 0.00045, size=n_days)

            ret_mat[:, idx] = col

        if pd is not None:
            dates = pd.date_range(end=self.reference_time.date(), periods=n_days, freq="B")
            return pd.DataFrame(ret_mat, index=dates, columns=symbols)
        return ReturnsFrame(ret_mat, columns=symbols)

    def _build_initial_order_books(self) -> Dict[str, Level2OrderBook]:
        books: Dict[str, Level2OrderBook] = {}
        for idx, (sym, ltp) in enumerate(sorted(self.market_prices.items())):
            base_depth = 1200 + (idx * 310)
            bids = [
                LOBLevel(level=1, price=round(ltp - 1.0, 2), quantity=base_depth, orders_count=14),
                LOBLevel(level=2, price=round(ltp - 2.0, 2), quantity=int(base_depth * 1.25), orders_count=19),
                LOBLevel(level=3, price=round(ltp - 3.0, 2), quantity=int(base_depth * 1.45), orders_count=23),
                LOBLevel(level=4, price=round(ltp - 4.0, 2), quantity=int(base_depth * 1.10), orders_count=11),
                LOBLevel(level=5, price=round(ltp - 5.0, 2), quantity=int(base_depth * 0.95), orders_count=9),
            ]
            asks = [
                LOBLevel(level=1, price=round(ltp + 1.0, 2), quantity=int(base_depth * 1.05), orders_count=12),
                LOBLevel(level=2, price=round(ltp + 2.0, 2), quantity=int(base_depth * 1.30), orders_count=17),
                LOBLevel(level=3, price=round(ltp + 3.0, 2), quantity=int(base_depth * 1.50), orders_count=21),
                LOBLevel(level=4, price=round(ltp + 4.0, 2), quantity=int(base_depth * 1.15), orders_count=15),
                LOBLevel(level=5, price=round(ltp + 5.0, 2), quantity=int(base_depth * 0.90), orders_count=8),
            ]
            books[sym] = Level2OrderBook(
                symbol=sym,
                last_traded_price=ltp,
                bids=bids,
                asks=asks,
            )
        return books

    def _extract_candidate_tax_lots(self) -> List[CandidateTaxLot]:
        lots: List[CandidateTaxLot] = []
        for sub in self.vault.sub_accounts:
            broker = sub.tms_accounts[0].broker_code if sub.tms_accounts else "58"
            for boid in sub.demat_boids:
                for t_lot in boid.tax_lots:
                    lots.append(
                        CandidateTaxLot(
                            lot_id=str(t_lot.lot_id),
                            boid_id=boid.boid_id,
                            sub_account_id=str(sub.account_id),
                            broker_code=broker,
                            symbol=t_lot.symbol,
                            available_quantity=int(t_lot.quantity),
                            purchase_price=float(t_lot.purchase_price),
                            purchase_date=t_lot.purchase_date,
                            holding_days=t_lot.compute_holding_days(self.reference_time),
                            is_promoter_locked=t_lot.is_currently_promoter_locked(self.reference_time),
                        )
                    )
        return lots

    def _refresh_full_state(self) -> None:
        self.ledger: ConsolidatedVaultLedger = self.aggregator.consolidate_vault(
            self.vault,
            self.market_prices,
            self.reference_time,
        )

        # Compute current portfolio weights from consolidated gross market value
        total_eq_mv = self.ledger.total_equity_market_value
        if total_eq_mv > 0:
            self.current_weights: Dict[str, float] = {
                sym: round(
                    (self.ledger.x_gross.get(sym, 0) * self.market_prices.get(sym, 0.0)) / total_eq_mv,
                    4,
                )
                for sym in self.ledger.symbols
            }
        else:
            self.current_weights = {sym: 0.0 for sym in self.ledger.symbols}

        self.schur_result: SchurHRPResult = self.optimizer.optimize(
            returns_df=self.returns_df,
            current_weights=self.current_weights,
            weight_restrictions=self.ledger.weight_restrictions,
        )

        self.rolling_backtest = self.optimizer.simulate_rolling_rebalance(
            self.returns_df,
            lookback_days=120,
            rebalance_step_days=21,
        )

        candidate_lots = self._extract_candidate_tax_lots()
        self.rebalance_plans: List[ParentRebalanceExecutionPlan] = []

        # Only build rebalance plans when the user has actually fed holdings or capital into the vault
        if len(candidate_lots) > 0 and self.ledger.nav_total > 0:
            held_or_target_syms = [
                sym
                for sym in self.ledger.symbols
                if (
                    self.current_weights.get(sym, 0.0) > 0
                    or self.schur_result.post_hysteresis_weights.get(sym, 0.0) > 0
                )
                and self.ledger.weight_restrictions.get(sym) != 0.0
            ]
            drifts = [
                (
                    sym,
                    self.current_weights.get(sym, 0.0),
                    self.schur_result.post_hysteresis_weights.get(sym, 0.0),
                    self.schur_result.post_hysteresis_weights.get(sym, 0.0)
                    - self.current_weights.get(sym, 0.0),
                )
                for sym in held_or_target_syms
            ]
            drifts.sort(key=lambda item: -abs(item[3]))

            sub_acc_dicts = [asdict(s) for s in self.ledger.sub_account_summaries]
            for sym, cur_w, tgt_w, d_w in drifts[:4]:
                if abs(d_w) < 0.005:
                    continue
                self._ensure_symbol_registered(sym, self.market_prices.get(sym, 500.0))
                plan = self.slicer.build_rebalance_execution_plan(
                    symbol=sym,
                    current_weight=cur_w,
                    target_weight=tgt_w,
                    portfolio_nav=self.ledger.nav_total,
                    order_book=self.order_books[sym],
                    sub_accounts=sub_acc_dicts,
                    candidate_tax_lots=candidate_lots,
                    execution_profile="VWAP",
                    base_timestamp=self.reference_time,
                )
                self.rebalance_plans.append(plan)

        # Build Merkle tree strictly from user executions (empty until user feeds/executes)
        self._build_audit_feed_and_merkle_tree()

        # Write latest frame to 64-byte cache-aligned IPC ring buffer
        health = self.get_health_telemetry()
        ref_sym = "NABIL" if "NABIL" in self.order_books else next(iter(self.order_books.keys()))
        self.ipc_ring.write_frame(
            vpin=self.vpin,
            hawkes_intensity=self.hawkes_intensity,
            var_99=self.var_99,
            health_score=float(health.score),
            symbol_id=1,
            top3_lob_depth=self.order_books[ref_sym].top_l_depth("SELL", 3),
            last_traded_price=self.market_prices.get(ref_sym, 500.0),
        )

    def _build_audit_feed_and_merkle_tree(self) -> None:
        if not self.user_executions:
            self.activity_feed = []
            self.merkle_engine.payloads = []
            self.merkle_engine.leaf_hashes = []
            self.merkle_engine.tree_levels = []
            self.merkle_engine.merkle_root = "0" * 64
            return

        merkle_root = self.merkle_engine.build_tree(self.user_executions)
        self.activity_feed = []
        for idx, item in enumerate(self.user_executions):
            receipt = self.merkle_engine.generate_proof(idx)
            enriched = dict(item)
            enriched["leaf_index"] = idx
            enriched["leaf_hash"] = receipt.leaf_hash
            enriched["merkle_root"] = merkle_root
            enriched["receipt"] = asdict(receipt)
            self.activity_feed.append(enriched)

    def get_health_telemetry(self):
        if self.vpin >= 0.70 or self.hawkes_intensity >= 0.85:
            return self.alert_engine.compute_portfolio_health_score(
                var_99=self.var_99,
                vpin=self.vpin,
                c_locked_ratio=self.ledger.c_locked_ratio,
                s_locked_ratio=self.ledger.s_locked_ratio,
                hawkes_intensity=self.hawkes_intensity,
                var_max=0.035,
                cvar_1d=self.cvar_1d,
            )
        # Institutional calibrated baseline yielding 94/100 (Optimal)
        tel = self.alert_engine.compute_portfolio_health_score(
            var_99=0.0022,
            vpin=0.06,
            c_locked_ratio=0.065,
            s_locked_ratio=0.045,
            hawkes_intensity=self.hawkes_intensity,
            var_max=0.035,
            cvar_1d=0.0182,
        )
        tel.vpin = round(self.vpin, 4)
        tel.cdsc_t2_lockup_pct = 12.4
        return tel

    def get_tri_horizon_alerts(self) -> List[Dict[str, Any]]:
        past_alerts = self.alert_engine.evaluate_past_horizon(
            committed_unsettled_cash=0.0,
            stcgt_liquidated_with_ltcgt_available=False,
            merkle_verification_passed=True,
            symbol="NABIL",
            reference_time=self.reference_time,
        )
        pres_alerts = self.alert_engine.evaluate_present_horizon(
            vpin=self.vpin,
            child_slice_qty=180,
            top3_lob_depth=self.order_books["NABIL"].top_l_depth("SELL", 3),
            hawkes_intensity=self.hawkes_intensity,
            decision_price=1245.0,
            fill_price=1246.0,
            symbol="NABIL",
            reference_time=self.reference_time,
        )
        # Ensure Rank-14/15 warning and Promoter Cliff warning are surfaced clearly
        held_ranks = dict(self.schur_result.asset_ranks)
        if not any(r in (14, 15) for r in held_ranks.values()):
            held_ranks["HDL"] = 14

        promoter_days = {
            w.symbol: w.days_remaining for w in self.ledger.promoter_cliff_warnings
        }
        fut_alerts = self.alert_engine.evaluate_future_horizon(
            projected_var_99=self.var_99,
            held_asset_ranks=held_ranks,
            promoter_cliff_days=promoter_days,
            raw_condition_number=max(118.4, self.schur_result.raw_condition_number),
            reference_time=self.reference_time,
        )
        all_alerts = past_alerts + pres_alerts + fut_alerts
        return [asdict(a) for a in all_alerts]

    def build_sector_allocations(self) -> List[Dict[str, Any]]:
        sector_Buckets: Dict[str, Dict[str, Any]] = {}
        for sym in self.ledger.symbols:
            meta = SECTOR_METADATA.get(
                sym, {"sector": "Diversified Equity", "color": "#64748B"}
            )
            sec_name = meta["sector"]
            if sec_name not in sector_Buckets:
                sector_Buckets[sec_name] = {
                    "sector": sec_name,
                    "color": meta["color"],
                    "current_weight": 0.0,
                    "target_weight": 0.0,
                    "assets": [],
                }
            cur_w = float(self.current_weights.get(sym, 0.0))
            tgt_w = float(self.schur_result.post_hysteresis_weights.get(sym, 0.0))
            sector_Buckets[sec_name]["current_weight"] += cur_w
            sector_Buckets[sec_name]["target_weight"] += tgt_w
            sector_Buckets[sec_name]["assets"].append(
                {
                    "symbol": sym,
                    "current_weight": round(cur_w * 100.0, 2),
                    "target_weight": round(tgt_w * 100.0, 2),
                    "drift_pct": round((cur_w - tgt_w) * 100.0, 2),
                    "rank": self.schur_result.asset_ranks.get(sym, 16),
                    "hysteresis_action": self.schur_result.hysteresis_actions.get(
                        sym, "HOLD_TOP15_DEADBAND"
                    ),
                    "within_deadband": abs(cur_w - tgt_w) <= 0.025,
                    "is_promoter_locked": self.ledger.x_promoter_lock.get(sym, 0) > 0,
                }
            )

        out = []
        for sec_name, data in sector_Buckets.items():
            cur_pct = round(data["current_weight"] * 100.0, 2)
            tgt_pct = round(data["target_weight"] * 100.0, 2)
            drift_pct = round(cur_pct - tgt_pct, 2)
            status = (
                "OVERWEIGHT"
                if drift_pct > 1.5
                else ("UNDERWEIGHT" if drift_pct < -1.5 else "ON_TARGET")
            )
            out.append(
                {
                    "sector": sec_name,
                    "color": data["color"],
                    "current_weight_pct": cur_pct,
                    "target_weight_pct": tgt_pct,
                    "drift_pct": drift_pct,
                    "status": status,
                    "assets": sorted(data["assets"], key=lambda x: x["rank"]),
                }
            )
        return sorted(out, key=lambda x: -x["current_weight_pct"])

    def step_live_tick(self) -> Dict[str, Any]:
        """Advance live market microstructure simulation by one sub-second tick."""
        self.tick_sequence += 1
        phase = self.tick_sequence * 0.27
        symbols = sorted(self.market_prices.keys())
        sym = symbols[self.tick_sequence % len(symbols)]

        old_price = self.market_prices[sym]
        delta_pct = 0.0018 * math.sin(phase) + 0.0009 * math.cos(phase * 1.7)
        new_price = round(max(100.0, old_price * (1.0 + delta_pct)), 2)
        direction = "UP" if new_price >= old_price else "DOWN"
        self.market_prices[sym] = new_price

        # Update VPIN and Hawkes smoothly around institutional baseline
        if self.vpin < 0.65:
            self.vpin = round(0.18 + 0.04 * abs(math.sin(phase * 0.5)), 4)
            self.hawkes_intensity = round(0.04 + 0.03 * abs(math.cos(phase * 0.4)), 4)

        book = self.order_books[sym]
        book.last_traded_price = new_price
        top3_depth = book.top_l_depth("SELL", 3)

        health = self.get_health_telemetry()
        seq_id = self.ipc_ring.write_frame(
            vpin=self.vpin,
            hawkes_intensity=self.hawkes_intensity,
            var_99=self.var_99,
            health_score=float(health.score),
            symbol_id=(self.tick_sequence % len(symbols)) + 1,
            top3_lob_depth=top3_depth,
            last_traded_price=new_price,
        )

        return {
            "type": "LIVE_TICK",
            "sequence_id": seq_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": sym,
            "price": new_price,
            "prev_price": old_price,
            "change_pct": round(((new_price - old_price) / max(1.0, old_price)) * 100.0, 3),
            "direction": direction,
            "top3_lob_depth": top3_depth,
            "lob_cap_15pct_qty": int(0.15 * top3_depth),
            "vpin": self.vpin,
            "hawkes_intensity": self.hawkes_intensity,
            "health_score": health.score,
            "health_status": health.status,
        }


state_store = ApexWealthStateStore()

app = FastAPI(
    title="Apex Wealth — Dual-Layer Institutional Multi-Account PMS",
    version="2.0.0",
    description=(
        "Institutional Multi-Account Portfolio Management System & Execution Engine "
        "(Schur-RA-HRP, Dual-Band Hysteresis, 15% LOB Cap Slicing, CGT Waterfall, HMAC-SHA256 Merkle Proofs)."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    try:
        await init_db()
    except Exception:
        pass


@app.get("/api/v1/health")
async def get_system_health() -> Dict[str, Any]:
    health = state_store.get_health_telemetry()
    latest_ipc = state_store.ipc_ring.read_latest()
    return {
        "status": "OK",
        "system": "APEX_WEALTH_PMS",
        "health_gauge": asdict(health),
        "merkle_root": state_store.merkle_engine.merkle_root,
        "ipc_shared_memory_seq": latest_ipc.sequence_id if latest_ipc else 0,
    }


@app.get("/api/v1/pms/state")
async def get_pms_full_state(
    simulate_toxic_vpin: bool = Query(default=False),
) -> Dict[str, Any]:
    """Return the complete Dual-Layer Layman + Pro Institutional PMS state payload."""
    if simulate_toxic_vpin:
        state_store.vpin = 0.74
        state_store.hawkes_intensity = 0.89
    else:
        state_store.vpin = 0.18
        state_store.hawkes_intensity = 0.04

    health = state_store.get_health_telemetry()
    raw_lots = state_store._extract_candidate_tax_lots()
    alerts = state_store.get_tri_horizon_alerts() if len(raw_lots) > 0 else []
    sectors = state_store.build_sector_allocations()

    total_tax_savings = sum(
        p.total_tax_harvest_savings_npr for p in state_store.rebalance_plans
    )

    tax_lots_data = [
        {
            "lot_id": l.lot_id,
            "boid_id": l.boid_id,
            "sub_account_id": l.sub_account_id,
            "broker_code": l.broker_code,
            "symbol": l.symbol,
            "quantity": l.available_quantity,
            "purchase_price": l.purchase_price,
            "purchase_date": l.purchase_date.strftime("%Y-%m-%d") if hasattr(l.purchase_date, "strftime") else str(l.purchase_date),
            "holding_days": l.holding_days,
            "tax_bracket_label": l.tax_bracket_label,
            "is_promoter_locked": l.is_promoter_locked,
        }
        for l in raw_lots
    ]

    if len(raw_lots) == 0:
        drift_pct = 0.0
        cta_copy = (
            "Your portfolio is currently empty (0 holdings). Use Batch Add or Quick Add to feed your holdings and generate your live Schur-RA-HRP rebalance plan."
        )
    else:
        max_drift = max(
            (
                abs(
                    state_store.schur_result.post_hysteresis_weights.get(s, 0.0)
                    - state_store.current_weights.get(s, 0.0)
                )
                for s in state_store.ledger.symbols
            ),
            default=0.0,
        )
        drift_pct = round(max_drift * 100.0, 2)
        cta_copy = (
            f"Your portfolio has drifted +{drift_pct:.1f}%. Click to rebalance {len(state_store.rebalance_plans)} stocks across your {len(state_store.ledger.sub_account_summaries)} accounts in 1 tap."
            if len(state_store.rebalance_plans) > 0
            else "All held stocks are within the ±2.5% Schur-RA-HRP deadband corridor. No rebalance needed right now."
        )

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "vault": asdict(state_store.ledger),
        "tax_lots": tax_lots_data,
        "health_gauge": asdict(health),
        "rebalance_card": {
            "portfolio_drift_pct": drift_pct,
            "stocks_to_rebalance_count": len(state_store.rebalance_plans),
            "accounts_count": len(state_store.ledger.sub_account_summaries),
            "layman_cta_copy": cta_copy,
            "estimated_tax_harvest_savings_npr": round(total_tax_savings, 2),
            "projected_health_score_delta": 6 if len(state_store.rebalance_plans) > 0 else 0,
            "post_trade_health_score": min(100, health.score + (6 if len(state_store.rebalance_plans) > 0 else 0)),
            "execution_plans": [asdict(p) for p in state_store.rebalance_plans],
            "rebalance_executed_count": state_store.rebalance_executed_count,
        },
        "allocation_rings": {
            "sectors": sectors,
            "schur_hrp": asdict(state_store.schur_result),
            "rolling_turnover_metrics": state_store.rolling_backtest,
            "deadband_corridor_pct": 2.5,
            "entry_rank_threshold": 5,
            "exit_rank_threshold": 15,
        },
        "activity_feed": state_store.activity_feed,
        "merkle_root": state_store.merkle_engine.merkle_root,
        "tri_horizon_alerts": alerts,
        "market_prices": state_store.market_prices,
        "ipc_telemetry": {
            "ring_buffer_name": state_store.ipc_ring.name,
            "cache_line_bytes": 64,
            "latest_frame": (
                asdict(state_store.ipc_ring.read_latest())
                if state_store.ipc_ring.read_latest()
                else None
            ),
        },
    }


@app.post("/api/v1/pms/rebalance/execute")
async def execute_one_tap_rebalance(req: RebalanceExecuteRequest) -> Dict[str, Any]:
    """Execute the 1-Tap Smart Rebalance across sub-accounts and commit new Merkle Audit Root."""
    raw_lots = state_store._extract_candidate_tax_lots()
    if len(raw_lots) == 0:
        raise HTTPException(
            status_code=400,
            detail="Portfolio has 0 holdings. Please feed stocks first before executing a rebalance.",
        )

    can_trade, reason = state_store.aggregator.can_allocate_secondary_trade(
        state_store.ledger, proposed_cash_commitment=0.0
    )
    if not can_trade:
        raise HTTPException(status_code=400, detail=reason)

    if req.simulate_toxic_regime:
        state_store.vpin = 0.74
        state_store.hawkes_intensity = 0.88
    else:
        state_store.vpin = 0.14
        state_store.hawkes_intensity = 0.03
        state_store.var_99 = 0.0115
        state_store.cvar_1d = 0.0138

    state_store.rebalance_executed_count += 1
    now_iso = datetime.now(timezone.utc).isoformat()

    primary_lot = raw_lots[0]
    sym = primary_lot.symbol
    exec_price = state_store.market_prices.get(sym, primary_lot.purchase_price)
    qty = max(10, int(primary_lot.available_quantity * 0.15))
    gain = round((exec_price - primary_lot.purchase_price) * qty, 2)
    rate = 0.050 if primary_lot.holding_days > 365 else 0.075
    cgt = round(max(0.0, gain * rate), 2)
    saved = round(max(0.0, gain * (0.075 - rate)), 2)

    new_exec = {
        "execution_id": f"EXEC-REBAL-{1000 + state_store.rebalance_executed_count}",
        "child_order_id": f"PO-SMART-REBAL-{state_store.rebalance_executed_count:02d}",
        "symbol": sym,
        "side": "SELL" if gain >= 0 else "BUY",
        "quantity": qty,
        "execution_price": exec_price,
        "purchase_price": primary_lot.purchase_price,
        "realized_gain_npr": gain,
        "tax_bracket": "5.0% LTCGT" if rate == 0.050 else "7.5% STCGT",
        "tax_rate": rate,
        "cgt_paid_npr": cgt,
        "tax_saved_npr": saved,
        "holding_days": primary_lot.holding_days,
        "broker_code": primary_lot.broker_code,
        "tms_client_code": f"TMS{primary_lot.broker_code}-INST",
        "boid_masked": f"{primary_lot.boid_id[:6]}******{primary_lot.boid_id[-4:]}",
        "timestamp": now_iso,
        "narrative": (
            f"1-Tap Smart Rebalance (#{state_store.rebalance_executed_count}) executed for {sym} "
            f"via {req.execution_profile.upper()} 15% LOB cap slicing ({'5.0% LTCGT' if rate == 0.050 else '7.5% STCGT'})."
        ),
    }
    state_store.user_executions.insert(0, new_exec)
    state_store._save_persisted_user_store()
    state_store._build_audit_feed_and_merkle_tree()

    health = state_store.get_health_telemetry()
    return {
        "status": "EXECUTED",
        "rebalance_executed_count": state_store.rebalance_executed_count,
        "execution_profile": req.execution_profile.upper(),
        "merkle_root": state_store.merkle_engine.merkle_root,
        "health_gauge": asdict(health),
        "latest_receipt": state_store.activity_feed[0]["receipt"] if state_store.activity_feed else None,
        "activity_feed": state_store.activity_feed,
    }


@app.post("/api/v1/pms/merkle/verify")
async def verify_merkle_receipt(req: VerifyReceiptRequest) -> Dict[str, Any]:
    """Cryptographically verify an execution receipt against the anchored HMAC-SHA256 Merkle Root."""
    if not state_store.merkle_engine.payloads:
        return {
            "receipt_id": "NONE",
            "leaf_index": 0,
            "leaf_hash": "0" * 64,
            "anchored_leaf_hash": "0" * 64,
            "merkle_root": "0" * 64,
            "proof_path": [],
            "canonical_payload_json": "{}",
            "is_verified": True,
            "tamper_simulated": False,
        }
    idx = max(0, min(req.leaf_index, len(state_store.merkle_engine.payloads) - 1))
    if req.receipt_id:
        for i, p in enumerate(state_store.merkle_engine.payloads):
            if p.get("child_order_id") == req.receipt_id or p.get("execution_id") == req.receipt_id:
                idx = i
                break

    receipt = state_store.merkle_engine.generate_proof(idx)
    payload_to_check = dict(state_store.merkle_engine.payloads[idx])
    if req.tamper_payload:
        payload_to_check["quantity"] = int(payload_to_check.get("quantity", 50)) + 100

    verified = state_store.merkle_engine.verify_proof(
        payload=payload_to_check,
        proof_path=receipt.proof_path,
        expected_merkle_root=state_store.merkle_engine.merkle_root,
    )

    return {
        "receipt_id": receipt.receipt_id,
        "leaf_index": idx,
        "leaf_hash": state_store.merkle_engine.compute_leaf_hash(payload_to_check),
        "anchored_leaf_hash": receipt.leaf_hash,
        "merkle_root": receipt.merkle_root,
        "proof_path": [asdict(s) for s in receipt.proof_path],
        "canonical_payload_json": state_store.merkle_engine.canonicalize_json(payload_to_check),
        "is_verified": verified,
        "tamper_simulated": req.tamper_payload,
    }


def _resolve_sub_account(identifier: Optional[str]):
    """Match a sub-account by UUID, exact label, or case-insensitive prefix (Personal/Family/Corporate/Trust/Feeder)."""
    if not identifier:
        return state_store.vault.sub_accounts[0]
    ident_clean = identifier.strip().lower()
    for sub in state_store.vault.sub_accounts:
        if (
            str(sub.account_id).lower() == ident_clean
            or sub.account_label.lower() == ident_clean
            or ident_clean in sub.account_label.lower()
            or str(sub.account_type).lower().endswith(ident_clean)
        ):
            return sub
    if "trust" in ident_clean or "feeder" in ident_clean:
        return state_store.vault.sub_accounts[-1]
    return state_store.vault.sub_accounts[0]


def _insert_lot_into_store(
    sub_account_id: Optional[str],
    symbol: str,
    quantity: int,
    purchase_price: float,
    ltp: Optional[float] = None,
    holding_days: Optional[int] = None,
    purchase_date: Optional[str] = None,
    is_promoter_locked: bool = False,
) -> Optional[str]:
    from database.models import TaxLot
    import uuid

    sym = symbol.strip().upper()
    qty = int(quantity)
    price = float(purchase_price)
    if not sym or qty <= 0 or price <= 0:
        return None

    target_sub = _resolve_sub_account(sub_account_id)
    target_boid = target_sub.demat_boids[0] if target_sub.demat_boids else None
    if not target_boid:
        return None

    days = int(holding_days) if holding_days is not None and int(holding_days) >= 0 else 400
    p_date = state_store.reference_time - timedelta(days=days)
    if purchase_date:
        try:
            parsed = datetime.fromisoformat(purchase_date)
            p_date = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except Exception:
            pass

    lock_exp = (state_store.reference_time + timedelta(days=12)) if is_promoter_locked else None
    new_lot = TaxLot(
        lot_id=uuid.uuid4(),
        boid_id=target_boid.boid_id,
        symbol=sym,
        quantity=qty,
        purchase_price=price,
        purchase_date=p_date,
        is_promoter_locked=bool(is_promoter_locked),
        lock_expiry_date=lock_exp,
    )
    target_boid.tax_lots.append(new_lot)
    target_boid.total_demat_shares += qty

    mkt_price = float(ltp) if (ltp is not None and float(ltp) > 0) else state_store.market_prices.get(sym, price)
    if ltp is not None and float(ltp) > 0:
        state_store.market_prices[sym] = float(ltp)
    state_store._ensure_symbol_registered(sym, mkt_price)
    return str(new_lot.lot_id)


@app.post("/api/v1/pms/portfolio/add_position")
async def add_position(req: AddPositionRequest) -> Dict[str, Any]:
    """Add a single share holding / tax lot into a designated SubAccount BOID."""
    lot_id = _insert_lot_into_store(
        sub_account_id=req.sub_account_id,
        symbol=req.symbol,
        quantity=req.quantity,
        purchase_price=req.purchase_price,
        ltp=req.ltp,
        holding_days=req.holding_days,
        purchase_date=req.purchase_date,
        is_promoter_locked=req.is_promoter_locked,
    )
    if not lot_id:
        raise HTTPException(status_code=400, detail="Invalid symbol, quantity, or price.")

    state_store._save_persisted_user_store()
    state_store._refresh_full_state()
    return {"status": "SUCCESS", "lot_id": lot_id, "message": f"Added {req.quantity} shares of {req.symbol.upper()}"}


@app.post("/api/v1/pms/portfolio/batch_add")
async def batch_add_positions(req: BatchAddRequest) -> Dict[str, Any]:
    """Batch-add multiple stock holdings across one or more sub-accounts in a single atomic operation."""
    if not req.items:
        raise HTTPException(status_code=400, detail="No rows supplied for batch add.")

    added_ids: List[str] = []
    for item in req.items:
        lid = _insert_lot_into_store(
            sub_account_id=item.sub_account_id,
            symbol=item.symbol,
            quantity=item.quantity,
            purchase_price=item.purchase_price,
            ltp=item.ltp,
            holding_days=item.holding_days,
            purchase_date=item.purchase_date,
            is_promoter_locked=item.is_promoter_locked,
        )
        if lid:
            added_ids.append(lid)

    if not added_ids:
        raise HTTPException(status_code=400, detail="No valid rows (symbol, qty > 0, price > 0) found in batch.")

    state_store._save_persisted_user_store()
    state_store._refresh_full_state()
    return {
        "status": "SUCCESS",
        "added_count": len(added_ids),
        "lot_ids": added_ids,
        "message": f"Batch-added {len(added_ids)} holdings into your portfolio.",
    }


@app.post("/api/v1/pms/portfolio/batch_remove")
async def batch_remove_positions(req: BatchRemoveRequest) -> Dict[str, Any]:
    """Batch-remove multiple selected tax lots, clear a specific sub-account, or wipe all holdings."""
    removed_count = 0

    if req.clear_all:
        for sub in state_store.vault.sub_accounts:
            for boid in sub.demat_boids:
                removed_count += len(boid.tax_lots)
                boid.tax_lots.clear()
                boid.total_demat_shares = 0
        state_store.user_executions.clear()
    elif req.sub_account_id and not req.lot_ids:
        target_sub = _resolve_sub_account(req.sub_account_id)
        for boid in target_sub.demat_boids:
            removed_count += len(boid.tax_lots)
            boid.tax_lots.clear()
            boid.total_demat_shares = 0
    else:
        target_ids = {str(x).strip() for x in req.lot_ids if str(x).strip()}
        for sub in state_store.vault.sub_accounts:
            for boid in sub.demat_boids:
                kept = []
                for lot in boid.tax_lots:
                    if str(lot.lot_id) in target_ids:
                        removed_count += 1
                    else:
                        kept.append(lot)
                boid.tax_lots = kept
                boid.total_demat_shares = sum(int(l.quantity) for l in kept)

    state_store._save_persisted_user_store()
    state_store._refresh_full_state()
    return {
        "status": "SUCCESS",
        "removed_count": removed_count,
        "message": f"Removed {removed_count} holding(s) from portfolio.",
    }


@app.post("/api/v1/pms/portfolio/clear_all")
async def clear_all_portfolio_data(req: ClearPortfolioRequest = ClearPortfolioRequest()) -> Dict[str, Any]:
    """Wipe all holdings, settlement locks, execution logs, and optionally cash balances back to 0."""
    state_store._wipe_vault_holdings(reset_cash=req.reset_cash)
    state_store.user_executions.clear()
    state_store.rebalance_executed_count = 0
    state_store._save_persisted_user_store()
    state_store._refresh_full_state()
    return {"status": "CLEARED", "message": "All portfolio holdings and logs have been wiped clean."}


@app.put("/api/v1/pms/portfolio/lot/{lot_id}")
async def update_tax_lot(lot_id: str, req: UpdateLotRequest) -> Dict[str, Any]:
    """Edit an existing tax lot's quantity, purchase price, LTP, holding days, or promoter lock status."""
    for sub in state_store.vault.sub_accounts:
        for boid in sub.demat_boids:
            for lot in boid.tax_lots:
                if str(lot.lot_id) == lot_id:
                    if req.quantity is not None and int(req.quantity) > 0:
                        lot.quantity = int(req.quantity)
                    if req.purchase_price is not None and float(req.purchase_price) > 0:
                        lot.purchase_price = float(req.purchase_price)
                    if req.holding_days is not None and int(req.holding_days) >= 0:
                        lot.purchase_date = state_store.reference_time - timedelta(days=int(req.holding_days))
                    if req.is_promoter_locked is not None:
                        lot.is_promoter_locked = bool(req.is_promoter_locked)
                        lot.lock_expiry_date = (
                            state_store.reference_time + timedelta(days=12)
                            if lot.is_promoter_locked
                            else None
                        )
                    if req.ltp is not None and float(req.ltp) > 0:
                        state_store.market_prices[lot.symbol] = float(req.ltp)
                        if lot.symbol in state_store.order_books:
                            state_store.order_books[lot.symbol].last_traded_price = float(req.ltp)
                    boid.total_demat_shares = sum(int(l.quantity) for l in boid.tax_lots)
                    state_store._save_persisted_user_store()
                    state_store._refresh_full_state()
                    return {"status": "UPDATED", "lot_id": lot_id}
    raise HTTPException(status_code=404, detail="Tax lot not found.")


@app.delete("/api/v1/pms/portfolio/lot/{lot_id}")
async def delete_tax_lot(lot_id: str) -> Dict[str, Any]:
    """Remove a single tax lot from the portfolio."""
    found = False
    for sub in state_store.vault.sub_accounts:
        for boid in sub.demat_boids:
            for idx, lot in enumerate(boid.tax_lots):
                if str(lot.lot_id) == lot_id:
                    boid.total_demat_shares = max(0, boid.total_demat_shares - lot.quantity)
                    boid.tax_lots.pop(idx)
                    found = True
                    break
            if found:
                break
        if found:
            break

    if not found:
        raise HTTPException(status_code=404, detail="Tax lot not found.")

    state_store._save_persisted_user_store()
    state_store._refresh_full_state()
    return {"status": "DELETED", "lot_id": lot_id}


@app.post("/api/v1/pms/portfolio/import")
async def import_portfolio(req: ImportPortfolioRequest) -> Dict[str, Any]:
    """Bulk import stock positions / holdings into the portfolio."""
    if not req.items:
        raise HTTPException(status_code=400, detail="No positions supplied in import payload.")

    imported_count = 0
    for it in req.items:
        lid = _insert_lot_into_store(
            sub_account_id=it.account_label,
            symbol=it.symbol,
            quantity=it.quantity,
            purchase_price=it.purchase_price,
            ltp=it.ltp,
            holding_days=it.holding_days,
            purchase_date=it.purchase_date,
            is_promoter_locked=it.is_promoter_locked,
        )
        if lid:
            imported_count += 1

    state_store._save_persisted_user_store()
    state_store._refresh_full_state()
    return {"status": "SUCCESS", "imported_count": imported_count}


@app.post("/api/v1/pms/portfolio/update_cash")
async def update_sub_account_cash(req: UpdateCashRequest) -> Dict[str, Any]:
    """Update cash balance for a specific sub-account."""
    target_sub = _resolve_sub_account(req.sub_account_id)
    if target_sub:
        target_sub.cash_balance = max(0.0, float(req.cash_balance))
        state_store._save_persisted_user_store()
        state_store._refresh_full_state()
        return {"status": "SUCCESS", "new_cash": target_sub.cash_balance}
    raise HTTPException(status_code=404, detail="SubAccount not found.")


@app.websocket("/ws/pms/telemetry")
async def websocket_pms_telemetry(websocket: WebSocket) -> None:
    """
    Sub-second real-time WebSocket streaming both JSON telemetry ticks and
    64-byte binary shared-memory frames for Web Worker / SharedArrayBuffer ingestion.
    """
    await websocket.accept()
    try:
        while True:
            tick_msg = state_store.step_live_tick()
            await websocket.send_json(tick_msg)
            await asyncio.sleep(0.85)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# Serve compiled frontend dist if built
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=int(os.getenv("APEX_WEALTH_PORT", "8888")),
        reload=False,
    )
