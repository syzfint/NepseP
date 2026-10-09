#!/usr/bin/env python3
"""
scripts/00_control/pre_open_auction_engine.py

APEXMARKETENGINE — PRE-OPEN DYNAMIC ORDER-IMBALANCE MATCHING ENGINE
====================================================================
Upgrades static pre-open modeling into a high-fidelity multilateral
call-auction matching engine for NEPSE's Special Pre-Open Session (10:30–10:45 AM).

Solves the Indicative Equilibrium Price (IEP) and Order Imbalance Ratio (OIR):
1. Cumulative Demand Curve: D(P) = sum_{p >= P} Q_bid(p)
2. Cumulative Supply Curve: S(P) = sum_{p <= P} Q_ask(p)
3. Maximizes Executable Volume: P* = argmax_P min(D(P), S(P))
4. Minimizes Order Imbalance: |D(P*) - S(P*)|
5. Ties broken by proximity to Reference Price (P_ref)
"""

import sys
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [PreOpenAuction] %(message)s"
)
logger = logging.getLogger("PreOpenAuction")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class PreOpenOrder:
    order_id: str
    symbol: str
    side: str          # "BUY" or "SELL"
    price: float
    quantity: int
    timestamp: str


@dataclass
class EquilibriumMatchResult:
    symbol: str
    reference_price: float
    indicative_equilibrium_price: float
    matched_volume: int
    unmatched_buy_volume: int
    unmatched_sell_volume: int
    order_imbalance_ratio: float       # in [-1.0, +1.0]
    expected_opening_gap_pct: float
    price_discovery_status: str        # "BALANCED", "BUY_IMBALANCE", "SELL_IMBALANCE", "NO_MATCH"


class PreOpenAuctionMatchingEngine:
    """Multilateral Call-Auction Matching Engine for NEPSE Pre-Open Session."""

    def __init__(self, tick_size: float = 0.10):
        self.tick_size = tick_size

    def calculate_iep(
        self,
        symbol: str,
        bids: List[Tuple[float, int]],       # list of (price, qty)
        asks: List[Tuple[float, int]],       # list of (price, qty)
        reference_price: float
    ) -> EquilibriumMatchResult:
        """
        Calculates Indicative Equilibrium Price (IEP) matching SEBON/NOTS auction rules.
        """
        if not bids or not asks:
            return EquilibriumMatchResult(
                symbol=symbol,
                reference_price=reference_price,
                indicative_equilibrium_price=reference_price,
                matched_volume=0,
                unmatched_buy_volume=sum(q for _, q in bids),
                unmatched_sell_volume=sum(q for _, q in asks),
                order_imbalance_ratio=0.0,
                expected_opening_gap_pct=0.0,
                price_discovery_status="NO_MATCH"
            )

        # Candidate price grid (all unique bid and ask prices)
        candidate_prices = sorted(list(set([p for p, _ in bids] + [p for p, _ in asks])))

        best_price = reference_price
        max_matched_vol = -1
        min_imbalance = float("inf")
        best_d = 0
        best_s = 0

        for p in candidate_prices:
            # Cumulative demand at price p: all buyers willing to pay >= p
            cum_demand = sum(q for bp, q in bids if bp >= p)
            # Cumulative supply at price p: all sellers willing to sell <= p
            cum_supply = sum(q for ap, q in asks if ap <= p)

            matched_vol = min(cum_demand, cum_supply)
            imbalance = abs(cum_demand - cum_supply)

            # Rule 1: Maximize matched volume
            if matched_vol > max_matched_vol:
                max_matched_vol = matched_vol
                min_imbalance = imbalance
                best_price = p
                best_d = cum_demand
                best_s = cum_supply
            elif matched_vol == max_matched_vol and matched_vol > 0:
                # Rule 2: Minimize imbalance
                if imbalance < min_imbalance:
                    min_imbalance = imbalance
                    best_price = p
                    best_d = cum_demand
                    best_s = cum_supply
                elif imbalance == min_imbalance:
                    # Rule 3: Tie-break closest to reference price
                    if abs(p - reference_price) < abs(best_price - reference_price):
                        best_price = p
                        best_d = cum_demand
                        best_s = cum_supply

        unmatched_buy = max(0, best_d - max_matched_vol)
        unmatched_sell = max(0, best_s - max_matched_vol)
        total_depth = best_d + best_s
        oir = round((best_d - best_s) / total_depth, 4) if total_depth > 0 else 0.0

        opening_gap = round(((best_price - reference_price) / reference_price) * 100.0, 2) if reference_price > 0 else 0.0

        if oir > 0.30:
            status = "BUY_IMBALANCE"
        elif oir < -0.30:
            status = "SELL_IMBALANCE"
        else:
            status = "BALANCED"

        return EquilibriumMatchResult(
            symbol=symbol,
            reference_price=reference_price,
            indicative_equilibrium_price=round(best_price, 2),
            matched_volume=max_matched_vol,
            unmatched_buy_volume=unmatched_buy,
            unmatched_sell_volume=unmatched_sell,
            order_imbalance_ratio=oir,
            expected_opening_gap_pct=opening_gap,
            price_discovery_status=status
        )

    def evaluate_pre_open_book(
        self,
        symbol: str,
        order_book_depth: Dict[str, Any],
        reference_price: float
    ) -> EquilibriumMatchResult:
        """Parses LOB queues from live NEPSE market depth and executes matching."""
        bids = []
        asks = []
        for b in order_book_depth.get("buy", []):
            bids.append((float(b.get("orderPrice", b.get("price", 0.0))), int(b.get("orderQuantity", b.get("quantity", 0)))))
        for a in order_book_depth.get("sell", []):
            asks.append((float(a.get("orderPrice", a.get("price", 0.0))), int(a.get("orderQuantity", a.get("quantity", 0)))))

        return self.calculate_iep(symbol, bids, asks, reference_price)


if __name__ == "__main__":
    engine = PreOpenAuctionMatchingEngine()
    # Simulated Special Pre-Open order book for NICA
    ref_p = 500.0
    test_bids = [(505.0, 400), (502.0, 800), (500.0, 1500), (498.0, 2000)]
    test_asks = [(498.0, 500), (500.0, 1200), (502.0, 1800), (505.0, 2500)]

    res = engine.calculate_iep("NICA", test_bids, test_asks, reference_price=ref_p)
    print("\n" + "=" * 70)
    print("      NEPSE SPECIAL PRE-OPEN MULTILATERAL CALL AUCTION TEST")
    print("=" * 70)
    print(f"Symbol:                   {res.symbol}")
    print(f"Reference Price:          NPR {res.reference_price:.2f}")
    print(f"Indicative IEP:           NPR {res.indicative_equilibrium_price:.2f} ({res.expected_opening_gap_pct:+.2f}%)")
    print(f"Matched Volume:           {res.matched_volume:,} shares")
    print(f"Unmatched Buy / Sell:     {res.unmatched_buy_volume:,} / {res.unmatched_sell_volume:,}")
    print(f"Order Imbalance Ratio:    {res.order_imbalance_ratio:+.2f}")
    print(f"Opening Status:           {res.price_discovery_status}")
    print("=" * 70)
