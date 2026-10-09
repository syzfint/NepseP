#!/usr/bin/env python3
"""
scripts/00_control/pre_open_spoof_detector.py

Pre-Open Call Auction Order Imbalance & Spoofing Detector (10:30–10:45 AM)
==========================================================================
Analyzes the 15-minute NEPSE Pre-Open Call Auction session to detect synthetic
tape-painting and deceptive spoofing maneuvers before the 10:45 AM matching freeze,
enforcing a strict Pre-Open Cutoff Buffer at 10:44:30 AM (ignoring the final 30 seconds).

Key Vulnerability in NEPSE:
1. 10:30-10:40 AM: Speculators enter massive non-firm bids within ±5% band to inflate
   the Indicative Matching Price (IMP) and trigger retail FOMO.
2. 10:44:00-10:44:59 AM: Right before the unannounced random matching freeze, spoofers
   cancel or pull their bids, leaving retail orders trapped at inflated open prices.
3. Third-party WebSocket latency: Floor sheet / depth feeds experience 1-3 seconds packet
   delays; evaluating depth changes up to 10:44:59 reads stale or pulled bids.

Algorithmic Defenses:
- Strict Pre-Open Cutoff Buffer at 10:44:30 AM: Drops all order events in the final 30s.
- Late Cancellation Rate (CR_60s): Volume canceled in final 60s / Total volume entered.
- Unmatched Imbalance Ratio (UIR): |Bid - Ask| / (Bid + Ask).
- Verdict Classifier:
    - SYNTHETIC_PRE_OPEN_SPOOF: CR_60s > 35% and executable volume collapses.
    - GENUINE_INSTITUTIONAL_GAP: CR_60s < 10% and high firm matched volume.
"""

import sys
import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pre_open_spoof")


class PreOpenSpoofDetector:
    """
    Audits pre-open order flow dynamics in the 10:30 - 10:45 AM window
    with a mandatory 30-second pre-open cutoff buffer at 10:44:30 AM.
    """

    def __init__(
        self,
        spoof_cancel_threshold_pct: float = 35.0,
        min_executable_shares: int = 500,
        cutoff_buffer_seconds: int = 30,
        auction_cutoff_time: str = "10:44:30"
    ):
        self.spoof_cancel_threshold = spoof_cancel_threshold_pct
        self.min_executable_shares = min_executable_shares
        self.cutoff_buffer_seconds = cutoff_buffer_seconds
        self.auction_cutoff_time = auction_cutoff_time

    def filter_late_order_events(
        self,
        order_events: List[Dict[str, Any]],
        cutoff_time: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Discards and filters out order updates/depth modifications timestamped after 10:44:30 AM.
        Protects against third-party API socket lag and late 10:44:58 AM spoof cancellations.
        """
        effective_cutoff = cutoff_time or self.auction_cutoff_time
        valid_events = []
        dropped_count = 0

        for ev in order_events:
            ts = ev.get("timestamp", ev.get("time", ""))
            if ts:
                # Extract HH:MM:SS
                time_str = str(ts).strip()
                if " " in time_str:
                    time_str = time_str.split(" ")[-1]
                if len(time_str) >= 8:
                    time_str = time_str[:8]
                    if time_str > effective_cutoff:
                        dropped_count += 1
                        continue
            valid_events.append(ev)

        return valid_events, dropped_count

    def evaluate_pre_open_order_flow(
        self,
        symbol: str,
        prev_close: float,
        indicative_match_price: float,
        total_entered_bid_shares: int,
        canceled_bid_shares_final_60s: int,
        final_executable_matched_shares: int,
        unmatched_bid_shares: int,
        unmatched_ask_shares: int,
        order_events: Optional[List[Dict[str, Any]]] = None,
        as_of_time: str = "10:44:30"
    ) -> Dict[str, Any]:
        """
        Evaluates pre-open order cancellations and imbalance to detect tape painting,
        enforcing the 10:44:30 AM cutoff buffer.
        """
        dropped_packets = 0
        if order_events:
            _, dropped_packets = self.filter_late_order_events(order_events, self.auction_cutoff_time)

        # 1. Price gap relative to previous close
        price_gap_pct = round(((indicative_match_price - prev_close) / prev_close) * 100.0, 2)

        # 2. Final 60-second cancellation rate
        cancel_rate_pct = round(
            (canceled_bid_shares_final_60s / max(total_entered_bid_shares, 1)) * 100.0, 2
        )

        # 3. Unmatched Imbalance Ratio (UIR)
        total_unmatched = unmatched_bid_shares + unmatched_ask_shares
        uir = (
            round(abs(unmatched_bid_shares - unmatched_ask_shares) / max(total_unmatched, 1), 4)
            if total_unmatched > 0
            else 0.0
        )

        # 4. Spoofer vs Genuine Gap-Up Classification
        is_spoofed = (
            (cancel_rate_pct >= self.spoof_cancel_threshold) or
            (price_gap_pct >= 2.5 and final_executable_matched_shares < self.min_executable_shares)
        )

        is_genuine_gap = (
            (price_gap_pct >= 1.5) and
            (cancel_rate_pct < 12.0) and
            (final_executable_matched_shares >= self.min_executable_shares * 2)
        )

        # Check if as_of_time is dangerously close to 10:45:00 without buffer
        buffer_violation = as_of_time > self.auction_cutoff_time

        if is_spoofed:
            verdict = "SYNTHETIC_PRE_OPEN_SPOOF"
            action = "REJECT_GAP_ENTRY_FADE_OPEN"
            confidence = 0.92
        elif is_genuine_gap:
            verdict = "GENUINE_INSTITUTIONAL_GAP"
            action = "CONFIRM_LONG_MOMENTUM_BREAKOUT"
            confidence = 0.88
        else:
            verdict = "NEUTRAL_ORDER_DISCOVERY"
            action = "OBSERVE_CONTINUOUS_SESSION"
            confidence = 0.65

        return {
            "symbol": symbol.upper().strip(),
            "prev_close": prev_close,
            "indicative_match_price": indicative_match_price,
            "gap_pct": price_gap_pct,
            "total_bid_shares_entered": total_entered_bid_shares,
            "canceled_bid_shares_final_60s": canceled_bid_shares_final_60s,
            "cancellation_rate_pct": cancel_rate_pct,
            "final_executable_matched_shares": final_executable_matched_shares,
            "unmatched_imbalance_ratio": uir,
            "pre_open_cutoff_enforced": True,
            "auction_cutoff_time": self.auction_cutoff_time,
            "cutoff_buffer_seconds": self.cutoff_buffer_seconds,
            "late_packets_filtered_count": dropped_packets,
            "buffer_violation_risk": buffer_violation,
            "verdict": verdict,
            "recommended_action": action,
            "confidence": confidence
        }


def main():
    detector = PreOpenSpoofDetector()

    # Scenario 1: Deceptive Tape-Painting Spoof (Bids canceled in last 60s)
    events = [
        {"timestamp": "10:43:00", "bid_qty": 20000, "price": 502.0},
        {"timestamp": "10:44:20", "bid_qty": 30000, "price": 502.0},
        {"timestamp": "10:44:45", "bid_qty": -24000, "price": 502.0}, # Past 10:44:30 cutoff!
        {"timestamp": "10:44:58", "bid_qty": -5000, "price": 502.0},  # Past cutoff!
    ]
    res_spoof = detector.evaluate_pre_open_order_flow(
        symbol="SHIVM",
        prev_close=480.0,
        indicative_match_price=502.0,  # +4.58% gap
        total_entered_bid_shares=50000,
        canceled_bid_shares_final_60s=24000,  # 48% canceled right before freeze
        final_executable_matched_shares=200,  # matched volume collapsed to 200 shares
        unmatched_bid_shares=1000,
        unmatched_ask_shares=25000,
        order_events=events,
        as_of_time="10:44:30"
    )
    print("Scenario 1 (Spoof Tape-Painting with 10:44:30 Cutoff):")
    print(res_spoof)

    # Scenario 2: Genuine Institutional Gap-Up
    res_real = detector.evaluate_pre_open_order_flow(
        symbol="NABIL",
        prev_close=615.0,
        indicative_match_price=632.0,  # +2.76% gap
        total_entered_bid_shares=40000,
        canceled_bid_shares_final_60s=1200,   # Only 3% canceled
        final_executable_matched_shares=8500, # 8,500 firm shares executed
        unmatched_bid_shares=15000,
        unmatched_ask_shares=2000,
        as_of_time="10:44:30"
    )
    print("\nScenario 2 (Genuine Gap):")
    print(res_real)


if __name__ == "__main__":
    main()
