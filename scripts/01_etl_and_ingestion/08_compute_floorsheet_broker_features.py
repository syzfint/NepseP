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
from pathlib import Path
import duckdb

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
    con = duckdb.connect(database=":memory:")
    
    pattern = str(FLOORSHEET_DIR / "**" / "*.csv").replace("\\", "/")
    out_parquet = FEATURE_DIR / "floorsheet_broker_signals.parquet"

    print(f"Scanning partitioned floorsheets from: {pattern}")
    print(f"Applying Anti-Wash Guard: Exclude (buyer == seller) & Board Lot Threshold >= {min_lot_size} units.")

    sql = f"""
    WITH raw_trades AS (
        SELECT 
            UPPER(TRIM(Symbol)) AS ticker,
            CAST(Date AS DATE) AS date,
            CAST(Buyer AS VARCHAR) AS buyer,
            CAST(Seller AS VARCHAR) AS seller,
            CAST(Quantity AS DOUBLE) AS quantity,
            CAST(Rate AS DOUBLE) AS price,
            CAST(Amount AS DOUBLE) AS amount,
            (CAST(Buyer AS VARCHAR) = CAST(Seller AS VARCHAR)) AS is_wash_trade,
            (CAST(Quantity AS DOUBLE) < {min_lot_size}) AS is_odd_lot
        FROM read_csv_auto('{pattern}', union_by_name=True, ignore_errors=True)
        WHERE Symbol IS NOT NULL AND Amount > 0 AND Date IS NOT NULL
    ),
    all_trade_stats AS (
        SELECT 
            ticker,
            date,
            COUNT(*) AS gross_trades,
            SUM(amount) AS gross_turnover,
            SUM(CASE WHEN is_wash_trade THEN amount ELSE 0 END) AS wash_turnover,
            SUM(CASE WHEN is_odd_lot THEN amount ELSE 0 END) AS odd_lot_turnover,
            SUM(CASE WHEN is_wash_trade THEN 1 ELSE 0 END) AS wash_trade_count,
            SUM(CASE WHEN is_odd_lot THEN 1 ELSE 0 END) AS odd_lot_count
        FROM raw_trades
        GROUP BY ticker, date
    ),
    clean_trades AS (
        SELECT *
        FROM raw_trades
        WHERE NOT is_wash_trade AND NOT is_odd_lot
    ),
    stock_daily_stats AS (
        SELECT 
            ticker,
            date,
            COUNT(*) AS clean_trades_count,
            SUM(amount) AS floorsheet_turnover,
            SUM(quantity) AS floorsheet_volume,
            AVG(amount) AS avg_trade_ticket,
            COUNT(DISTINCT buyer) AS unique_buyers,
            COUNT(DISTINCT seller) AS unique_sellers,
            (COUNT(DISTINCT seller) - COUNT(DISTINCT buyer)) / (COUNT(DISTINCT seller) + COUNT(DISTINCT buyer) + 1e-6) AS broker_dispersion,
            SUM(CASE WHEN amount >= 500000 THEN amount ELSE 0 END) / (SUM(amount) + 1e-6) AS block_trade_ratio
        FROM clean_trades
        GROUP BY ticker, date
    ),
    buyer_broker_volumes AS (
        SELECT ticker, date, buyer, SUM(amount) AS buyer_amt
        FROM clean_trades
        GROUP BY ticker, date, buyer
    ),
    buyer_ranked AS (
        SELECT 
            ticker, date, buyer, buyer_amt,
            ROW_NUMBER() OVER (PARTITION BY ticker, date ORDER BY buyer_amt DESC) as rank
        FROM buyer_broker_volumes
    ),
    buyer_metrics AS (
        SELECT 
            b.ticker,
            b.date,
            SUM(POWER(b.buyer_amt / (s.floorsheet_turnover + 1e-6), 2)) AS buyer_hhi,
            SUM(CASE WHEN r.rank <= 3 THEN r.buyer_amt ELSE 0 END) / (s.floorsheet_turnover + 1e-6) AS top3_buyer_share
        FROM buyer_broker_volumes b
        JOIN stock_daily_stats s ON b.ticker = s.ticker AND b.date = s.date
        JOIN buyer_ranked r ON b.ticker = r.ticker AND b.date = r.date AND b.buyer = r.buyer
        GROUP BY b.ticker, b.date, s.floorsheet_turnover
    ),
    seller_broker_volumes AS (
        SELECT ticker, date, seller, SUM(amount) AS seller_amt
        FROM clean_trades
        GROUP BY ticker, date, seller
    ),
    seller_metrics AS (
        SELECT 
            s_brk.ticker,
            s_brk.date,
            SUM(POWER(s_brk.seller_amt / (s.floorsheet_turnover + 1e-6), 2)) AS seller_hhi
        FROM seller_broker_volumes s_brk
        JOIN stock_daily_stats s ON s_brk.ticker = s.ticker AND s_brk.date = s.date
        GROUP BY s_brk.ticker, s_brk.date, s.floorsheet_turnover
    )
    SELECT 
        s.ticker,
        s.date,
        s.clean_trades_count,
        s.floorsheet_turnover,
        s.floorsheet_volume,
        s.avg_trade_ticket,
        s.unique_buyers,
        s.unique_sellers,
        s.broker_dispersion,
        s.block_trade_ratio,
        COALESCE(b.buyer_hhi, 0.0) AS buyer_hhi,
        COALESCE(b.top3_buyer_share, 0.0) AS top3_buyer_share,
        COALESCE(sm.seller_hhi, 0.0) AS seller_hhi,
        COALESCE(a.wash_turnover / (a.gross_turnover + 1e-6), 0.0) AS wash_turnover_ratio,
        COALESCE(a.odd_lot_turnover / (a.gross_turnover + 1e-6), 0.0) AS odd_lot_turnover_ratio,
        a.wash_trade_count,
        a.odd_lot_count
    FROM stock_daily_stats s
    JOIN all_trade_stats a ON s.ticker = a.ticker AND s.date = a.date
    LEFT JOIN buyer_metrics b ON s.ticker = b.ticker AND s.date = b.date
    LEFT JOIN seller_metrics sm ON s.ticker = sm.ticker AND s.date = sm.date
    ORDER BY s.ticker, s.date
    """

    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    out_str = str(out_parquet).replace("\\", "/")
    print(f"Executing query and persisting to: {out_parquet}")

    try:
        con.execute(f"COPY ({sql}) TO '{out_str}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_str}')").fetchone()[0]
        elapsed = time.time() - t0
        print(f"[SUCCESS] Anti-Wash Floorsheet Features generated: {cnt:,} rows in {elapsed:.2f}s.")
    except Exception as e:
        print(f"Error during floorsheet processing: {e}")


if __name__ == "__main__":
    compute_broker_features()
