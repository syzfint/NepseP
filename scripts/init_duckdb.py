#!/usr/bin/env python3
"""
scripts/init_duckdb.py

Dedicated DuckDB Database Initialization & Schema Rebuilder
------------------------------------------------------------
Bridges the gap between untracked local data (.parquet, .csv) and the tracked codebase.
Automatically initializes:
1. 02_processed_parquet/news_and_events.duckdb (Event studies, NLP sentiment, disclosures)
2. 02_processed_parquet/market_analytics.duckdb (Columnar analytical views & queries)
3. Registers Zero-Copy views over local Parquet & CSV files if available.
4. Idempotent and safe to run on fresh clones (cold-start) or existing repositories.
"""

import os
import glob
from pathlib import Path
import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
FEATURE_DIR = BASE_DIR / "03_feature_store"
RAW_DIR = BASE_DIR / "01_raw"
LAKEHOUSE_DIR = BASE_DIR / "nepse_lakehouse"
DAILY_DIR = BASE_DIR / "nepse_data_all"
STATIC_DIR = BASE_DIR / "static_data"

import sys
sys.path.insert(0, str(BASE_DIR))
from scripts.03_data_access_and_storage.duckdb_connection_manager import get_connection_manager


import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def ensure_directories():
    """Ensure all required local directory structures exist."""
    for d in [PROCESSED_DIR, FEATURE_DIR, RAW_DIR, LAKEHOUSE_DIR, DAILY_DIR, STATIC_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    print("[OK] Local directory structures verified.")


def init_news_harness_db():
    """Initializes schema tables for news disclosures and event studies."""
    db_path = PROCESSED_DIR / "news_and_events.duckdb"
    news_mgr = get_connection_manager(database=str(db_path))
    with news_mgr.acquire() as conn:

        # 1. Raw disclosures table
        conn.execute("""
    CREATE TABLE IF NOT EXISTS raw_disclosures (
        raw_hash VARCHAR PRIMARY KEY,
        source VARCHAR NOT NULL,
        source_url VARCHAR NOT NULL,
        headline VARCHAR NOT NULL,
        body_text TEXT NOT NULL,
        published_npt TIMESTAMP NOT NULL,
        retrieved_at TIMESTAMP NOT NULL,
        verification_status VARCHAR NOT NULL,
        source_metadata JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

        # 2. Verified events table
        conn.execute("""
    CREATE TABLE IF NOT EXISTS verified_events (
        event_id VARCHAR PRIMARY KEY,
        source VARCHAR NOT NULL,
        source_url VARCHAR NOT NULL,
        headline VARCHAR NOT NULL,
        summary TEXT,
        body_hash VARCHAR NOT NULL,
        published_npt VARCHAR NOT NULL,
        retrieved_at VARCHAR NOT NULL,
        category VARCHAR NOT NULL,
        scope VARCHAR NOT NULL,
        confidence DOUBLE NOT NULL,
        classifier_version VARCHAR NOT NULL,
        importance_tier VARCHAR NOT NULL,
        published_date_npt VARCHAR NOT NULL,
        timing_convention VARCHAR NOT NULL,
        t0_date VARCHAR NOT NULL,
        t_minus_1_date VARCHAR NOT NULL,
        affected_broad_market BOOLEAN NOT NULL,
        affected_sectors JSON,
        affected_symbols JSON,
        mapping_rationale TEXT,
        status VARCHAR NOT NULL,
        verification_status VARCHAR NOT NULL,
        failure_reason TEXT,
        created_at VARCHAR NOT NULL
    );
    """)

        # 3. Pre-event Market Features (T-1 snapshot)
        conn.execute("""
    CREATE TABLE IF NOT EXISTS pre_event_market_features (
        event_id VARCHAR PRIMARY KEY,
        t_minus_1_date VARCHAR NOT NULL,
        market_turnover DOUBLE,
        market_return_1d DOUBLE,
        market_volatility_20d DOUBLE,
        market_breadth_advance_pct DOUBLE,
        is_valid BOOLEAN NOT NULL,
        missing_reason TEXT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

        # 4. Event study outcomes
        conn.execute("""
    CREATE TABLE IF NOT EXISTS event_study_outcomes (
        event_id VARCHAR PRIMARY KEY,
        t0_return_raw DOUBLE,
        t0_return_abnormal DOUBLE,
        h1_return_raw DOUBLE,
        h1_return_abnormal DOUBLE,
        h3_return_raw DOUBLE,
        h3_return_abnormal DOUBLE,
        h5_return_raw DOUBLE,
        h5_return_abnormal DOUBLE,
        is_statistically_significant BOOLEAN,
        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

        # 5. News audit logs
        conn.execute("""
    CREATE TABLE IF NOT EXISTS news_audit_logs (
        log_id BIGINT PRIMARY KEY,
        event_id VARCHAR,
        action VARCHAR NOT NULL,
        details TEXT,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE SEQUENCE IF NOT EXISTS news_audit_seq START 1;
    """)

        tables = conn.execute("SHOW TABLES").fetchall()
    return db_path, [t[0] for t in tables]


def init_market_analytics_db():
    """
    Initializes market_analytics.duckdb with zero-copy views
    over Parquet files and raw CSVs.
    """
    db_path = PROCESSED_DIR / "market_analytics.duckdb"
    analytics_mgr = get_connection_manager(database=str(db_path))
    with analytics_mgr.acquire() as conn:

        views_created = []

        # 1. Market Master Union
        master_parquet = PROCESSED_DIR / "market_master_union.parquet"
        if master_parquet.exists():
            sql_path = str(master_parquet).replace("\\", "/")
            conn.execute(f"CREATE OR REPLACE VIEW market_master_union AS SELECT * FROM read_parquet('{sql_path}');")
            count = conn.execute("SELECT COUNT(*) FROM market_master_union").fetchone()[0]
            views_created.append(("market_master_union (view)", f"{count:,} rows", "Parquet"))
        else:
            views_created.append(("market_master_union (view)", "Pending Hydration", "File not yet built"))

        # 2. Technical Indicators Feature Store
        tech_parquet = FEATURE_DIR / "technical_indicators.parquet"
        if tech_parquet.exists():
            sql_path = str(tech_parquet).replace("\\", "/")
            conn.execute(f"CREATE OR REPLACE VIEW technical_indicators AS SELECT * FROM read_parquet('{sql_path}');")
            count = conn.execute("SELECT COUNT(*) FROM technical_indicators").fetchone()[0]
            views_created.append(("technical_indicators (view)", f"{count:,} rows", "Parquet"))
        else:
            views_created.append(("technical_indicators (view)", "Pending Hydration", "File not yet built"))

        # 3. Sentiment Scores
        sentiment_parquet = FEATURE_DIR / "sentiment_scores.parquet"
        if sentiment_parquet.exists():
            sql_path = str(sentiment_parquet).replace("\\", "/")
            conn.execute(f"CREATE OR REPLACE VIEW sentiment_scores AS SELECT * FROM read_parquet('{sql_path}');")
            count = conn.execute("SELECT COUNT(*) FROM sentiment_scores").fetchone()[0]
            views_created.append(("sentiment_scores (view)", f"{count:,} rows", "Parquet"))
        else:
            views_created.append(("sentiment_scores (view)", "Pending Hydration", "File not yet built"))

        # 4. Lakehouse Ticks
        lakehouse_files = list(LAKEHOUSE_DIR.glob("**/*.parquet"))
        if lakehouse_files:
            sql_path = str(LAKEHOUSE_DIR / "**/*.parquet").replace("\\", "/")
            conn.execute(f"CREATE OR REPLACE VIEW lakehouse_ticks AS SELECT * FROM read_parquet('{sql_path}');")
            count = conn.execute("SELECT COUNT(*) FROM lakehouse_ticks").fetchone()[0]
            views_created.append(("lakehouse_ticks (view)", f"{count:,} rows ({len(lakehouse_files)} parts)", "Parquet Hive"))
        else:
            views_created.append(("lakehouse_ticks (view)", "Pending Hydration", "No tick files yet"))

        # 5. Raw Daily CSVs
        daily_csvs = list(DAILY_DIR.glob("*.csv"))
        if daily_csvs:
            sql_path = str(DAILY_DIR / "*.csv").replace("\\", "/")
            conn.execute(f"CREATE OR REPLACE VIEW nepse_daily_csvs AS SELECT * FROM read_csv_auto('{sql_path}', union_by_name=True);")
            views_created.append(("nepse_daily_csvs (view)", f"{len(daily_csvs)} CSV files registered", "CSV Auto"))

    return db_path, views_created


def main():
    print("=" * 70)
    print("APEXMARKETENGINE: DUCKDB DATABASE INITIALIZATION & SCHEMA REBUILD")
    print("=" * 70)

    ensure_directories()

    news_db, news_tables = init_news_harness_db()
    print(f"\n[1] News & Disclosures Database:")
    print(f"    Path:    {news_db}")
    print(f"    Tables:  {', '.join(news_tables)} ({len(news_tables)} tables initialized)")

    analytics_db, views = init_market_analytics_db()
    print(f"\n[2] Market Analytics Database:")
    print(f"    Path:    {analytics_db}")
    for name, stat, source in views:
        print(f"    * {name:<30} -> {stat:<25} [{source}]")

    print("\n" + "=" * 70)
    print("DUCKDB INITIALIZATION COMPLETE - SCHEMAS READY FOR VECTORIZATION & API")
    print("=" * 70)


if __name__ == "__main__":
    main()
