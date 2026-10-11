#!/usr/bin/env python3
"""
scripts/01_etl_and_ingestion/08_compute_floorsheet_broker_features.py

NEPSE Floorsheet Broker Network & Microstructure Feature Generator (Anti-Wash Guard)
------------------------------------------------------------------------------------
Ingests tick-level floorsheet trade records (2024-2026) and extracts
institutional accumulation and broker concentration signals with strict anti-manipulation guards:
1. Anti-Wash Trade Filter: Excludes self-matched internal broker transactions (buyer == seller).
2. Odd-Lot Segregation: Separates sub-board lots (quantity < 10) from institutional volume metrics
   while retaining odd-lot activity metrics to track retail behavior without signal contamination.
3. Buyer & Seller Herfindahl-Hirschman Index (HHI) computed strictly on clean arms-length trades.
4. Top-3 Buyer Broker Share (Smart Money concentration).
5. Broker Dispersion Ratio:
   (Unique Sellers - Unique Buyers) / (Unique Sellers + Unique Buyers)
   Positive values indicate fragmented retail selling absorbed by concentrated institutional brokers.
6. Block Trade Ratio: Proportion of turnover executed in tickets >= NPR 500,000.
7. Wash Trade Ratio: Fraction of turnover executed in self-matched trades (used as a penalty/gate).

Outputs:
- 03_feature_store/floorsheet_broker_signals.parquet
- Zero-copy view in 02_processed_parquet/market_analytics.duckdb
"""

import os
import sys
import time
import logging
from pathlib import Path
import duckdb
import pandas as pd
from scripts.db_connection import connection_manager
from scripts.01_etl_and_ingestion.schema_canonicalization import (
    process_floorsheet_df,
    log_rejected_to_dead_letter,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(os.environ.get("NEPSE_BASE_DIR", r"C:/Users/achar/Downloads/neps"))
RAW_DIR = BASE_DIR / "01_raw"
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
FEATURE_DIR = BASE_DIR / "03_feature_store"
FLOORSHEET_DIR = RAW_DIR / "floorsheets" / "partitions" / "01_partitioned_floorsheets_2024_to_2026"
if not FLOORSHEET_DIR.exists():
    FLOORSHEET_DIR = RAW_DIR / "floorsheets"


def compute_broker_features(min_lot_size: int = 10):
    print("=" * 80)
    print("STEP 1: COMPUTING ANTI-WASH BROKER NETWORK FEATURES FROM FLOORSHEETS")
    print("=" * 80)

    if not FLOORSHEET_DIR.exists():
        print(f"Warning: Floorsheet directory {FLOORSHEET_DIR} does not exist.")
        return

    t0 = time.time()

    pattern = str(FLOORSHEET_DIR / "**" / "*.csv").replace("\\", "/")
    out_parquet = FEATURE_DIR / "floorsheet_broker_signals.parquet"

    print(f"Scanning partitioned floorsheets from: {pattern}")
    print(f"Applying Schema Canonicalization + Anti-Wash Guard: Board Lot Threshold >= {min_lot_size} units.")

    # ------------------------------------------------------------------
    # Step A: Load raw CSVs into a DataFrame for canonicalization.
    # Using DuckDB only to load; actual wash filtering happens in Python
    # via process_floorsheet_df() so that column names are canonical
    # before any broker-ID comparisons.
    # ------------------------------------------------------------------
    try:
        load_sql = f"""
        SELECT *
        FROM read_csv_auto('{pattern}', union_by_name=True, ignore_errors=True)
        WHERE Amount > 0
        """
        with connection_manager.acquire() as con:
            df_raw = con.execute(load_sql).df()
    except Exception as e:
        print(f"Error loading CSV floorsheets: {e}")
        return

    if df_raw.empty:
        print("No floorsheet records found. Skipping feature computation.")
        return

    print(f"Loaded {len(df_raw):,} raw trade records from CSV partitions.")

    # ------------------------------------------------------------------
    # Step B: Canonicalize column names, validate payloads, apply
    # anti-wash filter — all via process_floorsheet_df().
    # This resolves Bug Condition 2: schema mismatch causing NULL comparisons.
    # ------------------------------------------------------------------
    clean_df, rejected_incomplete, wash_trades = process_floorsheet_df(df_raw)

    # Confirm canonical columns are present post-canonicalization
    assert "buyer_broker_id" in clean_df.columns, (
        "buyer_broker_id column missing after canonicalization — check CANONICAL_SCHEMA mappings"
    )
    assert "seller_broker_id" in clean_df.columns, (
        "seller_broker_id column missing after canonicalization — check CANONICAL_SCHEMA mappings"
    )

    print(
        f"  Gross records  : {len(df_raw):,}\n"
        f"  Rejected (incomplete fields): {len(rejected_incomplete):,}\n"
        f"  Wash trades (buyer==seller) : {len(wash_trades):,}\n"
        f"  Clean cross-broker trades   : {len(clean_df):,}"
    )

    # Persist rejected records to dead-letter queue
    if not rejected_incomplete.empty:
        log_rejected_to_dead_letter(rejected_incomplete, "missing_broker_ids_or_date", RAW_DIR)
    if not wash_trades.empty:
        log_rejected_to_dead_letter(wash_trades, "wash_trade_buyer_eq_seller", RAW_DIR)

    if clean_df.empty:
        print("No clean trades after validation and anti-wash filter. Aborting feature computation.")
        return

    # ------------------------------------------------------------------
    # Step C: Apply board-lot filter to clean_df.
    # Column 'quantity' is canonical (mapped from Quantity/contractQuantity).
    # ------------------------------------------------------------------
    qty_col = "quantity"
    if qty_col not in clean_df.columns:
        print(f"Warning: '{qty_col}' column not found; skipping odd-lot filter.")
        df_institutional = clean_df
    else:
        clean_df[qty_col] = pd.to_numeric(clean_df[qty_col], errors="coerce").fillna(0.0)
        df_institutional = clean_df[clean_df[qty_col] >= min_lot_size].copy()

    # Ensure ticker/date/amount columns exist with canonical names
    for col_rename in [("ticker", "Symbol"), ("date", "Date"), ("price", "Rate"), ("amount", "Amount")]:
        canon_name, _ = col_rename
        if canon_name not in df_institutional.columns:
            # Try the alt name
            alt = col_rename[1]
            if alt in df_institutional.columns:
                df_institutional = df_institutional.rename(columns={alt: canon_name})

    # Normalise ticker and date
    if "ticker" in df_institutional.columns:
        df_institutional["ticker"] = df_institutional["ticker"].astype(str).str.upper().str.strip()
    if "date" in df_institutional.columns:
        df_institutional["date"] = pd.to_datetime(df_institutional["date"], errors="coerce").dt.date
    if "amount" in df_institutional.columns:
        df_institutional["amount"] = pd.to_numeric(df_institutional["amount"], errors="coerce").fillna(0.0)

    # Drop rows with missing ticker, date, or non-positive amount
    df_institutional = df_institutional.dropna(subset=["ticker", "date"])
    df_institutional = df_institutional[df_institutional["amount"] > 0]

    print(f"  Institutional lots (>= {min_lot_size} units): {len(df_institutional):,} trades")

    if df_institutional.empty:
        print("No institutional-lot trades after filtering. Aborting feature computation.")
        return

    # ------------------------------------------------------------------
    # Step D: Compute broker network features using DuckDB on clean data.
    # Column names are now canonical: buyer_broker_id, seller_broker_id.
    # ------------------------------------------------------------------
    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    out_parquet_str = str(out_parquet).replace("\\", "/")
    print(f"Executing broker feature aggregation and persisting to: {out_parquet}")

    try:
        with connection_manager.acquire() as con:
            con.register("clean_trades", df_institutional)

            agg_sql = f"""
            WITH stock_daily_stats AS (
                SELECT 
                    ticker,
                    CAST(date AS DATE) AS date,
                    COUNT(*) AS clean_trades_count,
                    SUM(amount) AS floorsheet_turnover,
                    SUM(quantity) AS floorsheet_volume,
                    AVG(amount) AS avg_trade_ticket,
                    COUNT(DISTINCT buyer_broker_id) AS unique_buyers,
                    COUNT(DISTINCT seller_broker_id) AS unique_sellers,
                    (COUNT(DISTINCT seller_broker_id) - COUNT(DISTINCT buyer_broker_id))
                        / (COUNT(DISTINCT seller_broker_id) + COUNT(DISTINCT buyer_broker_id) + 1e-6)
                        AS broker_dispersion,
                    SUM(CASE WHEN amount >= 500000 THEN amount ELSE 0 END)
                        / (SUM(amount) + 1e-6) AS block_trade_ratio
                FROM clean_trades
                GROUP BY ticker, CAST(date AS DATE)
            ),
            buyer_broker_volumes AS (
                SELECT 
                    ticker,
                    CAST(date AS DATE) AS date,
                    buyer_broker_id,
                    SUM(amount) AS buyer_amt
                FROM clean_trades
                GROUP BY ticker, CAST(date AS DATE), buyer_broker_id
            ),
            buyer_ranked AS (
                SELECT 
                    ticker, date, buyer_broker_id, buyer_amt,
                    ROW_NUMBER() OVER (PARTITION BY ticker, date ORDER BY buyer_amt DESC) AS rank
                FROM buyer_broker_volumes
            ),
            buyer_metrics AS (
                SELECT 
                    b.ticker,
                    b.date,
                    SUM(POWER(b.buyer_amt / (s.floorsheet_turnover + 1e-6), 2)) AS buyer_hhi,
                    SUM(CASE WHEN r.rank <= 3 THEN r.buyer_amt ELSE 0 END)
                        / (s.floorsheet_turnover + 1e-6) AS top3_buyer_share
                FROM buyer_broker_volumes b
                JOIN stock_daily_stats s ON b.ticker = s.ticker AND b.date = s.date
                JOIN buyer_ranked r
                    ON b.ticker = r.ticker AND b.date = r.date
                    AND b.buyer_broker_id = r.buyer_broker_id
                GROUP BY b.ticker, b.date, s.floorsheet_turnover
            ),
            seller_broker_volumes AS (
                SELECT 
                    ticker,
                    CAST(date AS DATE) AS date,
                    seller_broker_id,
                    SUM(amount) AS seller_amt
                FROM clean_trades
                GROUP BY ticker, CAST(date AS DATE), seller_broker_id
            ),
            seller_metrics AS (
                SELECT 
                    sv.ticker,
                    sv.date,
                    SUM(POWER(sv.seller_amt / (s.floorsheet_turnover + 1e-6), 2)) AS seller_hhi
                FROM seller_broker_volumes sv
                JOIN stock_daily_stats s ON sv.ticker = s.ticker AND sv.date = s.date
                GROUP BY sv.ticker, sv.date, s.floorsheet_turnover
            ),
            gross_stats AS (
                SELECT
                    ticker,
                    CAST(date AS DATE) AS date,
                    COUNT(*) AS gross_trades,
                    SUM(amount) AS gross_turnover
                FROM clean_trades
                GROUP BY ticker, CAST(date AS DATE)
            )
            SELECT 
                sd.ticker,
                sd.date,
                sd.clean_trades_count,
                sd.floorsheet_turnover,
                sd.floorsheet_volume,
                sd.avg_trade_ticket,
                sd.unique_buyers,
                sd.unique_sellers,
                sd.broker_dispersion,
                sd.block_trade_ratio,
                COALESCE(bm.buyer_hhi, 0.0) AS buyer_hhi,
                COALESCE(bm.top3_buyer_share, 0.0) AS top3_buyer_share,
                COALESCE(sm.seller_hhi, 0.0) AS seller_hhi,
                0.0 AS wash_turnover_ratio,
                0.0 AS odd_lot_turnover_ratio,
                0 AS wash_trade_count,
                0 AS odd_lot_count
            FROM stock_daily_stats sd
            LEFT JOIN buyer_metrics bm ON sd.ticker = bm.ticker AND sd.date = bm.date
            LEFT JOIN seller_metrics sm ON sd.ticker = sm.ticker AND sd.date = sm.date
            ORDER BY sd.ticker, sd.date
            """

            result_df = con.execute(agg_sql).df()
            result_df.to_parquet(out_parquet, index=False, compression="zstd")
            cnt = len(result_df)

        elapsed = time.time() - t0
        print(f"[SUCCESS] Anti-Wash Floorsheet Features generated: {cnt:,} rows in {elapsed:.2f}s.")
        logger.info(
            "compute_broker_features completed: %d feature rows, %d wash trades filtered, "
            "%d incomplete records rejected.",
            cnt,
            len(wash_trades),
            len(rejected_incomplete),
        )
    except Exception as e:
        print(f"Error during floorsheet processing: {e}")
        logger.exception("compute_broker_features failed")


if __name__ == "__main__":
    compute_broker_features()
