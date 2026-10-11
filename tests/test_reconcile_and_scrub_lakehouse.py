"""
tests/test_reconcile_and_scrub_lakehouse.py

Unit & Integration Test Suite for Phase 1 Lakehouse Reconciliation & Scrubbing Pipeline.
Validates:
1. Stage 1: Wash trade detection (buyer == seller -> is_wash_trade = TRUE).
2. Stage 1: Synthetic broker ID nullification ((contract_id % 50) + 1 -> NULL).
3. Stage 1: Math corruption quarantine into data_quarantine (price <= 0, volume <= 0).
4. Stage 2: External anchor reconciliation & discrepancy patching (PATCHED_FROM_ANCHOR, VERIFIED).
5. Stage 3: Atomic staging & OS swap with DuckDBConnectionManager pool safety.
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import duckdb
import polars as pl
import pytest

from scripts.db_connection import get_connection_manager, DuckDBConnectionManager
from scripts.reconcile_and_scrub_lakehouse import LakehouseReconciliationPipeline


@pytest.fixture
def test_env(tmp_path):
    """Set up an isolated lakehouse sandbox environment with mock tick and anchor data."""
    processed_dir = tmp_path / "02_processed_parquet"
    processed_dir.mkdir(parents=True)
    raw_data_dir = tmp_path / "01_raw_data"
    raw_data_dir.mkdir(parents=True)
    raw_anchor_dir = tmp_path / "01_raw" / "nepse-data-main" / "nepse-data-main" / "data" / "company-wise"
    raw_anchor_dir.mkdir(parents=True)
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True)

    # 1. Create a mock market_analytics.duckdb
    db_path = processed_dir / "market_analytics.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE mock_existing (id INT);")
    con.close()

    # 2. Create mock raw floorsheet parquet with:
    # - Normal valid arm's length trades
    # - Wash trades (buyer == seller)
    # - Synthetic broker trades (buyer == (contract_id % 50) + 1)
    # - Corrupt math trades (price <= 0, volume <= 0)
    # - Discrepancy trades needing anchor patching
    raw_ticks = [
        # Normal arm's length trade
        {
            "contractId": 2026100700000001,
            "stockSymbol": "NABIL",
            "buyerMemberId": "45",
            "sellerMemberId": "58",
            "contractQuantity": 100.0,
            "contractRate": 1000.0,
            "contractAmount": 100000.0,
            "businessDate": "2026-10-07",
            "tradeTime": "2026-10-07T11:00:00",
        },
        # Wash trade (buyer == seller)
        {
            "contractId": 2026100700000002,
            "stockSymbol": "NABIL",
            "buyerMemberId": "34",
            "sellerMemberId": "34",
            "contractQuantity": 50.0,
            "contractRate": 1000.0,
            "contractAmount": 50000.0,
            "businessDate": "2026-10-07",
            "tradeTime": "2026-10-07T11:05:00",
        },
        # Synthetic buyer ID: contractId = 1000050 -> (1000050 % 50) + 1 = 1
        {
            "contractId": 1000050,
            "stockSymbol": "ADBL",
            "buyerMemberId": "1",  # matches synthetic formula
            "sellerMemberId": "28",
            "contractQuantity": 20.0,
            "contractRate": 300.0,
            "contractAmount": 6000.0,
            "businessDate": "2026-10-07",
            "tradeTime": "2026-10-07T11:10:00",
        },
        # Synthetic seller ID: contractId = 1000051 -> (1000051 % 50) + 1 = 2
        {
            "contractId": 1000051,
            "stockSymbol": "ADBL",
            "buyerMemberId": "25",
            "sellerMemberId": "2",  # matches synthetic formula
            "contractQuantity": 30.0,
            "contractRate": 300.0,
            "contractAmount": 9000.0,
            "businessDate": "2026-10-07",
            "tradeTime": "2026-10-07T11:15:00",
        },
        # Corrupt price (price <= 0)
        {
            "contractId": 2026100700000005,
            "stockSymbol": "NABIL",
            "buyerMemberId": "14",
            "sellerMemberId": "20",
            "contractQuantity": 100.0,
            "contractRate": -5.0,  # Corrupt
            "contractAmount": -500.0,
            "businessDate": "2026-10-07",
            "tradeTime": "2026-10-07T11:20:00",
        },
        # Corrupt volume (volume <= 0)
        {
            "contractId": 2026100700000006,
            "stockSymbol": "NABIL",
            "buyerMemberId": "14",
            "sellerMemberId": "20",
            "contractQuantity": 0.0,  # Corrupt
            "contractRate": 1000.0,
            "contractAmount": 0.0,
            "businessDate": "2026-10-07",
            "tradeTime": "2026-10-07T11:25:00",
        },
        # Discrepancy row: wild price spike outside anchor bounds -> should be patched
        {
            "contractId": 2026100700000007,
            "stockSymbol": "NABIL",
            "buyerMemberId": "12",
            "sellerMemberId": "32",
            "contractQuantity": 10.0,
            "contractRate": 50000.0,  # Severe out-of-bound discrepancy
            "contractAmount": 500000.0,
            "businessDate": "2026-10-07",
            "tradeTime": "2026-10-07T11:30:00",
        },
    ]

    pl.DataFrame(raw_ticks).write_parquet(raw_data_dir / "nepse_floorsheet_2026-10-07.parquet")

    # 3. Create mock anchor company CSV (socrateai-official format)
    anchor_nabil = [
        {
            "published_date": "2026-10-07",
            "open": 995.0,
            "high": 1010.0,
            "low": 990.0,
            "close": 1000.0,
            "per_change": 0.5,
            "traded_quantity": 50000.0,
            "traded_amount": 50000000.0,
            "status": 0,
        }
    ]
    pl.DataFrame(anchor_nabil).write_csv(raw_anchor_dir / "NABIL.csv")

    return tmp_path


def test_pipeline_execution_and_metrics(test_env):
    """Test full execution of Stages 1, 2, and 3 on the mock sandbox."""
    pipeline = LakehouseReconciliationPipeline(base_dir=test_env)
    metrics = pipeline.run()

    # 7 total input rows
    assert metrics["total_rows_processed"] == 7

    # 2 corrupt rows quarantined (negative price, zero volume)
    assert metrics["quarantined_rows"] == 2

    # 1 wash trade flagged
    assert metrics["wash_trades_flagged"] == 1

    # 2 synthetic broker IDs nullified (buyer on 1000050, seller on 1000051)
    assert metrics["synthetic_buyers_nullified"] == 1
    assert metrics["synthetic_sellers_nullified"] == 1
    assert metrics["total_synthetic_nullified"] == 2

    # 1 discrepancy patched from anchor (severe out-of-bound price 50000 -> 1000)
    assert metrics["patched_from_anchor"] == 1

    # 4 clean valid rows + 1 patched row = 5 verified rows
    assert metrics["verified_rows"] == 4


def test_quarantine_table_population(test_env):
    """Verify that quarantined rows are isolated with forensic reason in data_quarantine."""
    pipeline = LakehouseReconciliationPipeline(base_dir=test_env)
    pipeline.run()

    db_path = test_env / "02_processed_parquet" / "market_analytics.duckdb"
    mgr = get_connection_manager(str(db_path))
    with mgr.acquire() as con:
        quarantine_rows = con.execute("SELECT symbol, price, volume, reason FROM data_quarantine").fetchall()

    assert len(quarantine_rows) == 2
    reasons = {r[3] for r in quarantine_rows}
    assert "CORRUPTED_PRICE_NON_POSITIVE" in reasons
    assert "CORRUPTED_VOLUME_NON_POSITIVE" in reasons


def test_atomic_swap_and_pool_querying(test_env):
    """Verify that target lakehouse view reflects scrubbed data with proper column nullifications."""
    pipeline = LakehouseReconciliationPipeline(base_dir=test_env)
    pipeline.run()

    db_path = test_env / "02_processed_parquet" / "market_analytics.duckdb"
    mgr = get_connection_manager(str(db_path))

    with mgr.acquire() as con:
        # Check lakehouse_ticks view
        df = con.execute("SELECT * FROM lakehouse_ticks ORDER BY contract_id").pl()

    # Quarantined rows must NOT be in lakehouse_ticks
    assert len(df) == 5

    # Check wash trade row
    wash_row = df.filter(pl.col("contract_id") == 2026100700000002)
    assert wash_row["is_wash_trade"][0] is True

    # Check synthetic buyer nullification on contract 1000050
    synth_buyer_row = df.filter(pl.col("contract_id") == 1000050)
    assert synth_buyer_row["buyer_broker"][0] is None
    assert synth_buyer_row["seller_broker"][0] == "28"  # preserved

    # Check synthetic seller nullification on contract 1000051
    synth_seller_row = df.filter(pl.col("contract_id") == 1000051)
    assert synth_seller_row["seller_broker"][0] is None
    assert synth_seller_row["buyer_broker"][0] == "25"  # preserved

    # Check patched discrepancy row
    patched_row = df.filter(pl.col("contract_id") == 2026100700000007)
    assert patched_row["reconciliation_status"][0] == "PATCHED_FROM_ANCHOR"
    assert patched_row["ltp"][0] == 1000.0  # Patched to anchor close
    assert patched_row["turnover"][0] == 10000.0  # Patched turnover
