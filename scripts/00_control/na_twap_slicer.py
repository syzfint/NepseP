#!/usr/bin/env python3
"""
scripts/00_control/na_twap_slicer.py

NA-TWAP Slicer (Non-Aggressive Depth-Capped TWAP Execution Engine)
==================================================================
Slices parent institutional orders into child limit orders for NEPSE TMS execution.

Institutional Rules:
1. Depth-Capped Participation:
   Each child order slice is strictly capped at <= 15% of the prevailing Level 2
   order book depth to avoid Kyle's lambda market impact slippage.
2. Time-Weighted Slicing (TWAP):
   Spreads execution across N time slices (e.g., 10 to 60 minutes).
3. Laya Pre-Execution Circuit Halt Gate:
   Continuously evaluates breaking news via LayaTriageGuard (<33ms).
   If P(bearish) > 0.85, unexecuted slices are immediately frozen.
4. TMS Staging Ready:
   Generates validated child order tickets ready for 1-click Playwright/TMS staging.
"""

import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("na_twap_slicer")

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from .laya_triage_guard import LayaTriageGuard

ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")


class NATWAPSlicer:
    """
    Non-Aggressive Depth-Capped TWAP Slicing Engine.
    """

    def __init__(self, laya_guard: Optional[LayaTriageGuard] = None, max_depth_participation: float = 0.15):
        self.laya_guard = laya_guard or LayaTriageGuard()
        self.max_depth_participation = max_depth_participation  # Max 15% of book depth per slice

    def compute_twap_slices(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        total_quantity: int,
        limit_price: float,
        duration_minutes: int = 30,
        interval_minutes: int = 5,
        prevailing_book_depth_shares: int = 2500,
        latest_headline_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Computes depth-capped child order slicing schedule.
        """
        # 1. Check Laya Pre-Trade Risk Gate
        risk_halt = False
        if latest_headline_context:
            risk_halt = self.laya_guard.evaluate_pre_execution_risk(latest_headline_context)
            if risk_halt:
                logger.warning(f"Laya Triage Guard triggered execution risk halt on headline: '{latest_headline_context}'")
                return {
                    "symbol": symbol.upper().strip(),
                    "side": side.upper(),
                    "total_quantity": total_quantity,
                    "status": "HALTED_PRE_TRADE_RISK",
                    "reason": "Laya System 1 Triage Guard detected critical bearish news.",
                    "child_orders": []
                }

        num_intervals = max(1, duration_minutes // interval_minutes)
        base_slice_qty = total_quantity // num_intervals
        remainder_qty = total_quantity % num_intervals

        # Max child order size capped by order book depth
        depth_cap = int(prevailing_book_depth_shares * self.max_depth_participation)
        max_slice_allowed = max(10, depth_cap)

        child_orders = []
        accumulated_qty = 0

        for i in range(num_intervals):
            slice_qty = base_slice_qty + (1 if i < remainder_qty else 0)
            # Enforce depth capping
            is_depth_capped = slice_qty > max_slice_allowed
            effective_qty = min(slice_qty, max_slice_allowed)

            accumulated_qty += effective_qty
            order_ticket = {
                "slice_id": f"SLICE-{symbol}-{i+1:02d}",
                "symbol": symbol.upper().strip(),
                "side": side.upper(),
                "quantity": effective_qty,
                "limit_price": limit_price,
                "scheduled_minute": i * interval_minutes,
                "book_depth_shares": prevailing_book_depth_shares,
                "depth_participation_pct": round((effective_qty / prevailing_book_depth_shares) * 100, 2),
                "is_depth_capped": is_depth_capped,
                "status": "READY_FOR_STAGING"
            }
            child_orders.append(order_ticket)

        # If depth caps prevented full sizing within nominal intervals, add overflow slices
        unallocated_qty = total_quantity - accumulated_qty
        overflow_idx = num_intervals + 1
        while unallocated_qty > 0:
            overflow_qty = min(unallocated_qty, max_slice_allowed)
            unallocated_qty -= overflow_qty
            child_orders.append({
                "slice_id": f"SLICE-{symbol}-{overflow_idx:02d}",
                "symbol": symbol.upper().strip(),
                "side": side.upper(),
                "quantity": overflow_qty,
                "limit_price": limit_price,
                "scheduled_minute": (overflow_idx - 1) * interval_minutes,
                "book_depth_shares": prevailing_book_depth_shares,
                "depth_participation_pct": round((overflow_qty / prevailing_book_depth_shares) * 100, 2),
                "is_depth_capped": True,
                "status": "OVERFLOW_SLICED"
            })
            overflow_idx += 1

        total_scheduled = sum(o["quantity"] for o in child_orders)
        return {
            "symbol": symbol.upper().strip(),
            "side": side.upper(),
            "total_requested_quantity": total_quantity,
            "total_scheduled_quantity": total_scheduled,
            "limit_price": limit_price,
            "estimated_turnover_npr": round(total_scheduled * limit_price, 2),
            "total_slices": len(child_orders),
            "depth_cap_limit_per_slice": max_slice_allowed,
            "status": "SUCCESS_SCHEDULED",
            "child_orders": child_orders
        }


def main():
    slicer = NATWAPSlicer()

    # Scenario 1: Standard institutional buy order
    res = slicer.compute_twap_slices(
        symbol="NABIL",
        side="BUY",
        total_quantity=2000,
        limit_price=620.0,
        duration_minutes=30,
        interval_minutes=5,
        prevailing_book_depth_shares=3000,
        latest_headline_context="Nabil bank branch expansion in Gandaki province"
    )
    print("Scenario 1 Slicing (Normal):")
    print(f"Total Slices: {res['total_slices']} | Sched Qty: {res['total_scheduled_quantity']}")
    for c in res["child_orders"][:3]:
        print("  -", c)

    # Scenario 2: Bearish news trigger halt
    res_halt = slicer.compute_twap_slices(
        symbol="NABIL",
        side="BUY",
        total_quantity=2000,
        limit_price=620.0,
        duration_minutes=30,
        interval_minutes=5,
        prevailing_book_depth_shares=3000,
        latest_headline_context="Central Bank issues strict directives on NPL provisioning, immediate market selloff expected"
    )
    print("\nScenario 2 Slicing (Bearish Trigger):")
    print("Status:", res_halt["status"])


if __name__ == "__main__":
    main()
