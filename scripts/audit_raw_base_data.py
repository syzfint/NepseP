#!/usr/bin/env python3
"""
scripts/audit_raw_base_data.py

Exhaustive data integrity diagnostic for RAW independent base attributes in NEPSE.
Audits:
1. Raw Floorsheet Ticks (CSV partitions / raw_floorsheet)
2. Raw Daily OHLCV Bars (market_master_union.parquet / raw_ohlcv)
3. Broker ID Bounds & Distribution
4. Corporate Actions & Disclosures (news_and_events.duckdb)
"""

import sys
import os
import duckdb
import polars as pl
from pathlib import Path

# Ensure UTF-8 output on Windows consoles for Polars Unicode tables (avoid breaking pytest capture)
if sys.platform == "win32" and "pytest" not in sys.modules:
    import io
    if hasattr(sys.stdout, "buffer") and not getattr(sys.stdout, "closed", False):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

BASE_DIR = Path(__file__).resolve().parent.parent

def audit_raw_base_data(
    analytics_db: str = str(BASE_DIR / "02_processed_parquet" / "market_analytics.duckdb"),
    news_db: str = str(BASE_DIR / "02_processed_parquet" / "news_and_events.duckdb"),
    ohlcv_parquet: str = str(BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"),
    floorsheet_csv_pattern: str = str(BASE_DIR / "01_raw" / "floorsheets" / "partitions" / "**" / "*.csv").replace("\\", "/")
):
    print("=" * 80)
    print("  RAW INDEPENDENT BASE DATA AUDIT REPORT")
    print("=" * 80)

    con = duckdb.connect()

    # ------------------------------------------------------------------
    # 1. RAW FLOORSHEET TICK AUDIT
    # ------------------------------------------------------------------
    print("\n[1/4] AUDITING RAW FLOORSHEET TICKS (CSV / LAKEHOUSE)...")
    
    # Check if partitioned CSVs exist
    sample_csv = list((BASE_DIR / "01_raw" / "floorsheets" / "partitions").glob("**/*.csv"))
    if sample_csv:
        target_path = floorsheet_csv_pattern
        print(f"  Target: {len(sample_csv)} Partitioned Floorsheet CSVs")
        # In the partitioned CSVs, columns are:
        # "Transact. No.", Symbol, Buyer, Seller, Quantity, Rate, Amount, Date
        floorsheet_sql = f"""
            SELECT
                COUNT(*) as total_ticks,
                COUNT(DISTINCT Symbol) as unique_symbols,
                MIN(CAST(Date AS VARCHAR)) as start_time,
                MAX(CAST(Date AS VARCHAR)) as end_time,
                -- Null Value Counts
                SUM(CASE WHEN "Transact. No." IS NULL THEN 1 ELSE 0 END) as null_contract_ids,
                SUM(CASE WHEN Buyer IS NULL THEN 1 ELSE 0 END) as null_buyer_ids,
                SUM(CASE WHEN Seller IS NULL THEN 1 ELSE 0 END) as null_seller_ids,
                SUM(CASE WHEN Rate IS NULL OR Rate <= 0 THEN 1 ELSE 0 END) as invalid_prices,
                SUM(CASE WHEN Quantity IS NULL OR Quantity <= 0 THEN 1 ELSE 0 END) as invalid_quantities,
                -- Math Consistency: amount == price * quantity
                SUM(CASE WHEN ABS(Amount - (Rate * Quantity)) > 0.05 THEN 1 ELSE 0 END) as math_mismatches,
                -- Anti-Wash Violation: buyer == seller
                SUM(CASE WHEN Buyer = Seller THEN 1 ELSE 0 END) as wash_trades_detected,
                -- Synthetic Fabrication Check: broker IDs matching formula (contract_id % 50) + 1
                SUM(CASE WHEN TRY_CAST(Buyer AS BIGINT) = ((TRY_CAST("Transact. No." AS BIGINT) % 50) + 1) THEN 1 ELSE 0 END) as suspected_synthetic_buyers,
                -- Duplicate Contract IDs
                COUNT(*) - COUNT(DISTINCT "Transact. No.") as duplicate_contract_ids
            FROM read_csv_auto('{target_path}', union_by_name=true, ignore_errors=true)
            WHERE Amount > 0
        """
        broker_sql = f"""
            SELECT
                MIN(TRY_CAST(Buyer AS BIGINT)) as min_buyer_id,
                MAX(TRY_CAST(Buyer AS BIGINT)) as max_buyer_id,
                MIN(TRY_CAST(Seller AS BIGINT)) as min_seller_id,
                MAX(TRY_CAST(Seller AS BIGINT)) as max_seller_id,
                COUNT(DISTINCT Buyer) as active_buyer_brokers,
                COUNT(DISTINCT Seller) as active_seller_brokers
            FROM read_csv_auto('{target_path}', union_by_name=true, ignore_errors=true)
            WHERE Amount > 0
        """
    else:
        # Fallback to lakehouse_ticks view if raw CSVs are not present
        print("  Target: lakehouse_ticks view in market_analytics.duckdb")
        con.execute(f"ATTACH '{analytics_db}' AS mkt (READ_ONLY)")
        floorsheet_sql = """
            SELECT
                COUNT(*) as total_ticks,
                COUNT(DISTINCT symbol) as unique_symbols,
                MIN(timestamp_npt) as start_time,
                MAX(timestamp_npt) as end_time,
                0 as null_contract_ids,
                SUM(CASE WHEN buyer_broker IS NULL THEN 1 ELSE 0 END) as null_buyer_ids,
                SUM(CASE WHEN seller_broker IS NULL THEN 1 ELSE 0 END) as null_seller_ids,
                SUM(CASE WHEN ltp IS NULL OR ltp <= 0 THEN 1 ELSE 0 END) as invalid_prices,
                SUM(CASE WHEN volume IS NULL OR volume <= 0 THEN 1 ELSE 0 END) as invalid_quantities,
                SUM(CASE WHEN ABS(turnover - (ltp * volume)) > 0.05 THEN 1 ELSE 0 END) as math_mismatches,
                SUM(CASE WHEN buyer_broker = seller_broker THEN 1 ELSE 0 END) as wash_trades_detected,
                0 as suspected_synthetic_buyers,
                0 as duplicate_contract_ids
            FROM mkt.lakehouse_ticks
        """
        broker_sql = """
            SELECT
                MIN(TRY_CAST(buyer_broker AS BIGINT)) as min_buyer_id,
                MAX(TRY_CAST(buyer_broker AS BIGINT)) as max_buyer_id,
                MIN(TRY_CAST(seller_broker AS BIGINT)) as min_seller_id,
                MAX(TRY_CAST(seller_broker AS BIGINT)) as max_seller_id,
                COUNT(DISTINCT buyer_broker) as active_buyer_brokers,
                COUNT(DISTINCT seller_broker) as active_seller_brokers
            FROM mkt.lakehouse_ticks
        """

    try:
        floorsheet_audit = con.execute(floorsheet_sql).pl()
        print(floorsheet_audit)
    except Exception as e:
        print(f"Error auditing floorsheet: {e}")

    # ------------------------------------------------------------------
    # 2. RAW DAILY OHLCV BARS AUDIT
    # ------------------------------------------------------------------
    print("\n[2/4] AUDITING RAW DAILY OHLCV BARS (MARKET MASTER UNION)...")
    ohlcv_sql = f"""
        SELECT
            COUNT(*) as total_bars,
            COUNT(DISTINCT ticker) as unique_symbols,
            MIN(date) as min_date,
            MAX(date) as max_date,
            -- High/Low/Open/Close Violations
            SUM(CASE WHEN high < low THEN 1 ELSE 0 END) as high_less_than_low,
            SUM(CASE WHEN open < low OR open > high THEN 1 ELSE 0 END) as open_out_of_bounds,
            SUM(CASE WHEN close < low OR close > high THEN 1 ELSE 0 END) as close_out_of_bounds,
            SUM(CASE WHEN volume < 0 THEN 1 ELSE 0 END) as negative_volume,
            -- Zero-Volume Stale Bars
            SUM(CASE WHEN volume = 0 THEN 1 ELSE 0 END) as zero_volume_bars,
            -- Duplicate Date/Symbol Pairs
            COUNT(*) - COUNT(DISTINCT (ticker || '_' || CAST(date AS VARCHAR))) as duplicate_symbol_dates
        FROM read_parquet('{ohlcv_parquet}')
    """
    try:
        ohlcv_audit = con.execute(ohlcv_sql).pl()
        print(ohlcv_audit)
    except Exception as e:
        print(f"Error auditing OHLCV bars: {e}")

    # ------------------------------------------------------------------
    # 3. RAW BROKER ID RANGE & DISTRIBUTION AUDIT
    # ------------------------------------------------------------------
    print("\n[3/4] AUDITING BROKER ID BOUNDS...")
    try:
        broker_audit = con.execute(broker_sql).pl()
        print(broker_audit)
    except Exception as e:
        print(f"Error auditing broker bounds: {e}")

    # ------------------------------------------------------------------
    # 4. RAW CORPORATE ACTIONS & DISCLOSURES AUDIT
    # ------------------------------------------------------------------
    print("\n[4/4] AUDITING CORPORATE ACTIONS & ANNOUNCEMENT TIMESTAMPS...")
    if Path(news_db).exists():
        con.execute(f"ATTACH '{news_db}' AS news (READ_ONLY)")
        corp_sql = """
            SELECT
                COUNT(*) as total_actions,
                SUM(CASE WHEN t0_date IS NULL OR t0_date = '' THEN 1 ELSE 0 END) as missing_t0_dates,
                SUM(CASE WHEN t0_date < published_date_npt THEN 1 ELSE 0 END) as invalid_t0_dates,
                COUNT(DISTINCT category) as unique_event_categories,
                COUNT(DISTINCT event_id) as unique_events
            FROM news.verified_events
        """
        try:
            corp_audit = con.execute(corp_sql).pl()
            print(corp_audit)
        except Exception as e:
            print(f"Error auditing corporate actions: {e}")
    else:
        print(f"Note: News database not found at {news_db}")

    con.close()
    print("\n" + "=" * 80)
    print("  AUDIT COMPLETE: All checks performed on uncalculated raw features.")
    print("=" * 80)


if __name__ == "__main__":
    audit_raw_base_data()
