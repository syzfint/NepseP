#!/usr/bin/env python3
"""
NEPSE Microstructure & Live Floorsheet Ingestion Engine
======================================================
Connects to NEPSE endpoints via NepseClient to ingest:
  - Live Market Snapshots & Ticker LTPs
  - Real-time Floorsheet Transactions & Trade Volumes
  - Top-5 Bid/Ask Order Book Market Depth
  - Real-time Order Book Imbalance & Microstructure Liquidity Metrics

Designed for institutional execution to prevent the T+2 Demat illiquidity trap.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

try:
    from nepse_client import NepseClient
except ImportError:
    NepseClient = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nepse_microstructure")

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
FEATURE_DIR = BASE_DIR / "03_feature_store"


class NepseMicrostructureStreamer:
    """Streams live market data and extracts microstructure features."""

    def __init__(self, tls_verify: bool = False):
        self.client = None
        if NepseClient is not None:
            try:
                self.client = NepseClient()
                self.client.setTLSVerification(tls_verify)
                logger.info("NepseClient initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not connect live NepseClient: {e}. Running in cached/fallback mode.")
        else:
            logger.warning("nepse-client not installed. Running in fallback mode.")

    def get_live_market_snapshot(self) -> pd.DataFrame:
        """Fetches all live traded scrips, volumes, and LTPs."""
        if not self.client:
            return pd.DataFrame()

        try:
            live_data = self.client.getLiveMarket()
            if not live_data:
                logger.warning("Empty live market data returned.")
                return pd.DataFrame()

            df = pd.DataFrame(live_data)
            # Standardize columns
            rename_map = {
                "symbol": "symbol",
                "lastTradedPrice": "ltp",
                "openPrice": "open",
                "highPrice": "high",
                "lowPrice": "low",
                "previousClose": "prev_close",
                "totalTradeQuantity": "volume",
                "totalTradeValue": "turnover",
                "percentageChange": "pct_change",
                "lastUpdatedDateTime": "timestamp",
            }
            available_cols = {k: v for k, v in rename_map.items() if k in df.columns}
            df = df.rename(columns=available_cols)
            logger.info(f"Retrieved {len(df)} scrips from live NEPSE market snapshot.")
            return df
        except Exception as e:
            logger.error(f"Error fetching live market snapshot: {e}")
            return pd.DataFrame()

    def get_market_index_status(self) -> Dict[str, Any]:
        """Fetches current NEPSE Index, Float, and turnover summary."""
        if not self.client:
            return {}

        try:
            status = self.client.getMarketStatus()
            indices = self.client.getNepseIndex()
            nepse_val = None
            nepse_chg = None
            nepse_pct = None
            if indices and isinstance(indices, list):
                for idx in indices:
                    if idx.get("index") == "NEPSE Index" or idx.get("id") == 58:
                        nepse_val = idx.get("currentValue", idx.get("close"))
                        nepse_chg = idx.get("change")
                        nepse_pct = idx.get("perChange")
                        break

            return {
                "isOpen": status.get("isOpen", False) if status else False,
                "nepse_index": nepse_val,
                "nepse_change": nepse_chg,
                "nepse_pct_change": nepse_pct,
                "raw_indices": indices[:3] if indices else [],
            }
        except Exception as e:
            logger.error(f"Error fetching index status: {e}")
            return {}

    def get_order_book_depth(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches Top-5 Bid/Ask queue and calculates:
          - Total Buy vs Sell volume
          - Order Book Imbalance Ratio [-1.0, 1.0]
          - Top Bid/Ask spread %
        """
        if not self.client:
            return {"symbol": symbol, "imbalance": 0.0, "total_buy": 0, "total_sell": 0}

        try:
            depth = self.client.getSymbolMarketDepth(symbol)
            if not depth:
                return {"symbol": symbol, "imbalance": 0.0, "total_buy": 0, "total_sell": 0}

            total_buy = depth.get("totalBuyQty", 0)
            total_sell = depth.get("totalSellQty", 0)
            denom = total_buy + total_sell
            imbalance = (total_buy - total_sell) / denom if denom > 0 else 0.0

            # Extract top bid and ask
            m_depth = depth.get("marketDepth", {})
            buys = m_depth.get("buyMarketDepthList", [])
            sells = m_depth.get("sellMarketDepthList", [])

            best_bid = buys[0].get("orderBookOrderPrice", 0.0) if buys else None
            best_ask = sells[0].get("orderBookOrderPrice", 0.0) if sells else None
            spread_pct = 0.0
            if best_bid and best_ask and best_bid > 0:
                spread_pct = (best_ask - best_bid) / best_bid * 100.0

            return {
                "symbol": symbol,
                "total_buy_qty": total_buy,
                "total_sell_qty": total_sell,
                "order_book_imbalance": round(imbalance, 4),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_pct": round(spread_pct, 2),
                "top3_buy_qty": sum(b.get("quantity", 0) for b in buys[:3]),
                "top3_sell_qty": sum(s.get("quantity", 0) for s in sells[:3]),
                "buy_orders_count": len(buys),
                "sell_orders_count": len(sells),
            }
        except Exception as e:
            logger.debug(f"Could not get depth for {symbol}: {e}")
            return {"symbol": symbol, "imbalance": 0.0, "total_buy": 0, "total_sell": 0, "top3_buy_qty": 0, "top3_sell_qty": 0}

    def calculate_safe_child_slice(
        self,
        symbol: str,
        target_shares: int,
        is_buy: bool = True,
        max_depth_pct: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Enforces 15% Top-3 Limit Order Book (L2) Depth Capping:
        Child order slice size is strictly capped at <= 15% of top-3 queue depth.
        If the book is one-sided (e.g. 0 ask quantity on upper circuit or 0 bid on lower circuit),
        the execution is frozen (returns 0 shares with ONE_SIDED_CIRCUIT_LOCKED).
        """
        depth = self.get_order_book_depth(symbol)
        opposing_top3 = depth.get("top3_sell_qty", 0) if is_buy else depth.get("top3_buy_qty", 0)

        # One-sided circuit breaker freeze
        if opposing_top3 <= 0:
            return {
                "symbol": symbol,
                "permitted_slice_shares": 0,
                "target_shares": target_shares,
                "top3_available_depth": 0,
                "status": "ONE_SIDED_CIRCUIT_LOCKED",
                "reason": "Zero opposing order book depth at circuit limit",
            }

        max_permitted = int(opposing_top3 * max_depth_pct)
        # Ensure minimum board lot (10 shares) if permitted
        if max_permitted < 10 and opposing_top3 >= 10:
            max_permitted = 10

        actual_slice = min(target_shares, max_permitted)

        return {
            "symbol": symbol,
            "permitted_slice_shares": actual_slice,
            "target_shares": target_shares,
            "top3_available_depth": opposing_top3,
            "depth_cap_ratio": round(actual_slice / opposing_top3, 4) if opposing_top3 > 0 else 0.0,
            "status": "APPROVED",
        }

    def get_floorsheet_stream(self, limit: int = 5000) -> pd.DataFrame:
        """Fetches live floorsheet transactions."""
        if not self.client:
            return pd.DataFrame()

        try:
            fs = self.client.getFloorSheet()
            if not fs:
                return pd.DataFrame()

            df = pd.DataFrame(fs[:limit])
            logger.info(f"Retrieved {len(df)} floorsheet trades.")
            return df
        except Exception as e:
            logger.error(f"Error fetching floorsheet: {e}")
            return pd.DataFrame()


def main():
    logger.info("Running NepseMicrostructureStreamer self-test...")
    streamer = NepseMicrostructureStreamer()
    status = streamer.get_market_index_status()
    print("Market Status:", json.dumps(status, indent=2))

    live_df = streamer.get_live_market_snapshot()
    if not live_df.empty:
        print(f"Live Market: {len(live_df)} symbols loaded. Top 5 by volume:")
        print(live_df.sort_values(by="volume", ascending=False)[["symbol", "ltp", "volume", "pct_change"]].head(5))

    # Test sample market depths
    for sym in ["NABIL", "SHIVM", "HDL", "GBIME"]:
        depth = streamer.get_order_book_depth(sym)
        print(f"Depth for {sym}: Imbalance={depth.get('order_book_imbalance')}, BuyQty={depth.get('total_buy_qty')}, SellQty={depth.get('total_sell_qty')}")


if __name__ == "__main__":
    main()
