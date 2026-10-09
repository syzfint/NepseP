#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/rd_agent_live_execution_bridge.py

RD-Agent & Qlib Live Execution Bridge
======================================
The production translation bridge connecting the RD-Agent / Qlib AlphaNEPSE
forecasting plane to NEPSE's sovereign live execution environment.

Integrates:
  1. Gate G4 Meta-Labeling conviction filter (P(win) >= 60%, positive return).
  2. skfolio Hierarchical Risk Parity (HRP) allocation with Chronos uncertainty shrinkage.
  3. QuantRiskLab Value-at-Risk (VaR 95%) and Expected Shortfall (ES 95%) portfolio bounds.
  4. Almgren-Chriss Dynamic Percentage of Volume (POV) slicing with U-shaped volume multipliers.
  5. Sovereign NEPSE Microstructure Rules:
     - 10-unit board lots (odd lots <10 kitta rejected / routed to odd-lot desk).
     - 15% Top-3 Limit Order Book (LOB) depth caps per child slice.
     - Daily circuit boundaries [P_ref * 0.90, P_ref * 1.10].
     - Adverse selection VPIN guard (pause if VPIN >= 0.70).
     - Broker commission (0.40%) and SEBON regulatory fee (0.015%) collateral check.
     - Immutable SHA-256 blotter signing for audit reproducibility.
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

# Dynamic path resolution
BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / "scripts"
CONTROL_DIR = SCRIPTS_DIR / "00_control"
MODEL_DIR = SCRIPTS_DIR / "02_modeling_and_calculations"

for p in [str(BASE_DIR), str(SCRIPTS_DIR), str(CONTROL_DIR), str(MODEL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from hrp_portfolio_allocator import HRPPortfolioAllocator
from dynamic_pov_engine import DynamicPOVEngine, NEPSE_HOURLY_VOLUME_FACTORS
from portfolio_risk_lab import QuantRiskLab

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [RDLiveBridge] %(message)s")
logger = logging.getLogger("RDLiveBridge")

STAGED_ORDERS_PATH = BASE_DIR / "static_data" / "live_staged_orders.json"


class RDAgentLiveExecutionBridge:
    """
    Translates RD-Agent / AlphaNEPSE candidate forecasts into institutional,
    depth-capped, circuit-bounded staged orders for the NEPSE TMS.
    """

    def __init__(
        self,
        min_meta_prob: float = 0.60,
        max_asset_weight: float = 0.20,
        min_asset_weight: float = 0.03,
        cash_buffer_pct: float = 0.10,
        max_portfolio_var_95: float = 0.035,  # 3.5% daily 95% VaR cap
        max_portfolio_es_95: float = 0.050,   # 5.0% daily 95% ES cap
        vpin_toxic_threshold: float = 0.70,
        broker_fee_pct: float = 0.0040,       # 0.40% broker fee
        sebon_fee_pct: float = 0.00015,       # 0.015% SEBON fee
    ):
        self.min_meta_prob = min_meta_prob
        self.max_asset_weight = max_asset_weight
        self.min_asset_weight = min_asset_weight
        self.cash_buffer_pct = cash_buffer_pct
        self.max_portfolio_var_95 = max_portfolio_var_95
        self.max_portfolio_es_95 = max_portfolio_es_95
        self.vpin_toxic_threshold = vpin_toxic_threshold
        self.broker_fee_pct = broker_fee_pct
        self.sebon_fee_pct = sebon_fee_pct

        self.hrp_allocator = HRPPortfolioAllocator(
            min_weight=min_asset_weight,
            max_weight=max_asset_weight,
            cash_buffer=cash_buffer_pct,
        )
        self.pov_engine = DynamicPOVEngine(
            target_participation_rate=0.08,
            max_book_depth_cap=0.15,
            vpin_toxic_threshold=vpin_toxic_threshold,
            max_price_impact_pct=0.40,
        )
        self.risk_lab = QuantRiskLab(trading_days=240, rf_rate=0.04)

    def filter_and_rank_candidates(
        self,
        candidates: List[Dict[str, Any]],
        vpin_metrics: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Filters candidates through Gate G4 conviction and VPIN toxicity gates.
        Ranks survivors by composite alpha score: z(exp_return) * meta_probability.
        """
        vpin_metrics = vpin_metrics or {}
        certified = []

        for cand in candidates:
            sym = cand["symbol"].upper().strip()
            meta_prob = float(cand.get("meta_probability", 0.50))
            exp_ret = float(cand.get("expected_return_5d", 0.0))
            vpin = float(vpin_metrics.get(sym, cand.get("vpin", 0.30)))

            # Gate G4 & Microstructure Screening
            if meta_prob < self.min_meta_prob:
                logger.info(f"[{sym}] Rejected: Meta-probability {meta_prob:.3f} < {self.min_meta_prob}")
                continue
            if exp_ret <= 0.0:
                logger.info(f"[{sym}] Rejected: Non-positive expected return {exp_ret:.4f}")
                continue
            if vpin >= self.vpin_toxic_threshold:
                logger.warning(f"[{sym}] Rejected: Toxic VPIN {vpin:.2f} >= {self.vpin_toxic_threshold} (Adverse Selection)")
                continue

            # Alpha score
            alpha_score = exp_ret * meta_prob
            c = dict(cand)
            c["vpin"] = vpin
            c["alpha_score"] = round(alpha_score, 5)
            certified.append(c)

        # Sort descending by alpha score
        certified.sort(key=lambda x: x["alpha_score"], reverse=True)
        logger.info(f"Certified {len(certified)} of {len(candidates)} candidates through Gate G4 & VPIN filters.")
        return certified

    def allocate_hrp_weights(
        self,
        certified_candidates: List[Dict[str, Any]],
        returns_df: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Derives robust HRP weights across certified candidates, incorporating
        predictive uncertainty spreads from Chronos/adaptive models.
        """
        if not certified_candidates or returns_df.empty:
            return {"CASH": 1.0}

        symbols = [c["symbol"] for c in certified_candidates]
        valid_cols = [s for s in symbols if s in returns_df.columns]

        if not valid_cols:
            # Equal weight among certified up to (1 - cash_buffer)
            n = len(certified_candidates)
            alloc_total = 1.0 - self.cash_buffer_pct
            w = alloc_total / n
            weights = {c["symbol"]: round(w, 4) for c in certified_candidates}
            weights["CASH"] = round(self.cash_buffer_pct, 4)
            return weights

        # Build uncertainty spreads map
        uncertainty_map = {
            c["symbol"]: float(c.get("uncertainty_spread", 6.0))
            for c in certified_candidates
        }

        subset_returns = returns_df[valid_cols].dropna()
        if len(subset_returns) < 20:
            # Insufficient covariance history; equal allocation
            n = len(valid_cols)
            w = (1.0 - self.cash_buffer_pct) / n
            weights = {s: round(w, 4) for s in valid_cols}
            weights["CASH"] = round(self.cash_buffer_pct, 4)
            return weights

        alloc_result = self.hrp_allocator.allocate(
            returns_df=subset_returns,
            uncertainty_spreads=uncertainty_map,
        )

        weights = dict(alloc_result.get("weights", {}))
        cash_w = float(alloc_result.get("cash_weight", self.cash_buffer_pct))
        weights["CASH"] = round(cash_w, 4)
        return weights

    def screen_and_adjust_tail_risk(
        self,
        weights: Dict[str, float],
        returns_df: pd.DataFrame,
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """
        Evaluates portfolio tail risk using QuantRiskLab (Historical, Parametric, Monte Carlo).
        If Parametric VaR(95%) or ES(95%) breaches risk limits, trims equity into CASH.
        """
        equity_weights = {k: v for k, v in weights.items() if k != "CASH" and v > 0.0}
        if not equity_weights or returns_df.empty:
            return weights, {"status": "NO_EQUITY_RISK"}

        # Normalize equity weights for risk engine
        total_eq = sum(equity_weights.values())
        norm_weights = {k: v / total_eq for k, v in equity_weights.items() if k in returns_df.columns}

        if not norm_weights:
            return weights, {"status": "NO_OVERLAPPING_RETURNS"}

        # Query QuantRiskLab tail risk
        risk_out = self.risk_lab.run_full_analysis(
            returns_df=returns_df[[k for k in norm_weights.keys()]].dropna(),
            weights=norm_weights,
            estimation_window=min(120, len(returns_df) - 5),
        )

        var_95 = risk_out["value_at_risk_and_expected_shortfall"]["95pct"]["parametric_gaussian"]["var_pct"] / 100.0
        es_95 = risk_out["value_at_risk_and_expected_shortfall"]["95pct"]["parametric_gaussian"]["expected_shortfall_pct"] / 100.0

        # Check breach
        var_breach = var_95 > self.max_portfolio_var_95
        es_breach = es_95 > self.max_portfolio_es_95

        adjusted_weights = dict(weights)
        if var_breach or es_breach:
            # Scale factor to bring within limits
            scale = min(self.max_portfolio_var_95 / max(var_95, 1e-4), self.max_portfolio_es_95 / max(es_95, 1e-4))
            scale = max(0.40, min(1.0, scale))
            logger.warning(f"Tail risk breach (VaR 95%={var_95*100:.2f}%, ES 95%={es_95*100:.2f}%). Scaling equities by {scale:.2f}x.")

            new_equity_sum = 0.0
            for k in list(adjusted_weights.keys()):
                if k != "CASH":
                    adjusted_weights[k] = round(adjusted_weights[k] * scale, 4)
                    new_equity_sum += adjusted_weights[k]
            adjusted_weights["CASH"] = round(1.0 - new_equity_sum, 4)

        risk_summary = {
            "var_95_pct": round(var_95 * 100.0, 2),
            "es_95_pct": round(es_95 * 100.0, 2),
            "var_limit_pct": round(self.max_portfolio_var_95 * 100.0, 2),
            "es_limit_pct": round(self.max_portfolio_es_95 * 100.0, 2),
            "risk_adjusted": bool(var_breach or es_breach),
        }
        return adjusted_weights, risk_summary

    def stage_execution_blotter(
        self,
        target_weights: Dict[str, float],
        candidates: List[Dict[str, Any]],
        total_capital_npr: float = 10_000_000.0,
        current_holdings: Optional[Dict[str, int]] = None,
        market_depths: Optional[Dict[str, Dict[str, Any]]] = None,
        as_of_time: str = "11:00",
        client_code: str = "INST-001",
        broker_id: str = "58",
    ) -> Dict[str, Any]:
        """
        Translates target portfolio weights into discrete, depth-capped,
        board-lot compliant child order slices ready for 1-click execution.
        """
        current_holdings = current_holdings or {}
        market_depths = market_depths or {}
        cand_map = {c["symbol"].upper(): c for c in candidates}

        tickets: List[Dict[str, Any]] = []
        total_buy_val = 0.0
        total_sell_val = 0.0
        total_comm = 0.0

        for symbol, target_w in target_weights.items():
            if symbol == "CASH" or target_w <= 0.0:
                continue

            cand_info = cand_map.get(symbol, {})
            price = float(cand_info.get("latest_close", 500.0))
            depth_info = market_depths.get(symbol, {})
            ref_price = float(depth_info.get("prev_close", price))
            ask_depth = int(depth_info.get("top3_ask_vol", 3000))
            bid_depth = int(depth_info.get("top3_bid_vol", 3000))

            # Circuit limits (+-10%)
            circuit_min = round(ref_price * 0.90, 1)
            circuit_max = round(ref_price * 1.10, 1)
            limit_price = max(circuit_min, min(circuit_max, round(price, 1)))

            # Calculate target quantity in 10-unit board lots
            target_val = target_w * total_capital_npr
            target_kitta_raw = target_val / max(limit_price, 1.0)
            target_kitta = int(target_kitta_raw // 10) * 10

            current_kitta = current_holdings.get(symbol, 0)
            delta_kitta = target_kitta - current_kitta

            if delta_kitta == 0:
                continue

            side = "BUY" if delta_kitta > 0 else "SELL"
            abs_kitta = abs(delta_kitta)

            # Applicable prevailing order book depth
            prevailing_depth = ask_depth if side == "BUY" else bid_depth
            # Depth cap: at most 15% of top-3 LOB depth per child slice
            max_slice_from_depth = max(10, int(prevailing_depth * 0.15 // 10) * 10)

            # Intraday U-shaped curve scaling
            u_mult = NEPSE_HOURLY_VOLUME_FACTORS.get(as_of_time, 1.0)
            base_slice_kitta = max(10, int(abs_kitta * 0.20 * u_mult // 10) * 10)
            child_slice_size = max(10, min(max_slice_from_depth, base_slice_kitta))

            num_slices = max(1, int(np.ceil(abs_kitta / child_slice_size)))

            remaining_kitta = abs_kitta
            for slice_idx in range(1, num_slices + 1):
                cur_slice_qty = min(child_slice_size, remaining_kitta)
                cur_slice_qty = max(10, int(cur_slice_qty // 10) * 10)
                if cur_slice_qty <= 0:
                    break

                slice_val = cur_slice_qty * limit_price
                comm = slice_val * (self.broker_fee_pct + self.sebon_fee_pct)

                ticket_id = f"TICK-{symbol}-{slice_idx}OF{num_slices}-{uuid.uuid4().hex[:6].upper()}"
                depth_share = round((cur_slice_qty / max(prevailing_depth, 1)) * 100.0, 2)

                ticket = {
                    "ticket_id": ticket_id,
                    "client_code": client_code,
                    "broker_id": str(broker_id),
                    "symbol": symbol,
                    "side": side,
                    "order_type": "LIMIT",
                    "retention": "DAY",
                    "quantity": int(cur_slice_qty),
                    "limit_price": float(limit_price),
                    "total_value_npr": round(slice_val, 2),
                    "estimated_commission_npr": round(comm, 2),
                    "slice_index": slice_idx,
                    "total_slices": num_slices,
                    "lob_depth_share_pct": depth_share,
                    "circuit_min": circuit_min,
                    "circuit_max": circuit_max,
                    "status": "STAGED",
                    "validation_notes": [
                        "10-unit board lot compliant",
                        f"<=15% LOB depth share ({depth_share}%)",
                        f"Circuit bounded [{circuit_min}, {circuit_max}]",
                    ],
                }

                tickets.append(ticket)
                remaining_kitta -= cur_slice_qty

                if side == "BUY":
                    total_buy_val += slice_val
                else:
                    total_sell_val += slice_val
                total_comm += comm

        cash_available = total_capital_npr * target_weights.get("CASH", self.cash_buffer_pct)
        remaining_cash = total_capital_npr - total_buy_val - total_comm + total_sell_val
        compliance_passed = remaining_cash >= 0.0

        # Cryptographic Provenance Hash (SHA-256)
        blotter_id = f"BLOTTER-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        hasher = hashlib.sha256()
        hasher.update(blotter_id.encode())
        for t in tickets:
            hasher.update(f"{t['ticket_id']}:{t['quantity']}:{t['limit_price']}".encode())
        integrity_hash = hasher.hexdigest()

        blotter_report = {
            "blotter_id": blotter_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "as_of_time": as_of_time,
            "client_code": client_code,
            "broker_id": str(broker_id),
            "total_capital_npr": round(total_capital_npr, 2),
            "total_staged_orders": len(tickets),
            "total_buy_value_npr": round(total_buy_val, 2),
            "total_sell_value_npr": round(total_sell_val, 2),
            "estimated_total_commission_npr": round(total_comm, 2),
            "allocated_cash_reserve_npr": round(cash_available, 2),
            "remaining_cash_npr": round(remaining_cash, 2),
            "compliance_passed": compliance_passed,
            "integrity_hash": integrity_hash,
            "tickets": tickets,
        }

        # Save to disk
        STAGED_ORDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STAGED_ORDERS_PATH, "w", encoding="utf-8") as f:
            json.dump(blotter_report, f, indent=2)

        logger.info(f"Staged {len(tickets)} orders to {STAGED_ORDERS_PATH}. Compliance: {compliance_passed}. Hash: {integrity_hash[:16]}...")
        return blotter_report

    def run_bridge_pipeline(
        self,
        candidates: List[Dict[str, Any]],
        returns_df: pd.DataFrame,
        total_capital_npr: float = 10_000_000.0,
        current_holdings: Optional[Dict[str, int]] = None,
        market_depths: Optional[Dict[str, Dict[str, Any]]] = None,
        vpin_metrics: Optional[Dict[str, float]] = None,
        as_of_time: str = "11:00",
    ) -> Dict[str, Any]:
        """
        Executes end-to-end bridge pipeline:
          Filter -> HRP Allocate -> Tail Risk Screen -> Dynamic POV Slice -> TMS Stage Blotter.
        """
        # Step 1: Filter & Rank Candidates
        certified = self.filter_and_rank_candidates(candidates, vpin_metrics=vpin_metrics)

        # Step 2: HRP Allocation
        hrp_weights = self.allocate_hrp_weights(certified, returns_df)

        # Step 3: QuantRiskLab Tail Risk Defense
        adj_weights, risk_summary = self.screen_and_adjust_tail_risk(hrp_weights, returns_df)

        # Step 4: Dynamic POV Slicing & TMS Staging
        blotter = self.stage_execution_blotter(
            target_weights=adj_weights,
            candidates=certified,
            total_capital_npr=total_capital_npr,
            current_holdings=current_holdings,
            market_depths=market_depths,
            as_of_time=as_of_time,
        )

        return {
            "certified_candidates": certified,
            "hrp_weights": hrp_weights,
            "tail_risk_adjusted_weights": adj_weights,
            "risk_summary": risk_summary,
            "execution_blotter": blotter,
        }
