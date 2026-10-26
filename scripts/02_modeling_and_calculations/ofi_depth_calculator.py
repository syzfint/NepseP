"""
scripts/02_modeling_and_calculations/ofi_depth_calculator.py

CONT-STOIKOV ORDER FLOW IMBALANCE (OFI) & MULTI-LEVEL L2 DEPTH CALCULATOR
==========================================================================
Implements high-frequency microstructure dynamics based on:
- Cont, R., Kukanov, A., & Stoikov, S. (2014). The Price Impact of Order Book Events.
  Journal of Financial Econometrics, 12(1), 47-88.
"""

from typing import Dict, Any, List, Optional, Tuple


class ContStoikovOFICalculator:
    """Calculates single-level and multi-level Order Flow Imbalance."""

    def __init__(self, depth_levels: int = 5):
        self.depth_levels = depth_levels
        # Previous state: {symbol: {"bids": [(p, q), ...], "asks": [(p, q), ...]}}
        self.prev_state: Dict[str, Dict[str, List[Tuple[float, float]]]] = {}

    def compute_level_ofi(
        self,
        prev_p: float, prev_q: float,
        curr_p: float, curr_q: float,
        is_bid: bool
    ) -> float:
        """Computes Cont-Stoikov event flow e_b(t) or e_a(t)."""
        if is_bid:
            if curr_p > prev_p:
                return curr_q
            elif curr_p == prev_p:
                return curr_q - prev_q
            else:
                return 0.0
        else:
            # Ask side
            if curr_p < prev_p:
                return -curr_q
            elif curr_p == prev_p:
                return -(curr_q - prev_q)
            else:
                return 0.0

    def update_order_book(
        self,
        symbol: str,
        bids: List[Tuple[float, float]], # List of (price, quantity), descending
        asks: List[Tuple[float, float]]  # List of (price, quantity), ascending
    ) -> Dict[str, Any]:
        """
        Updates L2 book for symbol and computes Level-1 OFI and Multi-Level Integrated OFI.
        """
        sym = symbol.upper().strip()
        if not bids or not asks:
            return {"symbol": sym, "ofi": 0.0, "nofi": 0.0, "spread_bps": 0.0}

        best_bid_p, best_bid_q = bids[0]
        best_ask_p, best_ask_q = asks[0]
        mid_p = (best_bid_p + best_ask_p) / 2.0
        spread = best_ask_p - best_bid_p
        spread_bps = (spread / mid_p * 10000.0) if mid_p > 0 else 0.0

        if sym not in self.prev_state:
            self.prev_state[sym] = {"bids": bids, "asks": asks}
            total_bid_q = sum(q for _, q in bids[:self.depth_levels])
            total_ask_q = sum(q for _, q in asks[:self.depth_levels])
            tot_depth = total_bid_q + total_ask_q
            static_imbalance = (total_bid_q - total_ask_q) / tot_depth if tot_depth > 0 else 0.0
            return {
                "symbol": sym,
                "best_bid": best_bid_p,
                "best_ask": best_ask_p,
                "spread_bps": round(spread_bps, 2),
                "ofi": 0.0,
                "nofi": round(static_imbalance, 4),
                "multi_level_ofi": 0.0,
                "queue_depletion": "NEUTRAL"
            }

        prev_bids = self.prev_state[sym]["bids"]
        prev_asks = self.prev_state[sym]["asks"]

        # Level 1 OFI
        eb_1 = self.compute_level_ofi(prev_bids[0][0], prev_bids[0][1], best_bid_p, best_bid_q, is_bid=True)
        ea_1 = self.compute_level_ofi(prev_asks[0][0], prev_asks[0][1], best_ask_p, best_ask_q, is_bid=False)
        ofi_1 = eb_1 + ea_1

        # Multi-level weighted OFI (decay weight = 1 / level)
        multi_ofi = 0.0
        total_weight = 0.0
        max_levels = min(len(bids), len(asks), len(prev_bids), len(prev_asks), self.depth_levels)

        for lvl in range(max_levels):
            w = 1.0 / (lvl + 1)
            eb_lvl = self.compute_level_ofi(prev_bids[lvl][0], prev_bids[lvl][1], bids[lvl][0], bids[lvl][1], is_bid=True)
            ea_lvl = self.compute_level_ofi(prev_asks[lvl][0], prev_asks[lvl][1], asks[lvl][0], asks[lvl][1], is_bid=False)
            multi_ofi += w * (eb_lvl + ea_lvl)
            total_weight += w

        weighted_ofi = multi_ofi / total_weight if total_weight > 0 else 0.0

        # Normalization NOFI in [-1.0, 1.0]
        denom = (best_bid_q + best_ask_q)
        nofi = ofi_1 / denom if denom > 0 else 0.0
        nofi = max(-1.0, min(1.0, nofi))

        # Detect queue depletion pressure
        if nofi > 0.40:
            depletion = "ASK_QUEUE_DEPLETION_BULLISH"
        elif nofi < -0.40:
            depletion = "BID_QUEUE_DEPLETION_BEARISH"
        else:
            depletion = "BALANCED"

        # Update cache
        self.prev_state[sym] = {"bids": bids, "asks": asks}

        return {
            "symbol": sym,
            "best_bid": best_bid_p,
            "best_ask": best_ask_p,
            "spread_bps": round(spread_bps, 2),
            "ofi": round(ofi_1, 2),
            "nofi": round(nofi, 4),
            "multi_level_ofi": round(weighted_ofi, 2),
            "queue_depletion": depletion
        }
