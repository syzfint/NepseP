#!/usr/bin/env python3
"""
scripts/00_control/execution_cost_model.py

APEXMARKETENGINE — DYNAMIC IMPLEMENTATION SHORTFALL (IS) & CRYPTOGRAPHIC AUDIT SUITE
===================================================================================
1. Dynamic Implementation Shortfall (IS) Decomposition:
   IS = Execution Cost (Half-Spread) + Market Impact + Opportunity Cost + Fixed Fees

   - Fixed Regulatory/Broker Friction:
     * Tiered Broker Commission (0.40% down to 0.27%)
     * SEBON Regulatory Fee (0.015%)
     * CDSC DP Fee (NPR 25 / transaction)
     * Round-trip friction target: ~0.65% (65 bps)
   - Dynamic Spread Cost:
     * Empirical half-spread (P_ask - P_bid) / (2 * P_mid) across liquidity tiers
   - Almgren-Chriss Square-Root Market Impact:
     * Temporary Impact = eta * (Order_Qty / ADV_20d)^0.5 * sigma_t
     * Permanent Impact = gamma * (Order_Qty / ADV_20d) * sigma_t
   - Opportunity Cost:
     * (Target_Qty - Executed_Qty) * |P_final - P_decision|

2. Append-Only Merkle Audit Chain (HMAC-SHA256):
   - Cryptographically linked audit ledger for institutional order blotters and signals.
   - Proves zero post-hoc modification, tampering, or reordering of execution records.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import math
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class ImplementationShortfallBreakdown:
    symbol: str
    target_shares: int
    executed_shares: int
    decision_price: float
    execution_price: float
    final_price: float
    
    # Cost Components in NPR
    spread_cost_npr: float
    market_impact_npr: float
    opportunity_cost_npr: float
    fixed_fees_npr: float
    total_is_npr: float
    
    # Relative Metrics
    total_is_bps: float
    is_percentage: float
    is_adverse: bool
    
    # Fee breakdown
    broker_commission_npr: float
    sebon_fee_npr: float
    cdsc_dp_fee_npr: float


class DynamicImplementationShortfallEngine:
    """
    Evaluates institutional execution efficiency and decomposes slippage
    into pure spread, market impact, opportunity cost, and regulatory friction.
    """

    # NEPSE Broker Commission Tiers (SEBON Gazette)
    COMMISSION_TIERS = [
        (50_000, 0.0040),        # Up to 50k: 0.40%
        (500_000, 0.0037),       # 50k - 500k: 0.37%
        (2_000_000, 0.0034),     # 500k - 2M: 0.34%
        (10_000_000, 0.0030),    # 2M - 10M: 0.30%
        (float("inf"), 0.0027),  # Above 10M: 0.27%
    ]
    SEBON_REGULATORY_RATE = 0.00015  # 0.015%
    CDSC_DP_FEE_NPR = 25.0           # 25 NPR per scrip

    def __init__(
        self,
        impact_eta: float = 0.142,   # Temporary impact coefficient
        impact_gamma: float = 0.085, # Permanent impact coefficient
        default_daily_volatility: float = 0.018  # 1.8% typical NEPSE daily vol
    ):
        self.impact_eta = impact_eta
        self.impact_gamma = impact_gamma
        self.default_vol = default_daily_volatility

    def compute_broker_commission(self, trade_value_npr: float) -> float:
        """Computes graduated NEPSE broker commission."""
        if trade_value_npr <= 0:
            return 0.0
        for ceiling, rate in self.COMMISSION_TIERS:
            if trade_value_npr <= ceiling:
                return max(10.0, round(trade_value_npr * rate, 2))
        return round(trade_value_npr * 0.0027, 2)

    def evaluate_implementation_shortfall(
        self,
        symbol: str,
        target_shares: int,
        executed_shares: int,
        decision_price: float,
        execution_price: float,
        final_price: Optional[float] = None,
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        adv_20d: int = 50_000,
        daily_volatility: Optional[float] = None,
        side: str = "BUY"
    ) -> ImplementationShortfallBreakdown:
        """
        Decomposes total implementation shortfall into its 4 constituent terms:
        IS = Spread Cost + Market Impact + Opportunity Cost + Fixed Fees
        """
        final_p = final_price if final_price is not None else execution_price
        sigma = daily_volatility if daily_volatility is not None else self.default_vol
        effective_adv = max(adv_20d, 1_000)

        # 1. Fixed Regulatory & Broker Friction
        exec_value = executed_shares * execution_price
        broker_comm = self.compute_broker_commission(exec_value) if executed_shares > 0 else 0.0
        sebon_fee = round(exec_value * self.SEBON_REGULATORY_RATE, 2) if executed_shares > 0 else 0.0
        dp_fee = self.CDSC_DP_FEE_NPR if executed_shares > 0 else 0.0
        fixed_fees = broker_comm + sebon_fee + dp_fee

        # 2. Spread Cost (Half-Spread)
        if bid_price and ask_price and ask_price > bid_price:
            mid_p = (ask_price + bid_price) / 2.0
            half_spread_pct = (ask_price - bid_price) / (2.0 * mid_p)
        else:
            # Calibrated baseline spread: 0.18% (18 bps) for active equities
            half_spread_pct = 0.0018
        spread_cost = round(exec_value * half_spread_pct, 2)

        # 3. Market Impact (Almgren-Chriss Square-Root Model)
        pov_fraction = executed_shares / effective_adv
        temp_impact_pct = self.impact_eta * math.sqrt(max(pov_fraction, 0.0)) * sigma
        perm_impact_pct = self.impact_gamma * pov_fraction * sigma
        total_impact_pct = temp_impact_pct + perm_impact_pct
        market_impact = round(exec_value * total_impact_pct, 2)

        # 4. Opportunity Cost (Unexecuted Quantity Drift)
        unexecuted_shares = max(0, target_shares - executed_shares)
        if side.upper() == "BUY":
            price_drift = max(0.0, final_p - decision_price)
        else:
            price_drift = max(0.0, decision_price - final_p)
        opportunity_cost = round(unexecuted_shares * price_drift, 2)

        # 5. Total Implementation Shortfall
        total_is = spread_cost + market_impact + opportunity_cost + fixed_fees
        total_target_value = target_shares * decision_price
        is_bps = round((total_is / total_target_value) * 10_000, 2) if total_target_value > 0 else 0.0
        is_pct = round((total_is / total_target_value) * 100, 4) if total_target_value > 0 else 0.0

        return ImplementationShortfallBreakdown(
            symbol=symbol.upper(),
            target_shares=target_shares,
            executed_shares=executed_shares,
            decision_price=decision_price,
            execution_price=execution_price,
            final_price=final_p,
            spread_cost_npr=spread_cost,
            market_impact_npr=market_impact,
            opportunity_cost_npr=opportunity_cost,
            fixed_fees_npr=round(fixed_fees, 2),
            total_is_npr=round(total_is, 2),
            total_is_bps=is_bps,
            is_percentage=is_pct,
            is_adverse=is_bps > 65.0,  # Fails 65 bps round-trip friction threshold
            broker_commission_npr=broker_comm,
            sebon_fee_npr=sebon_fee,
            cdsc_dp_fee_npr=dp_fee
        )


@dataclass
class MerkleChainEntry:
    sequence_id: int
    timestamp_utc: str
    event_type: str
    payload_hash: str
    previous_hash: str
    signature: str


class AppendOnlyMerkleAuditChain:
    """
    Append-only Merkle chain providing HMAC-SHA256 integrity proofs.
    Guarantees tamper-evident auditability for trading signals, blotters, and fill tickets.
    """

    GENESIS_PREV_HASH = "0" * 64

    def __init__(self, secret_key: str = "AMME-SOVEREIGN-AUDIT-KEY"):
        self.secret_key = secret_key.encode("utf-8")
        self.entries: List[MerkleChainEntry] = []
        self._current_sequence = 0

    def append_event(self, event_type: str, payload: Any) -> MerkleChainEntry:
        """Appends a new event and seals it with HMAC-SHA256 against the previous link."""
        if isinstance(payload, (dict, list)):
            canonical_payload = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        else:
            canonical_payload = str(payload)

        payload_h = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        prev_h = self.entries[-1].signature if self.entries else self.GENESIS_PREV_HASH
        seq = self._current_sequence + 1
        t_stamp = datetime.now(timezone.utc).isoformat()

        # Chain Link Formula: HMAC(Key, prev_hash || seq || event_type || payload_hash)
        chain_message = f"{prev_h}|{seq}|{event_type}|{payload_h}|{t_stamp}".encode("utf-8")
        sig = hmac.new(self.secret_key, chain_message, hashlib.sha256).hexdigest()

        entry = MerkleChainEntry(
            sequence_id=seq,
            timestamp_utc=t_stamp,
            event_type=event_type,
            payload_hash=payload_h,
            previous_hash=prev_h,
            signature=sig
        )
        self.entries.append(entry)
        self._current_sequence = seq
        return entry

    def verify_chain_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Validates the entire chain from genesis to head.
        Returns (True, None) if completely valid, or (False, error_reason) on any discrepancy.
        """
        expected_prev = self.GENESIS_PREV_HASH
        for idx, entry in enumerate(self.entries, 1):
            if entry.sequence_id != idx:
                return False, f"Sequence gap at index {idx}: expected {idx}, found {entry.sequence_id}"
            if entry.previous_hash != expected_prev:
                return False, f"Broken link at sequence {entry.sequence_id}: prev_hash mismatch"

            chain_message = f"{entry.previous_hash}|{entry.sequence_id}|{entry.event_type}|{entry.payload_hash}|{entry.timestamp_utc}".encode("utf-8")
            recomputed_sig = hmac.new(self.secret_key, chain_message, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(entry.signature, recomputed_sig):
                return False, f"Cryptographic signature mismatch at sequence {entry.sequence_id} (tampering detected)"

            expected_prev = entry.signature

        return True, None

    def export_chain_manifest(self) -> Dict[str, Any]:
        """Exports the verifiable audit chain manifest."""
        is_valid, err = self.verify_chain_integrity()
        return {
            "chain_length": len(self.entries),
            "head_signature": self.entries[-1].signature if self.entries else self.GENESIS_PREV_HASH,
            "is_valid": is_valid,
            "verification_error": err,
            "entries": [asdict(e) for e in self.entries]
        }
