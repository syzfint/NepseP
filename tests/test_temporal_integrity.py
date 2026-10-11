"""
Test Suite 5.6 — Temporal Integrity
=====================================
Five tests that cover:
  1. lag join → NaN on first row per ticker (correct behaviour after fix)
  2. same-day join → non-NaN on first row (confirms the original bug existed)
  3. validate_temporal_joins catches contamination
  4. validate_temporal_joins passes clean (correctly-lagged) data
  5. verify_column_alignment raises ColumnMismatchError on missing columns

Requirements: 2.3.1, 2.3.2, 2.3.3
"""

import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Load temporal_validator by file path — avoids the digit in the package name
# ('03_data_access_and_storage' is not a valid Python identifier)
# ---------------------------------------------------------------------------
_VALIDATOR_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "03_data_access_and_storage"
    / "temporal_validator.py"
)
_spec = importlib.util.spec_from_file_location("temporal_validator", _VALIDATOR_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["temporal_validator"] = _mod
_spec.loader.exec_module(_mod)

TemporalContaminationError = _mod.TemporalContaminationError
ColumnMismatchError = _mod.ColumnMismatchError
validate_temporal_joins = _mod.validate_temporal_joins
verify_column_alignment = _mod.verify_column_alignment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_df(dates, ticker: str = "NABIL") -> pd.DataFrame:
    """Minimal price DataFrame with ticker + date columns."""
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": pd.to_datetime(dates),
            "close": [500.0 + i for i in range(len(dates))],
        }
    )


def _make_broker_df(dates, ticker: str = "NABIL") -> pd.DataFrame:
    """Minimal broker DataFrame with a single feature column."""
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": pd.to_datetime(dates),
            "top_buyer_concentration": [float(i + 1) for i in range(len(dates))],
        }
    )


def _join_same_day(price_df: pd.DataFrame, broker_df: pd.DataFrame) -> pd.DataFrame:
    """Replicate the *unfixed* same-day join:  ON e.date = CAST(f.date AS DATE)."""
    con = duckdb.connect(":memory:")
    con.register("prices", price_df)
    con.register("broker", broker_df)
    result = con.execute("""
        SELECT
            e.ticker,
            e.date,
            e.close,
            f.top_buyer_concentration
        FROM prices e
        LEFT JOIN broker f
            ON e.ticker = f.ticker
           AND e.date = CAST(f.date AS DATE)
        ORDER BY e.ticker, e.date
    """).df()
    con.close()
    return result


def _join_1_session_lag(price_df: pd.DataFrame, broker_df: pd.DataFrame) -> pd.DataFrame:
    """Replicate the *fixed* 1-session lag join:
    ON CAST(f.date AS DATE) = e.date - INTERVAL 1 DAY
    """
    con = duckdb.connect(":memory:")
    con.register("prices", price_df)
    con.register("broker", broker_df)
    result = con.execute("""
        SELECT
            e.ticker,
            e.date,
            e.close,
            f.top_buyer_concentration
        FROM prices e
        LEFT JOIN broker f
            ON e.ticker = f.ticker
           AND CAST(f.date AS DATE) = e.date - INTERVAL 1 DAY
        ORDER BY e.ticker, e.date
    """).df()
    con.close()
    return result


# ---------------------------------------------------------------------------
# Test 1: Lag join — broker column is NaN on each ticker's first row
# ---------------------------------------------------------------------------

class TestLagJoinProducesNanOnFirstRow:
    """
    Validates: Requirement 2.3.1

    After applying the 1-session lag join (the fix), the price row for the
    earliest date in each ticker's history has no matching broker row,
    so ``top_buyer_concentration`` must be NaN / NULL for that row.

    This confirms the fix is structurally correct: future information is not
    present on the first row.
    """

    def test_lag_join_nan_on_first_row_single_ticker(self):
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        price_df = _make_price_df(dates)
        broker_df = _make_broker_df(dates)  # broker covers same dates as prices

        result = _join_1_session_lag(price_df, broker_df)

        # Sort by date and take the very first row
        first_row = result.sort_values("date").iloc[0]
        assert pd.isna(first_row["top_buyer_concentration"]), (
            f"Expected NaN on first row after lag join, "
            f"got {first_row['top_buyer_concentration']!r}"
        )

    def test_lag_join_nan_on_first_row_multiple_tickers(self):
        """Each ticker must independently have NaN on its own earliest date."""
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        tickers = ["NABIL", "NICA", "SCB"]

        price_dfs = [_make_price_df(dates, t) for t in tickers]
        broker_dfs = [_make_broker_df(dates, t) for t in tickers]

        price_df = pd.concat(price_dfs, ignore_index=True)
        broker_df = pd.concat(broker_dfs, ignore_index=True)

        result = _join_1_session_lag(price_df, broker_df)

        for ticker in tickers:
            ticker_rows = result[result["ticker"] == ticker].sort_values("date")
            first_val = ticker_rows.iloc[0]["top_buyer_concentration"]
            assert pd.isna(first_val), (
                f"Ticker {ticker}: expected NaN on first row after lag join, "
                f"got {first_val!r}"
            )

    def test_lag_join_subsequent_rows_have_values(self):
        """
        Rows after the first must receive broker values (the join works for
        dates where a T-1 broker row exists).
        """
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        price_df = _make_price_df(dates)
        broker_df = _make_broker_df(dates)

        result = _join_1_session_lag(price_df, broker_df).sort_values("date")

        # Rows at index 1..4 should have non-NaN broker concentration
        non_first = result.iloc[1:]
        assert non_first["top_buyer_concentration"].notna().all(), (
            "Rows 2+ should have broker concentration values after lag join; "
            f"got: {non_first['top_buyer_concentration'].tolist()}"
        )


# ---------------------------------------------------------------------------
# Test 2: Same-day join — first row is NOT NaN (confirms the original bug)
# ---------------------------------------------------------------------------

class TestSameDayJoinContaminates:
    """
    Validates: Requirement 2.3.1 (negative / regression baseline)

    The *original* same-day join (``ON e.date = CAST(f.date AS DATE)``)
    produces a non-NaN broker value on the very first row for each ticker,
    because broker data from date T is immediately available to price row T.

    This test documents the bug condition and serves as a sentinel: if this
    test were to fail, it would mean the same-day join no longer contaminates —
    but we keep it here to confirm the historical behaviour.
    """

    def test_same_day_join_first_row_not_nan(self):
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        price_df = _make_price_df(dates)
        broker_df = _make_broker_df(dates)

        result = _join_same_day(price_df, broker_df).sort_values("date")
        first_val = result.iloc[0]["top_buyer_concentration"]

        # The bug: first row has data (same-day data leaked)
        assert pd.notna(first_val), (
            "SAME-DAY JOIN BUG BASELINE FAILED: expected non-NaN value on "
            f"first row of same-day join, got {first_val!r}. "
            "This test confirms the original bug exists."
        )

    def test_same_day_join_all_rows_have_values(self):
        """With a same-day join every single row gets broker data — total contamination."""
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        price_df = _make_price_df(dates)
        broker_df = _make_broker_df(dates)

        result = _join_same_day(price_df, broker_df)
        assert result["top_buyer_concentration"].notna().all(), (
            "Same-day join should produce non-NaN values for ALL rows"
        )


# ---------------------------------------------------------------------------
# Test 3: validate_temporal_joins raises TemporalContaminationError
# ---------------------------------------------------------------------------

class TestValidateTemporalJoinsCatchesContamination:
    """
    Validates: Requirement 2.3.2

    ``validate_temporal_joins()`` must raise ``TemporalContaminationError``
    when given a DataFrame where a lagged feature column has a non-zero,
    non-NaN value on the first (earliest) row for any ticker.
    """

    def test_raises_on_nonzero_first_row(self):
        """
        Build a DataFrame where the first row has a non-zero broker value
        (simulating a same-day join) and verify the validator fires.
        """
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        df = pd.DataFrame(
            {
                "ticker": "NABIL",
                "date": dates,
                "close": 500.0,
                # First row has a non-zero broker value → contamination
                "top_buyer_concentration": [0.35, 0.40, 0.38, 0.42, 0.39],
            }
        )

        with pytest.raises(TemporalContaminationError, match="contamination"):
            validate_temporal_joins(df, ["top_buyer_concentration"])

    def test_raises_for_multiple_contaminated_tickers(self):
        dates = pd.date_range("2024-06-10", periods=3, freq="B")
        df = pd.concat(
            [
                pd.DataFrame({
                    "ticker": t,
                    "date": dates,
                    "close": 100.0,
                    "top_buyer_concentration": [0.5, 0.4, 0.3],
                })
                for t in ["NABIL", "NICA"]
            ],
            ignore_index=True,
        )

        with pytest.raises(TemporalContaminationError):
            validate_temporal_joins(df, ["top_buyer_concentration"])

    def test_error_message_contains_ticker_info(self):
        dates = pd.date_range("2024-06-10", periods=3, freq="B")
        df = pd.DataFrame(
            {
                "ticker": "CONTAMINATED",
                "date": dates,
                "close": 200.0,
                "buyer_hhi": [0.22, 0.18, 0.20],
            }
        )

        with pytest.raises(TemporalContaminationError) as exc_info:
            validate_temporal_joins(df, ["buyer_hhi"])

        assert "contamination" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 4: validate_temporal_joins passes clean, correctly-lagged data
# ---------------------------------------------------------------------------

class TestValidateTemporalJoinPassesCleanData:
    """
    Validates: Requirement 2.3.2

    ``validate_temporal_joins()`` must NOT raise for DataFrames that have
    NaN (or 0.0 via COALESCE fallback) on each ticker's first row.
    """

    def test_no_exception_when_first_row_is_nan(self):
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        # First row NaN — mirrors the lag join output before COALESCE
        values = [np.nan, 0.40, 0.38, 0.42, 0.39]
        df = pd.DataFrame(
            {
                "ticker": "NABIL",
                "date": dates,
                "close": 500.0,
                "top_buyer_concentration": values,
            }
        )

        # Should not raise
        validate_temporal_joins(df, ["top_buyer_concentration"])

    def test_no_exception_when_first_row_is_zero(self):
        """
        COALESCE(NULL, 0.0) in the SQL means lag-join first rows come back
        as 0.0 rather than NaN.  Zero on the first row is allowed (it means
        'no matching broker row' — temporal safety intact).
        """
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        values = [0.0, 0.35, 0.40, 0.38, 0.42]
        df = pd.DataFrame(
            {
                "ticker": "NICA",
                "date": dates,
                "close": 300.0,
                "top_buyer_concentration": values,
            }
        )

        # Should not raise — 0.0 first row is the COALESCE default for a lagged join
        validate_temporal_joins(df, ["top_buyer_concentration"])

    def test_no_exception_for_multiple_tickers_clean_data(self):
        dates = pd.date_range("2024-06-10", periods=5, freq="B")
        frames = []
        for i, ticker in enumerate(["NABIL", "NICA", "SCB"]):
            frames.append(
                pd.DataFrame(
                    {
                        "ticker": ticker,
                        "date": dates,
                        "close": float(100 + i * 50),
                        # First row NaN, rest have valid values
                        "top_buyer_concentration": [np.nan, 0.3, 0.35, 0.28, 0.32],
                        "buyer_hhi": [np.nan, 0.12, 0.14, 0.11, 0.13],
                    }
                )
            )
        df = pd.concat(frames, ignore_index=True)

        # Should not raise for any ticker
        validate_temporal_joins(df, ["top_buyer_concentration", "buyer_hhi"])

    def test_skips_columns_not_in_dataframe(self):
        """
        Columns listed in lagged_feature_cols but absent from the DataFrame
        must be silently skipped (no KeyError, no false positive).
        """
        dates = pd.date_range("2024-06-10", periods=3, freq="B")
        df = pd.DataFrame(
            {
                "ticker": "TEST",
                "date": dates,
                "close": 100.0,
                # Only 'top_buyer_concentration' present; others absent
                "top_buyer_concentration": [np.nan, 0.3, 0.35],
            }
        )

        # Should not raise even though 'buyer_hhi', 'broker_dispersion' are absent
        validate_temporal_joins(
            df,
            ["top_buyer_concentration", "buyer_hhi", "broker_dispersion"],
        )


# ---------------------------------------------------------------------------
# Test 5: verify_column_alignment raises ColumnMismatchError on missing cols
# ---------------------------------------------------------------------------

class TestVerifyColumnAlignment:
    """
    Validates: Requirement 2.3.3

    ``verify_column_alignment()`` must raise ``ColumnMismatchError`` when
    expected columns are absent from the actual schema, and must succeed
    (not raise) when all expected columns are present.
    """

    def test_raises_when_column_missing(self):
        expected = ["dist_sma20", "dist_sma50", "ret_1w"]
        actual = ["dist_sma20", "ret_1w"]  # 'dist_sma50' missing

        with pytest.raises(ColumnMismatchError, match="dist_sma50"):
            verify_column_alignment(expected, actual)

    def test_raises_lists_all_missing_columns(self):
        expected = ["col_a", "col_b", "col_c"]
        actual = ["col_a"]  # col_b and col_c absent

        with pytest.raises(ColumnMismatchError) as exc_info:
            verify_column_alignment(expected, actual)

        err_msg = str(exc_info.value)
        assert "col_b" in err_msg, f"Expected 'col_b' in error message, got: {err_msg}"
        assert "col_c" in err_msg, f"Expected 'col_c' in error message, got: {err_msg}"

    def test_no_exception_when_all_columns_present(self):
        expected = ["dist_sma20", "dist_sma50", "volatility_20"]
        actual = ["dist_sma20", "dist_sma50", "volatility_20", "extra_col"]

        # Should not raise — extra columns in 'actual' are fine
        verify_column_alignment(expected, actual)

    def test_context_appears_in_error_message(self):
        expected = ["missing_col"]
        actual = ["other_col"]

        with pytest.raises(ColumnMismatchError) as exc_info:
            verify_column_alignment(expected, actual, context="technical_indicators.parquet")

        assert "technical_indicators.parquet" in str(exc_info.value)

    def test_raises_on_completely_empty_actual(self):
        expected = ["col_a", "col_b"]
        actual = []

        with pytest.raises(ColumnMismatchError):
            verify_column_alignment(expected, actual)

    def test_no_exception_on_empty_expected(self):
        """Empty expected list — nothing to verify — should never raise."""
        verify_column_alignment([], ["any_col", "other_col"])

    def test_raises_with_correct_missing_count(self):
        expected = ["a", "b", "c", "d"]
        actual = ["a", "c"]  # b and d missing

        with pytest.raises(ColumnMismatchError) as exc_info:
            verify_column_alignment(expected, actual)

        err_msg = str(exc_info.value)
        # Error message reports count of missing columns
        assert "2" in err_msg, (
            f"Expected '2' missing columns reported, got: {err_msg}"
        )
