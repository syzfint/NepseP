#!/usr/bin/env python3
"""
scripts/01_etl_and_ingestion/build_promoter_lockin_calendar.py

Promoter Share 3-Year Lock-In Expiry Calendar Builder
=====================================================
Under SEBON / NEPSE listing regulations, promoter shares of newly listed companies
(especially Hydropower and Microfinance) are legally locked in for exactly 3 years (36 months)
from their official initial listing date.

When this 3-year lock-in period expires:
  - 70% to 80% of total company equity is unlocked as tradeable shares.
  - A massive supply overhang dumps into the secondary market.
  - Pure technical models suffer catastrophic false buy signals.

This module:
1. Extracts initial listing dates (min_date) for all listed ordinary equities from the lakehouse.
2. Computes the statutory 3-year lock-in expiry date:
     lockin_expiry_date = listing_date + 36 months (1,095 days).
3. Defines the Freeze Window:
     [lockin_expiry_date - 15 days, lockin_expiry_date + 30 days].
4. Persists static_data/promoter_lockin.parquet for zero-latency Gate G4 auditing.
"""

import sys
import logging
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np
from scripts.03_data_access_and_storage.duckdb_connection_manager import connection_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("promoter_lockin")

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_PARQUET = BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"
STATIC_DIR = BASE_DIR / "static_data"
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")
OUT_PARQUET = STATIC_DIR / "promoter_lockin.parquet"


def build_promoter_lockin_calendar():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    p_str = str(PROCESSED_PARQUET).replace("\\", "/")

    query = f"""
    SELECT 
        ticker as symbol,
        MIN(date) as ipo_listing_date,
        MAX(date) as latest_trade_date,
        COUNT(*) as total_trading_sessions
    FROM read_parquet('{p_str}')
    WHERE security_type = 'ORDINARY_EQUITY'
    GROUP BY ticker
    ORDER BY ipo_listing_date ASC
    """
    with connection_manager.acquire() as con:
        df = con.execute(query).df()
    df["ipo_listing_date"] = pd.to_datetime(df["ipo_listing_date"])
    df["latest_trade_date"] = pd.to_datetime(df["latest_trade_date"])

    # Statutory 3-year lock-in period = 36 months (approx 1095 days / DateOffset)
    df["lockin_expiry_date"] = df["ipo_listing_date"] + pd.DateOffset(years=3)
    df["freeze_window_start"] = df["lockin_expiry_date"] - pd.Timedelta(days=15)
    df["freeze_window_end"] = df["lockin_expiry_date"] + pd.Timedelta(days=30)

    # Flag companies whose lock-in expires between 2024 and 2027 (Active risk cohort)
    df["is_recent_ipo"] = df["ipo_listing_date"] >= "2021-01-01"

    out_str = str(OUT_PARQUET).replace("\\", "/")
    with connection_manager.acquire() as con:
        con.execute(f"COPY (SELECT * FROM df) TO '{out_str}' (FORMAT PARQUET)")
    logger.info(f"Generated promoter lock-in calendar: {len(df)} companies saved to {OUT_PARQUET}")

    # Mirror to ALT_DIR
    if ALT_DIR.exists():
        alt_out = ALT_DIR / "static_data" / "promoter_lockin.parquet"
        alt_out.parent.mkdir(parents=True, exist_ok=True)
        try:
            alt_out.write_bytes(OUT_PARQUET.read_bytes())
            logger.info(f"Mirrored to {alt_out}")
        except Exception:
            pass

    return df


def check_promoter_lockin_risk(symbol: str, as_of_date: str = "2026-10-07") -> dict:
    """Checks if a given symbol is currently within its 3-year lock-in supply dump freeze window."""
    if not OUT_PARQUET.exists():
        build_promoter_lockin_calendar()

    p_str = str(OUT_PARQUET).replace("\\", "/")
    with connection_manager.acquire() as con:
        res = con.execute(f"""
            SELECT 
                symbol,
                ipo_listing_date,
                lockin_expiry_date,
                freeze_window_start,
                freeze_window_end,
                is_recent_ipo
            FROM read_parquet('{p_str}')
            WHERE symbol = '{symbol.upper().strip()}'
        """).fetchone()

    if not res:
        return {"has_lockin_risk": False, "reason": "No listing record"}

    sym, listing_dt, expiry_dt, start_dt, end_dt, is_recent = res
    cur_dt = pd.to_datetime(as_of_date)

    in_window = (cur_dt >= start_dt) and (cur_dt <= end_dt)
    return {
        "symbol": sym,
        "has_lockin_risk": bool(in_window),
        "ipo_listing_date": str(listing_dt)[:10],
        "lockin_expiry_date": str(expiry_dt)[:10],
        "freeze_window": f"{str(start_dt)[:10]} to {str(end_dt)[:10]}",
        "is_recent_ipo": bool(is_recent),
    }


if __name__ == "__main__":
    df = build_promoter_lockin_calendar()
    print("Promoter Lock-In Calendar Sample (Recent IPOs):")
    recent = df[df["is_recent_ipo"]].head(10)
    print(recent[["symbol", "ipo_listing_date", "lockin_expiry_date", "freeze_window_start", "freeze_window_end"]])

    # Test check
    print("\nTest Check on Sample Ticker:")
    print(check_promoter_lockin_risk("SARBTM", "2026-10-07"))
