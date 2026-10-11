"""
Unit tests for NEPSE Broker Ecosystem SCD Type 2 Point-in-Time (PIT) table.
Ensures zero look-ahead bias, non-overlapping effective dates, and proper PIT name resolution.
"""

import pytest
import polars as pl
import importlib.util
from pathlib import Path

# Dynamic import for module with numeric directory prefix
_spec = importlib.util.spec_from_file_location(
    "build_broker_master_pit",
    Path(__file__).parent.parent / "scripts" / "01_etl_and_ingestion" / "build_broker_master_pit.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_broker_master_pit = _mod.build_broker_master_pit
get_broker_pit = _mod.get_broker_pit
STATIC_PARQUET = _mod.STATIC_PARQUET
OUT_PARQUET = _mod.OUT_PARQUET


def test_broker_master_parquet_exists():
    """Verify generated Parquet files exist and are non-empty."""
    assert OUT_PARQUET.exists(), f"Missing {OUT_PARQUET}"
    assert STATIC_PARQUET.exists(), f"Missing {STATIC_PARQUET}"
    
    df = pl.read_parquet(OUT_PARQUET)
    assert df.height > 90
    assert "broker_id" in df.columns
    assert "legal_name" in df.columns
    assert "effective_start_date" in df.columns
    assert "effective_end_date" in df.columns
    assert "is_current" in df.columns
    assert "version" in df.columns


def test_unique_primary_key_broker_version():
    """Ensure (broker_id, version) forms a strictly unique primary key."""
    df = pl.read_parquet(OUT_PARQUET)
    dups = df.group_by(["broker_id", "version"]).len().filter(pl.col("len") > 1)
    assert dups.height == 0, f"Found duplicate (broker_id, version): {dups}"


def test_no_overlapping_effective_intervals():
    """Ensure no date interval overlaps for the same broker_id."""
    df = pl.read_parquet(OUT_PARQUET)
    multi_version_brokers = (
        df.group_by("broker_id")
        .len()
        .filter(pl.col("len") > 1)["broker_id"]
        .to_list()
    )

    for b_id in multi_version_brokers:
        b_df = df.filter(pl.col("broker_id") == b_id).sort("effective_start_date")
        rows = b_df.to_dicts()
        for i in range(len(rows) - 1):
            assert rows[i]["effective_end_date"] < rows[i + 1]["effective_start_date"], (
                f"Overlap detected for broker {b_id}: "
                f"v{rows[i]['version']} end {rows[i]['effective_end_date']} vs "
                f"v{rows[i+1]['version']} start {rows[i+1]['effective_start_date']}"
            )


def test_broker_58_scd_type_2_evolution():
    """Verify Broker 58 (Naasa) transitions from Pvt. Ltd. to Co. Ltd. without lookahead bias."""
    # Historical 2018 Trade -> Version 1 (Pvt. Ltd.)
    b_2018 = get_broker_pit("58", "2018-05-10")
    assert b_2018 is not None
    assert b_2018["legal_name"] == "Naasa Securities Pvt. Ltd."
    assert b_2018["version"] == 1
    assert b_2018["is_current"] is False

    # Current 2026 Trade -> Version 2 (Co. Ltd.)
    b_2026 = get_broker_pit("58", "2026-10-07")
    assert b_2026 is not None
    assert b_2026["legal_name"] == "Naasa Securities Co. Ltd."
    assert b_2026["version"] == 2
    assert b_2026["is_current"] is True


def test_expansion_broker_lookahead_bias_rejection():
    """Verify post-2023 expansion brokers (e.g., #94 KBL) return None for trades before licensing."""
    # Historical 2018 Trade -> Must return None (didn't exist)
    b_2018 = get_broker_pit("94", "2018-05-10")
    assert b_2018 is None, "Lookahead bias violation: Expansion broker resolved in 2018!"

    # Modern 2026 Trade -> Resolves successfully
    b_2026 = get_broker_pit("94", "2026-10-07")
    assert b_2026 is not None
    assert "K.B.L. Securities Limited" in b_2026["legal_name"]
    assert b_2026["license_category"] == "EXPANSION_BROKER"
