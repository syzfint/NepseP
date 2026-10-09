#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/ten_kitta_allotment_sink.py

10-Kitta Mandatory Allotment & Odd-Lot Liquidity Sink POV
=========================================================
Models post-IPO listing dynamics under SEBON's mandatory 10-kitta (10 units) rule,
incorporating the Book-Building vs Par-Value dual track and 6-Month QIB Lock-in supply shock.

Market Mechanics:
1. Retail Fragmentation: Millions of retail Demat accounts receive exactly 10 units.
2. Par-Value vs Book-Building Tracks:
   - Par-Value (NPR 100): 100% public float (retail gets almost all shares), massive flip profit margins.
   - Book-Building (e.g. SARBTM, SONA): 40% reserved for Qualified Institutional Buyers (QIBs)
     with a mandatory 6-month lock-in period (180 days). Retail enters at high cut-off prices with
     much narrower flip profit margins.
3. Phase 1: Initial Lockup (Consecutive +10% upper circuit days, razor-thin volume).
4. Phase 2: Retail Dumping Wave (Circuit breaks, small accounts dump 10-unit blocks).
5. Phase 3: Institutional Absorption Inflection: Cumulative volume absorbs the retail dump target
   (eta_dump >= 70%) and broker concentration shifts to institutional accumulators.
6. Phase 4: Post-Absorption Equilibrium: Normal secondary market trading.
7. Phase 5: Book-Building QIB 6-Month Lock-In Expiry Supply Shock:
   Arrival of the 40% institutional QIB tranche onto the secondary market after 180 calendar days.
"""

import sys
import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ten_kitta_sink")


class TenKittaAllotmentSink:
    """
    Quantifies the post-IPO 10-kitta retail exhaustion point and QIB secondary supply shocks.
    """

    def __init__(self, retail_dump_propensity: float = 0.70):
        self.retail_dump_propensity = retail_dump_propensity  # ~70% of 10-kitta holders flip for fast gains

    def compute_retail_float_profile(
        self,
        symbol: str,
        total_ipo_shares: int,
        allottee_count: int,
        nominal_price: float = 100.0,
        issue_type: str = "PAR_VALUE",  # "PAR_VALUE" or "BOOK_BUILDING"
        cutoff_price: Optional[float] = None,
        qib_tranche_pct: float = 40.0,
        qib_lockin_days: int = 180
    ) -> Dict[str, Any]:
        """
        Calculates fragmented retail float, institutional QIB tranches, and required absorption volume.
        """
        is_book_building = issue_type.upper().strip() == "BOOK_BUILDING"
        effective_price = cutoff_price if (is_book_building and cutoff_price is not None) else nominal_price

        allotted_retail_shares = allottee_count * 10
        institutional_ipo_shares = max(0, total_ipo_shares - allotted_retail_shares)

        # In Book-Building, QIBs hold a statutory 40% tranche locked for 180 days
        if is_book_building:
            qib_shares = int(total_ipo_shares * (qib_tranche_pct / 100.0))
            # Retail dump margin is narrower on book-building due to higher issue price
            retail_flip_margin_threshold_pct = 20.0
            dump_propensity = min(self.retail_dump_propensity, 0.55)
        else:
            qib_shares = 0
            retail_flip_margin_threshold_pct = 100.0  # Par value retail expect 100%+ gains
            dump_propensity = self.retail_dump_propensity

        target_absorption_shares = int(allotted_retail_shares * dump_propensity)

        return {
            "symbol": symbol.upper().strip(),
            "issue_type": "BOOK_BUILDING" if is_book_building else "PAR_VALUE",
            "total_ipo_shares": total_ipo_shares,
            "allottee_count": allottee_count,
            "nominal_price_npr": nominal_price,
            "effective_issue_price_npr": effective_price,
            "retail_allotted_shares": allotted_retail_shares,
            "institutional_ipo_shares": institutional_ipo_shares,
            "qib_shares_locked": qib_shares,
            "qib_lockin_days": qib_lockin_days if is_book_building else 0,
            "retail_float_pct": round((allotted_retail_shares / max(total_ipo_shares, 1)) * 100, 2),
            "retail_flip_margin_threshold_pct": retail_flip_margin_threshold_pct,
            "dump_propensity_used": dump_propensity,
            "estimated_dump_volume_target": target_absorption_shares,
            "capital_required_nominal_npr": target_absorption_shares * effective_price,
            "secondary_qib_supply_shock_shares": qib_shares
        }

    def evaluate_post_listing_phase(
        self,
        symbol: str,
        allottee_count: int,
        daily_trading_history: List[Dict[str, Any]],  # list of dicts: {"day": int, "close": float, "volume": int, "is_upper_circuit": bool, "broker_top_buyer_pct": float}
        odd_lot_volume: int = 0,
        issue_type: str = "PAR_VALUE",
        cutoff_price: Optional[float] = None,
        days_since_listing: Optional[int] = None,
        total_ipo_shares: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Evaluates post-listing trading history to identify retail exhaustion,
        institutional absorption inflection, and book-building QIB lock-in expiry.
        """
        is_book_building = issue_type.upper().strip() == "BOOK_BUILDING"
        dump_propensity = min(self.retail_dump_propensity, 0.55) if is_book_building else self.retail_dump_propensity
        retail_target = int(allottee_count * 10 * dump_propensity)

        cum_volume = 0
        circuit_streak = 0
        circuit_broken = False
        circuit_break_day = None

        total_days = len(daily_trading_history)
        elapsed_days = days_since_listing if days_since_listing is not None else total_days

        for bar in daily_trading_history:
            day = bar.get("day", 1)
            vol = bar.get("volume", 0)
            is_circuit = bar.get("is_upper_circuit", False)

            cum_volume += vol

            if is_circuit and not circuit_broken:
                circuit_streak += 1
            elif not is_circuit and not circuit_broken:
                circuit_broken = True
                circuit_break_day = day

        absorption_ratio = round(cum_volume / max(retail_target, 1), 4)
        latest_bar = daily_trading_history[-1] if daily_trading_history else {}
        top_buyer_pct = latest_bar.get("broker_top_buyer_pct", 0.0)
        latest_close = latest_bar.get("close", 100.0)

        # Calculate retail profit margin
        base_price = cutoff_price if (is_book_building and cutoff_price is not None) else 100.0
        retail_profit_margin_pct = round(((latest_close - base_price) / base_price) * 100.0, 2)

        # Inflection occurs when circuit is broken, >= 70% of retail dump is absorbed,
        # and top 3 brokers accumulate >= 40% of volume.
        is_inflection = circuit_broken and (absorption_ratio >= 0.70) and (top_buyer_pct >= 40.0)

        # Check for Book-Building QIB 6-month lock-in expiry (180 calendar days or approx 120 trading days)
        qib_lockin_expired = is_book_building and (elapsed_days >= 180)
        qib_supply_shock_shares = int((total_ipo_shares or (allottee_count * 10 / 0.6)) * 0.40) if is_book_building else 0

        if qib_lockin_expired:
            phase = "PHASE_5_QIB_LOCKIN_EXPIRY_SUPPLY_SHOCK"
            action = "DEFENSIVE_HOLD_OR_REDUCE_QIB_SUPPLY_WALL"
        elif not circuit_broken:
            phase = "PHASE_1_UPPER_CIRCUIT_LOCKUP"
            action = "HOLD_WAIT_FOR_LIQUIDITY"
        elif circuit_broken and absorption_ratio < 0.70:
            phase = "PHASE_2_RETAIL_DUMPING_CASCADE"
            action = "AVOID_RETAIL_PANIC_WAVE"
        elif is_inflection and absorption_ratio <= 1.30:
            phase = "PHASE_3_INSTITUTIONAL_ABSORPTION_INFLECTION"
            action = "STRONG_BUY_INSTITUTIONAL_ENTRY"
        else:
            phase = "PHASE_4_POST_ABSORPTION_EQUILIBRIUM"
            action = "NORMAL_SECONDARY_TRADING"

        return {
            "symbol": symbol.upper().strip(),
            "issue_type": "BOOK_BUILDING" if is_book_building else "PAR_VALUE",
            "total_trading_days": total_days,
            "days_since_listing": elapsed_days,
            "consecutive_upper_circuits": circuit_streak,
            "circuit_broken": circuit_broken,
            "circuit_break_day": circuit_break_day,
            "cumulative_volume_traded": cum_volume,
            "retail_target_dump_shares": retail_target,
            "retail_absorption_ratio": absorption_ratio,
            "odd_lot_volume_excluded": odd_lot_volume,
            "top_broker_concentration_pct": top_buyer_pct,
            "retail_profit_margin_pct": retail_profit_margin_pct,
            "qib_lockin_expired": qib_lockin_expired,
            "qib_supply_shock_shares": qib_supply_shock_shares,
            "current_phase": phase,
            "recommended_action": action
        }


def main():
    sink = TenKittaAllotmentSink()
    # 1. Par-Value IPO Simulation (HRL)
    prof_par = sink.compute_retail_float_profile(
        symbol="HRL",
        total_ipo_shares=30000000,
        allottee_count=1500000,
        nominal_price=206.0,
        issue_type="PAR_VALUE"
    )
    print("Par-Value Float Profile (HRL):", prof_par)

    # 2. Book-Building IPO Simulation (SARBTM: Cutoff 430 NPR, 40% QIB lockin)
    prof_bb = sink.compute_retail_float_profile(
        symbol="SARBTM",
        total_ipo_shares=10000000,
        allottee_count=600000,
        nominal_price=100.0,
        issue_type="BOOK_BUILDING",
        cutoff_price=430.0,
        qib_tranche_pct=40.0,
        qib_lockin_days=180
    )
    print("\nBook-Building Float Profile (SARBTM):", prof_bb)

    # Simulated post-listing trading history for SARBTM
    history = [
        {"day": 1, "close": 550.0, "volume": 15000, "is_upper_circuit": True, "broker_top_buyer_pct": 15.0},
        {"day": 2, "close": 605.0, "volume": 25000, "is_upper_circuit": True, "broker_top_buyer_pct": 20.0},
        {"day": 3, "close": 580.0, "volume": 1800000, "is_upper_circuit": False, "broker_top_buyer_pct": 32.0},
        {"day": 4, "close": 560.0, "volume": 2200000, "is_upper_circuit": False, "broker_top_buyer_pct": 46.0},
    ]
    eval_result = sink.evaluate_post_listing_phase(
        "SARBTM",
        allottee_count=600000,
        daily_trading_history=history,
        issue_type="BOOK_BUILDING",
        cutoff_price=430.0,
        days_since_listing=185,  # Past 180 days!
        total_ipo_shares=10000000
    )
    print("\nSARBTM Phase Evaluation (QIB Lock-in Expiry Shock):")
    print(eval_result)


if __name__ == "__main__":
    main()
