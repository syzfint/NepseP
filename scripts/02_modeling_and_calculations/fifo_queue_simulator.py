#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/fifo_queue_simulator.py

APEXMARKETENGINE — FIFO QUEUE-POSITION & FILL-PROBABILITY SIMULATOR
===================================================================
Models child order queue priority rank and fill likelihood in NEPSE's Level 2 Order Book.
Based on queue-reactive microstructure models (Huang, Lehalle & Rosenbaum, 2015; Titan L2).

Mathematical Architecture:
1. FIFO Queue Depletion:
   Q_ahead(t + Delta t) = max(0, Q_ahead(t) - V_aggressor(Delta t) - Cancellations_ahead(Delta t))
2. Probability of Execution:
   Given remaining session time T - t (in seconds), average matching rate mu_v,
   and volume variance sigma_v^2:
   P(Fill | t) = Phi((mu_v * (T - t) - Q_ahead) / (sigma_v * sqrt(T - t)))
3. Algorithmic Routing Action:
   - P(Fill) >= 0.75 : OPTIMAL_QUEUE_POSITION (maintain passive limit order)
   - 0.35 <= P(Fill) < 0.75 : MARGINAL_RISK (monitor aggressor acceleration)
   - P(Fill) < 0.35 : DEAD_CAPITAL_TRAP -> Cancel ticket, re-slice, or cross spread
"""

import sys
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from scipy.stats import norm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FIFOQueueSimulator] %(message)s"
)
logger = logging.getLogger("FIFOQueueSimulator")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class QueueSimTicket:
    ticket_id: str
    symbol: str
    side: str                          # "BUY" or "SELL"
    limit_price: float
    order_quantity: int
    queue_shares_ahead: int
    estimated_fill_probability: float  # [0.0, 1.0]
    expected_time_to_fill_sec: float
    session_remaining_sec: float
    routing_recommendation: str        # "MAINTAIN_PASSIVE", "MONITOR", "CANCEL_AND_REDEPLOY"


class FIFOQueuePositionSimulator:
    """Simulates Level-2 order book queue priority and fill probability."""

    def __init__(self, default_cancellation_rate: float = 0.20):
        # In NEPSE, approximately 20% of passive queue volume is cancelled before trade touch
        self.cancellation_rate = default_cancellation_rate

    def estimate_fill_probability(
        self,
        order_qty: int,
        shares_ahead: int,
        daily_median_turnover_shares: int,
        session_remaining_seconds: float = 3600.0,
        is_touching_circuit: bool = False
    ) -> Tuple[float, float, str]:
        """
        Computes analytical probability of complete fill P(Fill) and expected wait time.
        """
        if is_touching_circuit:
            # At circuit limit (+10% or -10%), book is completely one-sided, matching rate collapses to zero
            return 0.05, float("inf"), "CANCEL_AND_REDEPLOY (Circuit Lockup Zero Fills)"

        if shares_ahead <= 0:
            return 0.99, 5.0, "MAINTAIN_PASSIVE (Top of Queue)"

        # Effective queue to clear considering cancellations ahead
        effective_queue = shares_ahead * (1.0 - self.cancellation_rate) + order_qty

        # Average fill rate per second based on active continuous trading session (4 hours = 14,400s)
        trading_day_seconds = 14_400.0
        avg_rate_per_sec = max(0.05, daily_median_turnover_shares / trading_day_seconds)
        vol_rate_per_sec = max(0.10, avg_rate_per_sec * 0.45)

        # Expected volume traded during remaining window
        mu = avg_rate_per_sec * session_remaining_seconds
        sigma = vol_rate_per_sec * np.sqrt(max(1.0, session_remaining_seconds))

        # Probability that incoming aggressor volume >= effective_queue
        z = (mu - effective_queue) / sigma if sigma > 0 else 0.0
        p_fill = float(norm.cdf(z))
        p_fill = round(min(0.99, max(0.01, p_fill)), 4)

        # Expected seconds to complete fill
        expected_sec = round(effective_queue / avg_rate_per_sec, 1)

        # Determine tactical action
        if p_fill >= 0.70:
            rec = "MAINTAIN_PASSIVE"
        elif p_fill >= 0.35:
            rec = "MONITOR_ACCELERATION"
        else:
            rec = "CANCEL_AND_REDEPLOY (Fill Probability Below Threshold)"

        return p_fill, expected_sec, rec

    def evaluate_staged_tickets(
        self,
        staged_tickets: List[Dict[str, Any]],
        session_remaining_sec: float = 3600.0,
        scrip_daily_volumes: Optional[Dict[str, int]] = None
    ) -> List[QueueSimTicket]:
        """Evaluates a batch of staged TMS order tickets against queue depth."""
        scrip_daily_volumes = scrip_daily_volumes or {}
        results: List[QueueSimTicket] = []

        for tkt in staged_tickets:
            sym = tkt.get("symbol", "")
            qty = int(tkt.get("quantity", 100))
            side = tkt.get("side", "BUY")
            price = float(tkt.get("limit_price", 100.0))
            
            # Estimate queue ahead: by default 2x the child order quantity if not provided
            shares_ahead = int(tkt.get("queue_ahead", qty * 3))
            daily_vol = scrip_daily_volumes.get(sym, 25_000)

            p_fill, exp_sec, rec = self.estimate_fill_probability(
                order_qty=qty,
                shares_ahead=shares_ahead,
                daily_median_turnover_shares=daily_vol,
                session_remaining_seconds=session_remaining_sec
            )

            sim_tkt = QueueSimTicket(
                ticket_id=tkt.get("ticket_id", "TKT-SIM-001"),
                symbol=sym,
                side=side,
                limit_price=price,
                order_quantity=qty,
                queue_shares_ahead=shares_ahead,
                estimated_fill_probability=p_fill,
                expected_time_to_fill_sec=exp_sec,
                session_remaining_sec=session_remaining_sec,
                routing_recommendation=rec
            )
            results.append(sim_tkt)

        return results


if __name__ == "__main__":
    simulator = FIFOQueuePositionSimulator()

    # Scenario: 500 shares of SHIVM with 4,000 shares ahead in queue, 45 minutes (2,700s) left in session
    p_fill, wait_sec, rec = simulator.estimate_fill_probability(
        order_qty=500,
        shares_ahead=4000,
        daily_median_turnover_shares=45_000,
        session_remaining_seconds=2700.0
    )

    print("\n" + "=" * 70)
    print("      L2 FIFO QUEUE POSITION & FILL PROBABILITY SIMULATOR TEST")
    print("=" * 70)
    print(f"Order Quantity:           500 shares")
    print(f"Queue Ahead:              4,000 shares")
    print(f"Remaining Session Time:   2,700 seconds (45 minutes)")
    print(f"Fill Probability P(Fill): {p_fill*100:.1f}%")
    print(f"Expected Wait Time:       {wait_sec:.1f} seconds ({wait_sec/60:.1f} mins)")
    print(f"Routing Recommendation:   {rec}")
    print("=" * 70)
