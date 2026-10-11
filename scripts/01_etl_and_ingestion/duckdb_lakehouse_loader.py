#!/usr/bin/env python3
"""
DuckDB Lakehouse Ingestion & Lakehouse Loader
============================================
Maintains 02_processed_parquet/market_master_union.parquet using DuckDB's
high-performance vectorized columnar engine.
Performs:
  - Multi-source union & priority-based deduplication
  - Out-of-core sorting by (ticker, date)
  - Security categorization (Ordinary vs Promoter / Debenture / Mutual Fund)
  - Fast zero-copy slicing for downstream ML modeling
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, List
import duckdb
import numpy as np
import pandas as pd
from scripts.db_connection import connection_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("duckdb_lakehouse")

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "01_raw"
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
ALT_BASE = Path(r"C:/Users/achar/Downloads/neps")


class DuckDBLakehouseLoader:
    def __init__(self, lakehouse_path: Optional[Path] = None):
        if lakehouse_path:
            self.parquet_path = Path(lakehouse_path)
        else:
            local_p = PROCESSED_DIR / "market_master_union.parquet"
            alt_p = ALT_BASE / "02_processed_parquet" / "market_master_union.parquet"
            if local_p.exists():
                self.parquet_path = local_p
            elif alt_p.exists():
                self.parquet_path = alt_p
            else:
                self.parquet_path = local_p

        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)

    def get_summary_stats(self) -> dict:
        """Returns row count, ticker count, and date ranges."""
        if not self.parquet_path.exists():
            return {"exists": False, "rows": 0, "tickers": 0}

        p_str = str(self.parquet_path).replace("\\", "/")
        with connection_manager.acquire() as con:
            res = con.execute(f"""
                SELECT 
                    COUNT(*) as total_rows,
                    COUNT(DISTINCT ticker) as total_tickers,
                    MIN(date) as min_date,
                    MAX(date) as max_date
                FROM read_parquet('{p_str}')
            """).fetchone()

        return {
            "exists": True,
            "path": str(self.parquet_path),
            "rows": res[0],
            "tickers": res[1],
            "min_date": str(res[2]),
            "max_date": str(res[3]),
        }

    def load_ticker_data(self, ticker: str, min_date: Optional[str] = None, adjusted: bool = True) -> pd.DataFrame:
        """
        Loads price history for a given ticker.
        If adjusted=True, applies backward ratio adjustments on detected book-closure
        and split drop anomalies (overnight drop < -15% violating NEPSE circuit limits),
        preventing false crashes in sequence models.
        """
        if not self.parquet_path.exists():
            return pd.DataFrame()

        p_str = str(self.parquet_path).replace("\\", "/")
        date_filter = f"AND date >= '{min_date}'" if min_date else ""
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM read_parquet('{p_str}')
            WHERE ticker = '{ticker.upper().strip()}' {date_filter}
            ORDER BY date ASC
        """
        df = self.con.execute(query).df()
        if df.empty or not adjusted or len(df) < 5:
            return df

        # Detect unadjusted split / book-closure drops (< -15%)
        df = df.copy()
        raw_rets = df["close"].pct_change()
        split_mask = (raw_rets <= -0.15) & (df["close"].shift(1) > 0)
        split_indices = df.index[split_mask].tolist()

        if split_indices:
            adj_factors = np.ones(len(df))
            for idx in reversed(split_indices):
                prev_c = df.loc[idx - 1, "close"]
                cur_c = df.loc[idx, "close"]
                if prev_c > 0 and cur_c > 0:
                    ratio = cur_c / prev_c
                    # Scale all historical prices prior to ex-date
                    adj_factors[:idx] *= ratio

            df["open"] = df["open"] * adj_factors
            df["high"] = df["high"] * adj_factors
            df["low"] = df["low"] * adj_factors
            df["close"] = df["close"] * adj_factors
            df["is_split_adjusted"] = True
        else:
            df["is_split_adjusted"] = False

        return df

    def load_active_universe(self, min_date: str = "2024-01-01", min_trading_days: int = 100) -> List[str]:
        """Returns list of active, liquid scrips."""
        if not self.parquet_path.exists():
            return []

        p_str = str(self.parquet_path).replace("\\", "/")
        query = f"""
            SELECT ticker, COUNT(*) as cnt
            FROM read_parquet('{p_str}')
            WHERE date >= '{min_date}' AND security_type = 'ORDINARY_EQUITY'
            GROUP BY ticker
            HAVING cnt >= {min_trading_days}
            ORDER BY cnt DESC
        """
        df = self.con.execute(query).df()
        return df["ticker"].tolist()


def main():
    logger.info("Initializing DuckDBLakehouseLoader...")
    loader = DuckDBLakehouseLoader()
    stats = loader.get_summary_stats()
    print("Lakehouse Summary:", stats)

    if stats.get("exists"):
        active = loader.load_active_universe(min_date="2025-01-01", min_trading_days=50)
        print(f"Active liquid equities (2025+): {len(active)} tickers. Sample: {active[:10]}")
        sample_df = loader.load_ticker_data("NABIL")
        print(f"Loaded {len(sample_df)} rows for NABIL.")


if __name__ == "__main__":
    main()
