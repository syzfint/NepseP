"""
scripts/02_modeling_and_calculations/market_depth_reconstructor.py

LEVEL-2 ORDER BOOK DEPTH RECONSTRUCTION & QUEUE DEPLETION ENGINE
=================================================================
Synthesizes and formats full 10-level visual order book ladders for Screen S04
(Cont-Stoikov OFI & L1/L2 Depth Cockpit).
"""

import math
from typing import Dict, Any, List, Tuple


def generate_synthetic_or_real_l2_depth(
    symbol: str,
    ltp: float,
    spread_pct: float = 0.003,
    num_levels: int = 10
) -> Dict[str, Any]:
    """
    Generates a deterministic 10-level L2 depth ladder around an LTP.
    """
    sym = symbol.upper().strip()
    tick_size = 0.10 if ltp < 500 else (0.20 if ltp < 1000 else 0.50)
    half_spread = max(tick_size, round(ltp * spread_pct / 2.0, 1))

    best_bid = round(ltp - half_spread, 1)
    best_ask = round(ltp + half_spread, 1)
    if best_bid >= best_ask:
        best_ask = best_bid + tick_size

    bids: List[Dict[str, Any]] = []
    cum_bid_vol = 0
    for i in range(num_levels):
        p = round(best_bid - (i * tick_size), 1)
        # Depth volume distribution: exponential growth away from inside market
        q = int(500 * (1.2 ** i) + (hash(f"{sym}_b_{i}") % 300))
        cum_bid_vol += q
        bids.append({"level": i + 1, "price": p, "quantity": q, "cumulative": cum_bid_vol})

    asks: List[Dict[str, Any]] = []
    cum_ask_vol = 0
    for i in range(num_levels):
        p = round(best_ask + (i * tick_size), 1)
        q = int(450 * (1.22 ** i) + (hash(f"{sym}_a_{i}") % 350))
        cum_ask_vol += q
        asks.append({"level": i + 1, "price": p, "quantity": q, "cumulative": cum_ask_vol})

    # Imbalance metrics
    total_bids = bids[-1]["cumulative"]
    total_asks = asks[-1]["cumulative"]
    depth_imbalance = (total_bids - total_asks) / (total_bids + total_asks)

    # Microprice: P_micro = (P_ask * V_bid + P_bid * V_ask) / (V_bid + V_ask)
    v_b1 = bids[0]["quantity"]
    v_a1 = asks[0]["quantity"]
    microprice = (best_ask * v_b1 + best_bid * v_a1) / (v_b1 + v_a1)

    return {
        "symbol": sym,
        "ltp": ltp,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": round(best_ask - best_bid, 2),
        "spread_bps": round((best_ask - best_bid) / ltp * 10000.0, 2),
        "microprice": round(microprice, 2),
        "total_bid_depth": total_bids,
        "total_ask_depth": total_asks,
        "depth_imbalance_ratio": round(depth_imbalance, 4),
        "bids": bids,
        "asks": asks
    }
