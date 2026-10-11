"""
Preservation Test 2.1: Storage & Concurrency Baseline

**Validates: Requirements 3.1.1, 3.1.2, 3.1.3**

This is a PRESERVATION baseline test that MUST PASS on UNFIXED code.
It captures the correct sequential / single-connection behaviour of DuckDB and
Parquet so that we can verify nothing regresses after the connection-pooling fix.

The observed baseline patterns come from:
  - scripts/pulse_chart_engine.py  (con = duckdb.connect(); … con.close())
  - scripts/01_build_master_union.py (con = duckdb.connect(database=":memory:"))

Properties under test:
  P-3.1.1  Sequential DuckDB queries (single connection, in-memory) execute
           successfully and return correct data.
  P-3.1.2  A DataFrame written to a Parquet file and read back is byte-for-byte
           identical to the original (no data corruption).
  P-3.1.3  A single sequential DuckDB query against the master parquet completes
           within 2 seconds (lightweight latency preserved).

Requirements: 3.1.1, 3.1.2, 3.1.3
"""

import os
import hashlib
import tempfile
import shutil
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
MASTER_PARQUET = BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df_hash(df: pd.DataFrame) -> str:
    """Stable SHA-256 fingerprint of a DataFrame (column-order-insensitive)."""
    df_sorted = df[sorted(df.columns)].sort_values(by=sorted(df.columns)).reset_index(drop=True)
    raw = df_sorted.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _make_ohlcv(rows: int, seed: int) -> pd.DataFrame:
    """Return a minimal OHLCV DataFrame for Parquet round-trip tests."""
    rng = np.random.default_rng(seed)
    tickers = ["NABIL", "EBL", "HBL", "SCB", "SBI"]
    closes = rng.uniform(100.0, 1_000.0, size=rows).round(2)
    spreads = rng.uniform(0.0, 20.0, size=rows).round(2)
    return pd.DataFrame(
        {
            "ticker": rng.choice(tickers, size=rows),
            "date": pd.date_range("2024-01-01", periods=rows, freq="D")
            .strftime("%Y-%m-%d")
            .tolist(),
            "open": (closes - spreads / 2).round(2),
            "high": (closes + spreads).round(2),
            "low": (closes - spreads).round(2),
            "close": closes,
            "volume": rng.integers(1_000, 100_000, size=rows),
        }
    )


# ---------------------------------------------------------------------------
# P-3.1.2  Parquet round-trip integrity (property-based)
# ---------------------------------------------------------------------------

@given(
    rows=st.integers(min_value=1, max_value=500),
    seed=st.integers(min_value=0, max_value=9_999),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_parquet_write_read_roundtrip_is_identical(rows, seed):
    """
    Property: For any OHLCV DataFrame, writing it to Parquet and reading it back
    yields an identical DataFrame.

    Validates: Requirement 3.1.2
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="preserve_storage_"))
    try:
        df_original = _make_ohlcv(rows, seed)
        parquet_path = tmp_dir / "test_data.parquet"

        # Sequential single write (baseline pattern)
        df_original.to_parquet(parquet_path, index=False, engine="pyarrow")

        # Read back
        df_read = pd.read_parquet(parquet_path)

        # Both hashes must match
        assert _df_hash(df_original) == _df_hash(df_read), (
            f"Parquet round-trip mismatch for {rows} rows (seed={seed}): "
            "written data != read data"
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# P-3.1.2  Parquet write produces a valid, readable file (deterministic)
# ---------------------------------------------------------------------------

def test_single_parquet_write_is_readable():
    """
    Deterministic: a small DataFrame written to a temp Parquet file can be read
    back without errors and the row count matches.

    Validates: Requirement 3.1.2
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="preserve_storage_det_"))
    try:
        df = _make_ohlcv(rows=100, seed=42)
        parquet_path = tmp_dir / "single_write.parquet"

        df.to_parquet(parquet_path, index=False, engine="pyarrow")

        assert parquet_path.exists(), "Parquet file was not created"
        assert parquet_path.stat().st_size > 0, "Parquet file is empty"

        df_back = pd.read_parquet(parquet_path)

        assert len(df_back) == len(df), (
            f"Row count mismatch: wrote {len(df)}, read {len(df_back)}"
        )
        assert list(df_back.columns) == list(df.columns), (
            f"Column mismatch: wrote {list(df.columns)}, read {list(df_back.columns)}"
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# P-3.1.1  Sequential DuckDB queries execute correctly (property-based)
# ---------------------------------------------------------------------------

@given(
    rows=st.integers(min_value=10, max_value=300),
    seed=st.integers(min_value=0, max_value=9_999),
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
def test_sequential_duckdb_queries_return_correct_data(rows, seed):
    """
    Property: For any in-memory DuckDB table, a sequence of independent queries
    (aggregate, filter, order) executes without error and returns logically
    consistent results.

    Mirrors the pattern in pulse_chart_engine.py:
        con = duckdb.connect()
        df = con.execute(query).df()
        con.close()

    Validates: Requirement 3.1.1
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="preserve_duck_"))
    try:
        df = _make_ohlcv(rows, seed)
        parquet_path = tmp_dir / "seq_test.parquet"
        df.to_parquet(parquet_path, index=False, engine="pyarrow")
        p_str = str(parquet_path).replace("\\", "/")

        con = duckdb.connect()
        try:
            # Query 1 – row count
            count_result = con.execute(
                f"SELECT COUNT(*) AS n FROM read_parquet('{p_str}')"
            ).fetchone()
            assert count_result[0] == rows, (
                f"Row count mismatch: expected {rows}, got {count_result[0]}"
            )

            # Query 2 – aggregation
            agg_result = con.execute(
                f"SELECT ticker, AVG(close) AS avg_close "
                f"FROM read_parquet('{p_str}') GROUP BY ticker"
            ).fetchdf()
            assert len(agg_result) > 0, "Aggregation query returned zero rows"
            assert (agg_result["avg_close"] > 0).all(), (
                "avg_close contains non-positive values"
            )

            # Query 3 – ordered selection
            ordered_result = con.execute(
                f"SELECT ticker, date, close "
                f"FROM read_parquet('{p_str}') "
                f"ORDER BY date ASC LIMIT {min(rows, 10)}"
            ).fetchdf()
            assert len(ordered_result) == min(rows, 10), (
                f"Ordered query returned {len(ordered_result)} rows, "
                f"expected {min(rows, 10)}"
            )
        finally:
            con.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# P-3.1.1  In-memory DuckDB matches baseline from 01_build_master_union.py
# ---------------------------------------------------------------------------

def test_in_memory_duckdb_connection_baseline():
    """
    Deterministic: replicates the exact connection pattern from
    01_build_master_union.py — con = duckdb.connect(database=":memory:") —
    and verifies it executes queries successfully.

    Validates: Requirement 3.1.1
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="preserve_inmem_"))
    try:
        df = _make_ohlcv(rows=200, seed=7)
        parquet_path = tmp_dir / "inmem_test.parquet"
        df.to_parquet(parquet_path, index=False, engine="pyarrow")
        p_str = str(parquet_path).replace("\\", "/")

        # Exact pattern from 01_build_master_union.py
        con = duckdb.connect(database=":memory:")
        con.execute(f"CREATE TABLE market_data AS SELECT * FROM read_parquet('{p_str}')")

        result = con.execute(
            "SELECT COUNT(DISTINCT ticker) AS n_tickers FROM market_data"
        ).fetchone()
        assert result[0] > 0, "Expected at least one distinct ticker in in-memory table"

        result2 = con.execute(
            "SELECT ticker, MAX(high) AS max_high FROM market_data GROUP BY ticker ORDER BY ticker"
        ).fetchdf()
        assert len(result2) > 0, "GROUP BY query returned no rows"
        assert (result2["max_high"] > 0).all(), "max_high contains non-positive values"

        con.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# P-3.1.1  Master parquet readable with single in-memory connection
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not MASTER_PARQUET.exists(),
    reason=f"Master parquet not found at {MASTER_PARQUET}"
)
def test_master_parquet_readable_via_duckdb():
    """
    Deterministic: verifies the production master parquet file can be queried
    through a single in-memory DuckDB connection (the pulse_chart_engine.py
    pattern) without error and returns a non-empty DataFrame.

    Validates: Requirement 3.1.1
    """
    p_str = str(MASTER_PARQUET).replace("\\", "/")
    con = duckdb.connect()
    try:
        df = con.execute(
            f"SELECT ticker, date, close, volume "
            f"FROM read_parquet('{p_str}') "
            f"WHERE date >= '2024-01-01' "
            f"LIMIT 100"
        ).df()
        assert len(df) > 0, (
            "Expected rows from master parquet query but got zero results"
        )
        assert "ticker" in df.columns, "Column 'ticker' missing from result"
        assert "close" in df.columns, "Column 'close' missing from result"
        assert (df["close"] > 0).all(), "close prices contain non-positive values"
    finally:
        con.close()


# ---------------------------------------------------------------------------
# P-3.1.3  Single sequential query latency is under 2 seconds
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not MASTER_PARQUET.exists(),
    reason=f"Master parquet not found at {MASTER_PARQUET}"
)
def test_sequential_query_latency_under_2s():
    """
    Deterministic: a single sequential DuckDB read_parquet query against the
    production master parquet completes in under 2 seconds.

    Validates: Requirement 3.1.3
    """
    p_str = str(MASTER_PARQUET).replace("\\", "/")
    con = duckdb.connect()
    try:
        start = time.time()
        result = con.execute(
            f"SELECT ticker, date, close, volume "
            f"FROM read_parquet('{p_str}') "
            f"ORDER BY date DESC "
            f"LIMIT 500"
        ).fetchdf()
        elapsed = time.time() - start
    finally:
        con.close()

    assert elapsed < 2.0, (
        f"Sequential query took {elapsed:.3f}s, expected < 2s "
        "(Requirement 3.1.3 violated: sub-2s latency for lightweight operations)"
    )
    assert len(result) > 0, "Query returned no rows"


# ---------------------------------------------------------------------------
# P-3.1.3  Small in-memory Parquet write latency (property-based)
# ---------------------------------------------------------------------------

@given(rows=st.integers(min_value=1, max_value=1_000))
@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
def test_parquet_write_latency_scales_reasonably(rows):
    """
    Property: writing a small-to-medium DataFrame to Parquet completes in
    under 2 seconds for up to 1 000 rows (lightweight synchronous workload).

    Validates: Requirement 3.1.3
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="preserve_latency_"))
    try:
        df = _make_ohlcv(rows, seed=rows)
        parquet_path = tmp_dir / "latency_test.parquet"

        start = time.time()
        df.to_parquet(parquet_path, index=False, engine="pyarrow")
        elapsed = time.time() - start

        assert elapsed < 2.0, (
            f"Parquet write of {rows} rows took {elapsed:.3f}s, expected < 2s"
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
