#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/vpin_market_toxicity.py

APEXMARKETENGINE — VOLUME-SYNCHRONIZED PROBABILITY OF TOXICITY (VPIN) & KYLE'S LAMBDA
=====================================================================================
Quantitative Microstructure Engine for Detecting Informed Flow and Order Toxicity.
Based on Easley, López de Prado & O'Hara (2012) and Kyle (1985).

Mathematical Architecture:
1. Volume Bucketing:
   Partitions tick/floorsheet transaction stream into constant-volume buckets of size V
   (e.g., V = 5,000 shares for small-caps, V = 20,000 shares for liquid commercial banks).
2. Bulk Volume Classification (BVC):
   Splits volume in bucket tau into buy volume V_tau^B and sell volume V_tau^S:
   V_tau^B = V * Phi((P_tau - P_{tau-1}) / sigma_DeltaP)
   V_tau^S = V - V_tau^B
3. Volume-Synchronized Toxicity:
   VPIN = (sum_{tau=1}^N |V_tau^B - V_tau^S|) / (N * V) in [0, 1]
   - VPIN > 0.70 : Toxic flow alert (informed insider trading or aggressive institutional liquidation)
4. Kyle's Lambda (Price Impact per Share):
   lambda_Kyle = Delta P_tau / (V_tau^B - V_tau^S)
   Measures illiquidity and adverse price impact per share traded.
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
from scipy.stats import norm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [VPINToxicity] %(message)s"
)
logger = logging.getLogger("VPINToxicity")

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Dominant institutional and operator syndicate clusters in NEPSE
DEFAULT_BROKER_SYNDICATES: Dict[str, List[int]] = {
    "SYNDICATE_ALPHA_58_45_49": [58, 45, 49],
    "SYNDICATE_BETA_34_38_28": [34, 38, 28],
}


@dataclass
class VolumeBucket:
    bucket_index: int
    open_price: float
    close_price: float
    buy_volume: float
    sell_volume: float
    absolute_order_imbalance: float
    timestamp_end: str


@dataclass
class VPINReport:
    symbol: str
    bucket_size_shares: int
    total_buckets_evaluated: int
    vpin_score: float                  # [0.0, 1.0]
    kyles_lambda: float                # NPR price impact per 10k net shares
    is_flow_toxic: bool                # True if VPIN > 0.70
    toxicity_regime: str               # "BENIGN", "MODERATE_INFORMED", "HIGHLY_TOXIC_INSIDER_DISTRIBUTION"
    adverse_selection_cost_bps: float
    summary_notes: str


class VPINMarketToxicityEngine:
    """Calculates Volume-Synchronized Probability of Toxicity and Kyle's Lambda."""

    def __init__(self, bucket_size: int = 10_000, rolling_window_buckets: int = 20):
        self.bucket_size = bucket_size
        self.rolling_window = rolling_window_buckets

    def slice_into_volume_buckets(
        self,
        trades_df: pd.DataFrame
    ) -> List[VolumeBucket]:
        """
        Slices raw trade transactions (price, quantity, timestamp) into constant-volume buckets.
        Uses Bulk Volume Classification (BVC) to determine buy vs sell volume.
        """
        if trades_df.empty or "quantity" not in trades_df.columns or "price" not in trades_df.columns:
            return []

        buckets: List[VolumeBucket] = []
        cur_vol = 0
        cur_open = float(trades_df.iloc[0]["price"])
        prev_close = cur_open

        trade_prices = trades_df["price"].values
        price_diffs = np.diff(trade_prices, prepend=cur_open)
        sigma_p = np.std(price_diffs) if len(price_diffs) > 1 and np.std(price_diffs) > 0 else 0.50

        bucket_idx = 0
        cur_buy_vol = 0.0
        cur_sell_vol = 0.0

        for _, row in trades_df.iterrows():
            q = float(row["quantity"])
            p = float(row["price"])
            ts = str(row.get("tradeTime", row.get("date", datetime.now(timezone.utc).isoformat())))

            while q > 0:
                needed = self.bucket_size - cur_vol
                take_qty = min(q, needed)

                # Classify trade chunk via normalized price delta
                z = (p - prev_close) / sigma_p if sigma_p > 0 else 0.0
                buy_pct = float(norm.cdf(z))
                buy_pct = min(0.98, max(0.02, buy_pct))

                cur_buy_vol += take_qty * buy_pct
                cur_sell_vol += take_qty * (1.0 - buy_pct)
                cur_vol += take_qty
                q -= take_qty

                if cur_vol >= self.bucket_size:
                    # Finalize bucket
                    b = VolumeBucket(
                        bucket_index=bucket_idx,
                        open_price=cur_open,
                        close_price=p,
                        buy_volume=round(cur_buy_vol, 1),
                        sell_volume=round(cur_sell_vol, 1),
                        absolute_order_imbalance=round(abs(cur_buy_vol - cur_sell_vol), 1),
                        timestamp_end=ts
                    )
                    buckets.append(b)
                    bucket_idx += 1
                    cur_vol = 0
                    cur_buy_vol = 0.0
                    cur_sell_vol = 0.0
                    cur_open = p
                
                prev_close = p

        return buckets

    def calculate_vpin(
        self,
        symbol: str,
        trades_df: pd.DataFrame
    ) -> VPINReport:
        """Computes VPIN and Kyle's Lambda across the sliced volume buckets."""
        buckets = self.slice_into_volume_buckets(trades_df)

        if len(buckets) < 3:
            # Fallback for illiquid sessions with fewer than 3 volume buckets
            return VPINReport(
                symbol=symbol,
                bucket_size_shares=self.bucket_size,
                total_buckets_evaluated=len(buckets),
                vpin_score=0.25,
                kyles_lambda=0.05,
                is_flow_toxic=False,
                toxicity_regime="BENIGN",
                adverse_selection_cost_bps=5.0,
                summary_notes="Insufficient volume buckets to establish high-confidence toxicity profile."
            )

        eval_buckets = buckets[-self.rolling_window:]
        total_imbalance = sum(b.absolute_order_imbalance for b in eval_buckets)
        total_volume = len(eval_buckets) * self.bucket_size

        vpin = round(total_imbalance / total_volume, 4)

        # Calculate Kyle's Lambda: slope of Delta P vs Net Volume (V^B - V^S)
        price_deltas = [b.close_price - b.open_price for b in eval_buckets]
        net_volumes = [b.buy_volume - b.sell_volume for b in eval_buckets]

        cov_pv = np.cov(price_deltas, net_volumes)[0, 1] if len(eval_buckets) > 1 else 0.0
        var_v = np.var(net_volumes) if len(eval_buckets) > 1 and np.var(net_volumes) > 0 else 1.0
        # Kyle's lambda scaled to price impact per 10,000 net shares
        kyles_lambda = round(max(0.001, (cov_pv / var_v) * 10_000), 4)

        is_toxic = bool(vpin >= 0.70)
        if vpin >= 0.70:
            regime = "HIGHLY_TOXIC_INSIDER_DISTRIBUTION"
            notes = f"Critical toxic flow detected (VPIN: {vpin:.2f}). Aggressive informed traders actively draining liquidity."
        elif vpin >= 0.45:
            regime = "MODERATE_INFORMED"
            notes = f"Moderate informed activity (VPIN: {vpin:.2f}). Directional flow present."
        else:
            regime = "BENIGN"
            notes = f"Balanced uninformed retail flow (VPIN: {vpin:.2f}). Safe execution environment."

        adverse_cost_bps = round(vpin * kyles_lambda * 12.5, 2)

        return VPINReport(
            symbol=symbol,
            bucket_size_shares=self.bucket_size,
            total_buckets_evaluated=len(eval_buckets),
            vpin_score=vpin,
            kyles_lambda=kyles_lambda,
            is_flow_toxic=is_toxic,
            toxicity_regime=regime,
            adverse_selection_cost_bps=adverse_cost_bps,
            summary_notes=notes
        )

    def calculate_syndicate_cluster_vpin(
        self,
        symbol: str,
        floorsheet_trades: List[Dict[str, Any]],
        cluster_brokers: Optional[List[int]] = None,
        cluster_name: str = "SYNDICATE_ALPHA_58_45_49"
    ) -> Dict[str, Any]:
        """
        Aggregates buying and selling volume across co-moving broker clusters (e.g. Brokers 58, 45, 49)
        to detect cartel-coordinated accumulation sweeps or distributed liquidations.
        """
        target_cluster = cluster_brokers or DEFAULT_BROKER_SYNDICATES.get(cluster_name, [58, 45, 49])
        cluster_set = set(target_cluster)

        total_market_vol = 0.0
        cluster_buy_vol = 0.0
        cluster_sell_vol = 0.0

        for tr in floorsheet_trades:
            qty = float(tr.get("quantity", tr.get("contractQuantity", 0)))
            b_broker = int(tr.get("buyer_broker", tr.get("buyerBrokerId", tr.get("buyerMemberId", 0))))
            s_broker = int(tr.get("seller_broker", tr.get("sellerBrokerId", tr.get("sellerMemberId", 0))))

            total_market_vol += qty

            if b_broker in cluster_set:
                cluster_buy_vol += qty
            if s_broker in cluster_set:
                cluster_sell_vol += qty

        cluster_total_vol = cluster_buy_vol + cluster_sell_vol
        cluster_imbalance = abs(cluster_buy_vol - cluster_sell_vol)
        cluster_vpin = round(cluster_imbalance / max(cluster_total_vol, 1.0), 4)
        participation_pct = round((cluster_total_vol / max(total_market_vol, 1.0)) * 100.0, 2)

        is_toxic_sweep = cluster_vpin >= 0.70 and cluster_total_vol >= 5000.0
        if is_toxic_sweep and cluster_buy_vol > cluster_sell_vol:
            regime = "COORDINATED_SYNDICATE_ACCUMULATION_SWEEP"
        elif is_toxic_sweep and cluster_sell_vol > cluster_buy_vol:
            regime = "COORDINATED_SYNDICATE_DISTRIBUTION_SWEEP"
        elif cluster_vpin >= 0.45:
            regime = "MODERATE_SYNDICATE_DIRECTIONAL_FLOW"
        else:
            regime = "BALANCED_SYNDICATE_FLOW"

        return {
            "symbol": symbol.upper().strip(),
            "cluster_name": cluster_name,
            "cluster_brokers": list(target_cluster),
            "cluster_buy_volume": cluster_buy_vol,
            "cluster_sell_volume": cluster_sell_vol,
            "cluster_total_volume": cluster_total_vol,
            "cluster_order_imbalance": cluster_imbalance,
            "syndicate_cluster_vpin": cluster_vpin,
            "market_participation_pct": participation_pct,
            "is_toxic_cluster_sweep": is_toxic_sweep,
            "syndicate_regime": regime
        }


if __name__ == "__main__":
    engine = VPINMarketToxicityEngine(bucket_size=5_000, rolling_window_buckets=10)

    # Simulate 50,000 shares of aggressive selling in 500-share chunks
    np.random.seed(42)
    n_trades = 100
    prices = [500.0]
    for _ in range(n_trades - 1):
        prices.append(prices[-1] - np.random.uniform(0.1, 0.4)) # Steady downside drift
    quantities = [500] * n_trades

    df_test = pd.DataFrame({
        "price": prices,
        "quantity": quantities,
        "tradeTime": [f"12:{i:02d}:00" for i in range(n_trades)]
    })

    rep = engine.calculate_vpin("NICA", df_test)
    print("\n" + "=" * 70)
    print("      VOLUME-SYNCHRONIZED VPIN & KYLE'S LAMBDA TEST")
    print("=" * 70)
    print(f"Symbol:                   {rep.symbol}")
    print(f"Volume Buckets:           {rep.total_buckets_evaluated} (Size: {rep.bucket_size_shares:,} shares)")
    print(f"VPIN Score:               {rep.vpin_score:.4f} (Toxic Threshold: 0.70)")
    print(f"Kyle's Lambda:            {rep.kyles_lambda:.4f} NPR / 10k shares")
    print(f"Toxicity Regime:          {rep.toxicity_regime}")
    print(f"Flow Toxic Alert:         {rep.is_flow_toxic}")
    print(f"Adverse Cost:             {rep.adverse_selection_cost_bps:.1f} bps")
    print(f"Summary:                  {rep.summary_notes}")
    print("=" * 70)
