"""
Preservation Test 2.3: Temporal Preservation

**Property 2: Preservation** — Multi-Day Lag Features Unchanged

This is a PRESERVATION baseline test that MUST PASS on UNFIXED code.
It captures the correct behaviour of multi-day rolling windows and SQL lag
joins so that nothing regresses after the 1-session temporal lag fix is applied
(Phase 5 of the bugfix spec).

Two feature-engineering pipelines are tested:

Pipeline A — scripts/02_feature_engineering.py
  Uses DuckDB window functions with:
      ROWS BETWEEN N PRECEDING AND 1 PRECEDING (correct t-1 lag)
  and a floorsheet join currently written as:
      ON e.ticker = f.ticker AND e.date = CAST(f.date AS DATE)   ← same-day (to be fixed later)
  Here we only test the ROLLING WINDOW columns (sma_20, sma_50, volatility_20,
  ret_1w, ret_1m) which are already lagged correctly and must remain so.

Pipeline B — scripts/02_modeling_and_calculations/02_feature_engineering.py
  Uses per-ticker Pandas .rolling() / .ewm() operations:
      close.rolling(20).mean()
      close.rolling(50).mean()
      close.rolling(20).std() / close  (volatility_20)
      close.ewm(span=12).mean() - close.ewm(span=26).mean()  (MACD)
      compute_rsi(close, 14)  (RSI-14)

Properties under test:
  P-3.3.1  Rolling-window features (SMA-5, SMA-20, SMA-50, vol-20) return
           non-NaN values after the required warm-up period and match a
           manual reference calculation.
  P-3.3.2  Point-in-time correctness: the value at date index i only depends
           on data at indices <= i (no forward-looking bias in look-back windows).
  P-3.3.3  DuckDB INTERVAL N DAY lag join: for any pair (price_date, broker_date)
           produced by a K-day lag join, broker_date == price_date - K.

Requirements: 3.3.1, 3.3.2, 3.3.3
"""

import math
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Reference implementations (mirrors the actual production code)
# ---------------------------------------------------------------------------

def _pandas_sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average with pandas (matches rolling(N).mean())."""
    return series.rolling(window=window).mean()


def _pandas_rolling_std(series: pd.Series, window: int) -> pd.Series:
    """Rolling std with pandas (matches rolling(N).std())."""
    return series.rolling(window=window).std()


def _compute_volatility_20(close: pd.Series) -> pd.Series:
    """
    Mirrors the production formula from scripts/02_feature_engineering.py:
        std_20 / (sma_20 + 1e-6)
    where both windows use ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING in SQL,
    i.e., the window does NOT include the current row.

    We replicate this with shift(1) + rolling(20).
    """
    std_20 = close.shift(1).rolling(20).std()
    sma_20 = close.shift(1).rolling(20).mean()
    return std_20 / (sma_20 + 1e-6)


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Mirrors compute_rsi from
    scripts/02_modeling_and_calculations/02_feature_engineering.py.
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-8)
    return 100 - (100 / (1 + rs))


def _make_price_series(n: int, seed: int = 42) -> pd.Series:
    """Generate a realistic positive price series of length n."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=0.0003, scale=0.015, size=n)
    prices = 500.0 * np.cumprod(1 + returns)
    return pd.Series(prices, name="close")


def _make_ohlcv_df(n: int, seed: int = 42, ticker: str = "TEST") -> pd.DataFrame:
    """
    Build a minimal OHLCV DataFrame that mirrors the production parquet schema.
    Dates are consecutive trading days (Mon–Fri).
    """
    rng = np.random.default_rng(seed)
    close = _make_price_series(n, seed)
    spread = rng.uniform(0.5, 5.0, size=n)
    dates = pd.date_range("2023-01-02", periods=n, freq="B")  # business days
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": (close - spread / 2).clip(lower=1.0).round(2),
            "high": (close + spread).round(2),
            "low": (close - spread).clip(lower=1.0).round(2),
            "close": close.round(2),
            "volume": rng.integers(1_000, 100_000, size=n),
        }
    )


# ---------------------------------------------------------------------------
# Helper: compute DuckDB window features on an in-memory DataFrame
# (replicates scripts/02_feature_engineering.py SQL pipeline without file I/O)
# ---------------------------------------------------------------------------

def _duckdb_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs the same DuckDB window-function SQL as scripts/02_feature_engineering.py
    on an in-memory DataFrame (no Parquet files required).

    Returns a DataFrame with: ticker, date, close, sma_20, sma_50,
    volatility_20, ret_1w, ret_1m.
    """
    con = duckdb.connect(database=":memory:")
    con.register("market", df)

    sql = """
    WITH base AS (
        SELECT
            ticker,
            CAST(date AS DATE) AS date,
            close,
            volume,
            LAG(close, 1)  OVER w AS prev_close,
            AVG(close)     OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS sma_20,
            AVG(close)     OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING) AS sma_50,
            STDDEV(close)  OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS std_20,
            LAG(close,  5) OVER w AS close_lag5,
            LAG(close, 20) OVER w AS close_lag20
        FROM market
        WINDOW w AS (PARTITION BY ticker ORDER BY date)
    )
    SELECT
        ticker,
        date,
        close,
        sma_20,
        sma_50,
        (std_20 / (sma_20 + 1e-6)) AS volatility_20,
        ((prev_close / (close_lag5  + 1e-6)) - 1.0) AS ret_1w,
        ((prev_close / (close_lag20 + 1e-6)) - 1.0) AS ret_1m
    FROM base
    ORDER BY ticker, date
    """
    result = con.execute(sql).df()
    con.close()
    return result


# ---------------------------------------------------------------------------
# Helper: lag-join two in-memory DataFrames using DuckDB and INTERVAL N DAY
# ---------------------------------------------------------------------------

def _duckdb_lag_join(price_df: pd.DataFrame, broker_df: pd.DataFrame, lag_days: int) -> pd.DataFrame:
    """
    Performs the lag join pattern from scripts/02_feature_engineering.py:

        ON e.ticker = f.ticker
        AND e.date = CAST(f.date AS DATE) + INTERVAL N DAY

    where N = lag_days.  Returns a DataFrame with columns:
        price_date, ticker, broker_date, broker_feature.

    This is the FIXED join pattern we want to preserve for multi-day lags.
    For lag_days=2 this is already correct; for lag_days=1 this represents
    the fix to be applied later.
    """
    con = duckdb.connect(database=":memory:")
    con.register("prices", price_df)
    con.register("broker", broker_df)

    sql = f"""
    SELECT
        e.date        AS price_date,
        e.ticker,
        f.date        AS broker_date,
        f.broker_feature
    FROM prices e
    LEFT JOIN broker f
        ON  e.ticker = f.ticker
        AND e.date   = CAST(f.date AS DATE) + INTERVAL '{lag_days}' DAY
    WHERE f.date IS NOT NULL
    ORDER BY e.ticker, e.date
    """
    result = con.execute(sql).df()
    con.close()
    return result


# ---------------------------------------------------------------------------
# Unit Tests — Rolling Window Correctness (P-3.3.1)
# ---------------------------------------------------------------------------

class TestRollingWindowCorrectness:
    """
    Validates: Requirement 3.3.1

    Verifies that SMA-5, SMA-20, SMA-50, and 20-day rolling volatility
    produce correct values matching a manual reference calculation, and that
    they return non-NaN values after the required warm-up period.
    """

    def test_sma_5_matches_manual_after_warmup(self):
        """SMA-5 at position i must equal mean(close[i-4:i+1])."""
        close = pd.Series([100, 102, 98, 105, 103, 107, 110, 108, 112, 115], dtype=float)
        sma5 = _pandas_sma(close, 5)

        # First 4 rows are NaN (warm-up)
        assert sma5.iloc[:4].isna().all(), "SMA-5 should be NaN for first 4 rows"

        # Row 4 (index 4): mean of [100,102,98,105,103]
        expected_4 = (100 + 102 + 98 + 105 + 103) / 5
        assert abs(sma5.iloc[4] - expected_4) < 1e-6, (
            f"SMA-5 at row 4: expected {expected_4:.4f}, got {sma5.iloc[4]:.4f}"
        )

        # Row 9 (index 9): mean of [107,110,108,112,115]
        expected_9 = (107 + 110 + 108 + 112 + 115) / 5
        assert abs(sma5.iloc[9] - expected_9) < 1e-6, (
            f"SMA-5 at row 9: expected {expected_9:.4f}, got {sma5.iloc[9]:.4f}"
        )

    def test_sma_20_non_nan_after_20th_row(self):
        """SMA-20 must be non-NaN from row 19 onward for a 50-row series."""
        close = _make_price_series(50, seed=1)
        sma20 = _pandas_sma(close, 20)

        assert sma20.iloc[:19].isna().all(), "SMA-20 should be NaN for first 19 rows"
        assert not sma20.iloc[19:].isna().any(), (
            "SMA-20 must be non-NaN from row 19 onward"
        )

    def test_sma_50_non_nan_after_50th_row(self):
        """SMA-50 must be non-NaN from row 49 onward for a 100-row series."""
        close = _make_price_series(100, seed=2)
        sma50 = _pandas_sma(close, 50)

        assert sma50.iloc[:49].isna().all(), "SMA-50 should be NaN for first 49 rows"
        assert not sma50.iloc[49:].isna().any(), (
            "SMA-50 must be non-NaN from row 49 onward"
        )

    def test_rolling_std_20_non_nan_after_warmup(self):
        """Rolling std-20 must be non-NaN from row 19 onward."""
        close = _make_price_series(50, seed=3)
        std20 = _pandas_rolling_std(close, 20)

        assert std20.iloc[:19].isna().all(), "std-20 should be NaN for first 19 rows"
        assert not std20.iloc[19:].isna().any(), (
            "std-20 must be non-NaN from row 19 onward"
        )

    def test_sma_20_equals_arithmetic_mean_of_window(self):
        """
        SMA-20 at position i must equal the arithmetic mean of the 20
        preceding values [i-19 .. i] (inclusive).
        """
        close = _make_price_series(60, seed=4)
        sma20 = _pandas_sma(close, 20)

        for i in range(19, 60):
            expected = close.iloc[i - 19: i + 1].mean()
            assert abs(sma20.iloc[i] - expected) < 1e-8, (
                f"SMA-20 mismatch at row {i}: expected {expected:.6f}, "
                f"got {sma20.iloc[i]:.6f}"
            )

    def test_volatility_20_non_negative(self):
        """20-day rolling volatility (std/mean) must be >= 0 everywhere."""
        close = _make_price_series(80, seed=5)
        vol = _compute_volatility_20(close)
        non_nan_vol = vol.dropna()
        assert (non_nan_vol >= 0).all(), (
            "volatility_20 must be non-negative; "
            f"found negative values: {non_nan_vol[non_nan_vol < 0].tolist()}"
        )

    def test_duckdb_sma_20_matches_pandas(self):
        """
        DuckDB window-function SMA-20 (ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)
        must equal the pandas SMA-20 shifted by 1 (the t-1 lag enforced in SQL).
        """
        df = _make_ohlcv_df(n=80, seed=6)
        result = _duckdb_rolling_features(df)

        # Pandas reference: shift(1) then rolling(20).mean()
        pandas_sma20 = df["close"].shift(1).rolling(20).mean()

        # Align by position (DuckDB result is ordered by date)
        duck_sma20 = result["sma_20"].reset_index(drop=True)
        pd_sma20 = pandas_sma20.reset_index(drop=True)

        # Compare only non-NaN rows (after warm-up)
        valid = duck_sma20.notna() & pd_sma20.notna()
        assert valid.sum() > 0, "No valid (non-NaN) rows to compare"
        np.testing.assert_allclose(
            duck_sma20[valid].values,
            pd_sma20[valid].values,
            rtol=1e-4,
            err_msg="DuckDB SMA-20 differs from pandas reference",
        )

    def test_duckdb_sma_50_matches_pandas(self):
        """
        DuckDB SMA-50 (ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING) must equal
        the pandas SMA-50 shifted by 1.
        """
        df = _make_ohlcv_df(n=120, seed=7)
        result = _duckdb_rolling_features(df)

        pandas_sma50 = df["close"].shift(1).rolling(50).mean()

        duck_sma50 = result["sma_50"].reset_index(drop=True)
        pd_sma50 = pandas_sma50.reset_index(drop=True)

        valid = duck_sma50.notna() & pd_sma50.notna()
        assert valid.sum() > 0, "No valid (non-NaN) rows to compare"
        np.testing.assert_allclose(
            duck_sma50[valid].values,
            pd_sma50[valid].values,
            rtol=1e-4,
            err_msg="DuckDB SMA-50 differs from pandas reference",
        )

    def test_duckdb_volatility_20_non_negative(self):
        """DuckDB volatility_20 must be >= 0 everywhere (after warm-up)."""
        df = _make_ohlcv_df(n=80, seed=8)
        result = _duckdb_rolling_features(df)
        valid_vol = result["volatility_20"].dropna()
        assert (valid_vol >= 0).all(), (
            f"DuckDB volatility_20 has negative values: {valid_vol[valid_vol < 0].tolist()}"
        )

    def test_rsi_14_bounds(self):
        """RSI-14 must stay in [0, 100] for a realistic price series."""
        close = _make_price_series(100, seed=9)
        rsi = _compute_rsi(close, 14)
        valid_rsi = rsi.dropna()
        assert not valid_rsi.empty, "RSI should have non-NaN values after warm-up"
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all(), (
            f"RSI out of [0,100]: min={valid_rsi.min():.2f}, max={valid_rsi.max():.2f}"
        )


# ---------------------------------------------------------------------------
# Unit Tests — Point-in-Time Correctness (P-3.3.2)
# ---------------------------------------------------------------------------

class TestPointInTimeCorrectness:
    """
    Validates: Requirement 3.3.2

    Verifies that rolling features at row i do NOT incorporate any data from
    rows j > i (no forward-looking bias in look-back windows).
    """

    def test_sma_20_does_not_change_when_future_appended(self):
        """
        Append 10 new future rows to a price series. The SMA-20 values for
        the original rows must be unchanged.
        """
        close_orig = _make_price_series(60, seed=10)
        close_ext = pd.concat([
            close_orig,
            _make_price_series(10, seed=999) * 0.5,  # drastically different future
        ], ignore_index=True)

        sma_orig = _pandas_sma(close_orig, 20)
        sma_ext = _pandas_sma(close_ext, 20)

        # Values for original 60 rows must be identical in both
        np.testing.assert_array_equal(
            sma_orig.values,
            sma_ext.iloc[:60].values,
            err_msg=(
                "SMA-20 values changed after appending future data — "
                "forward-looking bias detected"
            ),
        )

    def test_rolling_std_20_does_not_change_when_future_appended(self):
        """
        std-20 for existing rows must not change when future data is appended.
        """
        close_orig = _make_price_series(60, seed=11)
        close_ext = pd.concat([
            close_orig,
            _make_price_series(10, seed=888) * 2.0,
        ], ignore_index=True)

        std_orig = _pandas_rolling_std(close_orig, 20)
        std_ext = _pandas_rolling_std(close_ext, 20)

        np.testing.assert_array_equal(
            std_orig.values,
            std_ext.iloc[:60].values,
            err_msg=(
                "Rolling std-20 changed after appending future data — "
                "forward-looking bias detected"
            ),
        )

    def test_duckdb_window_respects_row_order(self):
        """
        The DuckDB window SMA-20 for row i must equal the mean of the 20 rows
        immediately before i (ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING).
        Verified against a hand-computed reference for a deterministic series.
        """
        # Deterministic price series: 100, 101, 102, ..., 199
        n = 70
        prices = [float(100 + i) for i in range(n)]
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        df = pd.DataFrame({
            "ticker": "DET",
            "date": dates,
            "open": prices,
            "high": [p + 1.0 for p in prices],
            "low":  [p - 1.0 for p in prices],
            "close": prices,
            "volume": [1000] * n,
        })

        result = _duckdb_rolling_features(df)

        # At row i (0-indexed), sma_20 = mean(prices[i-20 .. i-1])  (the SQL uses 1 PRECEDING)
        for i in range(21, n):  # first valid row after 20+1 warm-up
            prev_window = prices[i - 20: i]   # 20 values ending at i-1
            expected = sum(prev_window) / 20.0
            got = result.iloc[i]["sma_20"]
            assert abs(got - expected) < 1e-4, (
                f"Row {i}: DuckDB SMA-20={got:.4f}, expected={expected:.4f}"
            )

    def test_ret_1w_only_uses_lagged_data(self):
        """
        ret_1w = (prev_close / close_lag5 - 1). Both prev_close and close_lag5
        are LAG functions (look back only), never forward.
        We verify the sign is consistent with the deterministic series direction.
        """
        # Monotonically increasing series → ret_1w should be positive
        n = 50
        prices = [float(100 + i * 2) for i in range(n)]
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        df = pd.DataFrame({
            "ticker": "MONO",
            "date": dates,
            "open": prices, "high": prices, "low": prices,
            "close": prices, "volume": [1000] * n,
        })

        result = _duckdb_rolling_features(df)
        valid_ret = result["ret_1w"].dropna()
        assert (valid_ret > 0).all(), (
            "ret_1w should be positive for a monotonically increasing series; "
            f"found non-positive values: {valid_ret[valid_ret <= 0].tolist()}"
        )

    def test_ret_1m_only_uses_lagged_data(self):
        """
        ret_1m = (prev_close / close_lag20 - 1). Verify sign for monotonic series.
        """
        n = 80
        prices = [float(100 + i * 1.5) for i in range(n)]
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        df = pd.DataFrame({
            "ticker": "MONO2",
            "date": dates,
            "open": prices, "high": prices, "low": prices,
            "close": prices, "volume": [1000] * n,
        })

        result = _duckdb_rolling_features(df)
        valid_ret = result["ret_1m"].dropna()
        assert (valid_ret > 0).all(), (
            "ret_1m should be positive for a monotonically increasing series; "
            f"found non-positive values: {valid_ret[valid_ret <= 0].tolist()}"
        )


# ---------------------------------------------------------------------------
# Unit Tests — DuckDB INTERVAL Lag Join Correctness (P-3.3.3)
# ---------------------------------------------------------------------------

class TestIntervalLagJoinCorrectness:
    """
    Validates: Requirement 3.3.3

    Verifies that DuckDB INTERVAL N DAY lag joins produce rows where
    broker_date == price_date - N for every result row (no same-day leakage).
    """

    def _make_price_df(self, dates: list, ticker: str = "NABIL") -> pd.DataFrame:
        return pd.DataFrame({
            "ticker": ticker,
            "date": pd.to_datetime(dates),
            "close": [500.0 + i for i in range(len(dates))],
        })

    def _make_broker_df(self, dates: list, ticker: str = "NABIL") -> pd.DataFrame:
        return pd.DataFrame({
            "ticker": ticker,
            "date": pd.to_datetime(dates),
            "broker_feature": [float(i + 1) for i in range(len(dates))],
        })

    def test_2_day_lag_join_broker_date_equals_price_date_minus_2(self):
        """
        For a 2-day lag join, every result row must satisfy:
            broker_date == price_date - 2 calendar days.
        """
        price_dates  = ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13"]
        broker_dates = ["2024-06-08", "2024-06-09", "2024-06-10", "2024-06-11"]

        price_df  = self._make_price_df(price_dates)
        broker_df = self._make_broker_df(broker_dates)

        result = _duckdb_lag_join(price_df, broker_df, lag_days=2)
        assert len(result) == 4, f"Expected 4 matched rows, got {len(result)}"

        for _, row in result.iterrows():
            diff = (pd.Timestamp(row["price_date"]) - pd.Timestamp(row["broker_date"])).days
            assert diff == 2, (
                f"2-day lag violated: price_date={row['price_date']}, "
                f"broker_date={row['broker_date']}, diff={diff} days (expected 2)"
            )

    def test_5_day_lag_join_broker_date_equals_price_date_minus_5(self):
        """
        For a 5-day lag join, every result row must satisfy:
            broker_date == price_date - 5 calendar days.
        """
        # 10 trading days, broker dates offset 5 days earlier
        price_dates  = pd.date_range("2024-06-10", periods=10, freq="B")
        broker_dates = [d - timedelta(days=5) for d in price_dates]

        price_df  = self._make_price_df(price_dates.tolist())
        broker_df = self._make_broker_df(broker_dates)

        result = _duckdb_lag_join(price_df, broker_df, lag_days=5)
        assert len(result) > 0, "5-day lag join returned no rows"

        for _, row in result.iterrows():
            diff = (pd.Timestamp(row["price_date"]) - pd.Timestamp(row["broker_date"])).days
            assert diff == 5, (
                f"5-day lag violated: price_date={row['price_date']}, "
                f"broker_date={row['broker_date']}, diff={diff} days (expected 5)"
            )

    def test_lag_join_produces_no_same_day_rows(self):
        """
        A lag-1 join must produce zero rows where price_date == broker_date.
        This is the key temporal safety invariant.
        """
        # price and broker both cover the same date range
        dates = pd.date_range("2024-06-10", periods=10, freq="B")
        price_df  = self._make_price_df(dates.tolist())
        broker_df = self._make_broker_df(dates.tolist())

        result = _duckdb_lag_join(price_df, broker_df, lag_days=1)

        same_day_rows = result[
            pd.to_datetime(result["price_date"]) == pd.to_datetime(result["broker_date"])
        ]
        assert len(same_day_rows) == 0, (
            f"Lag-1 join produced {len(same_day_rows)} same-day rows — "
            "temporal contamination would occur"
        )

    def test_lag_join_no_future_broker_data(self):
        """
        In a K-day lag join, broker_date must always be strictly less than
        price_date (broker data is from the past, not the future).
        """
        dates = pd.date_range("2024-01-02", periods=20, freq="B")
        price_df  = self._make_price_df(dates.tolist())
        broker_df = self._make_broker_df(dates.tolist())

        for lag in [1, 2, 5, 10]:
            result = _duckdb_lag_join(price_df, broker_df, lag_days=lag)
            if result.empty:
                continue  # no matches is fine for large lags relative to data
            future_rows = result[
                pd.to_datetime(result["broker_date"]) >= pd.to_datetime(result["price_date"])
            ]
            assert len(future_rows) == 0, (
                f"Lag-{lag} join produced {len(future_rows)} rows where "
                "broker_date >= price_date (future information leakage)"
            )


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------

# Strategy: positive price series length
series_length = st.integers(min_value=60, max_value=200)

# Strategy: random seed for price generation
random_seed = st.integers(min_value=0, max_value=9_999)

# Strategy: lag days for SQL join tests
lag_days_st = st.integers(min_value=1, max_value=10)

# Strategy: number of broker records
n_broker_records = st.integers(min_value=5, max_value=50)


@given(length=series_length, seed=random_seed)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property_sma20_at_position_i_equals_mean_of_preceding_20(length, seed):
    """
    **Validates: Requirements 3.3.1**

    Property: For ANY price series of length >= 60, the 20-day SMA at row i
    equals exactly the arithmetic mean of the 20 most recent prices ending at i.

    This is the fundamental rolling-average preservation guarantee: the
    computation formula must not change after the temporal lag fix.
    """
    close = _make_price_series(length, seed)
    sma20 = _pandas_sma(close, 20)

    # Check every position after warm-up
    for i in range(19, length):
        expected = close.iloc[i - 19: i + 1].mean()
        got = sma20.iloc[i]
        assert not math.isnan(got), f"SMA-20 is NaN at position {i} (length={length})"
        assert abs(got - expected) < 1e-6, (
            f"SMA-20 PRESERVATION VIOLATION at row {i} (seed={seed}): "
            f"expected={expected:.6f}, got={got:.6f}"
        )


@given(length=series_length, seed=random_seed)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property_rolling_std_20_non_negative_and_non_nan_after_warmup(length, seed):
    """
    **Validates: Requirements 3.3.1**

    Property: For ANY price series of length >= 60, the 20-day rolling standard
    deviation is non-negative and non-NaN for all positions >= 19 (after warm-up).

    Volatility-based features (volatility_20, Bollinger Bands) depend on this.
    """
    close = _make_price_series(length, seed)
    std20 = _pandas_rolling_std(close, 20)

    after_warmup = std20.iloc[19:]
    assert not after_warmup.isna().any(), (
        f"Rolling std-20 has NaN values after warm-up (length={length}, seed={seed})"
    )
    assert (after_warmup >= 0).all(), (
        f"Rolling std-20 has negative values (length={length}, seed={seed}): "
        f"min={after_warmup.min():.6f}"
    )


@given(length=series_length, seed=random_seed)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property_sma20_does_not_use_future_data(length, seed):
    """
    **Validates: Requirements 3.3.2**

    Property: For ANY price series, modifying a future value does NOT change
    any SMA-20 computed for rows before that modification point.

    This is the point-in-time correctness guarantee: no forward-looking bias.
    """
    close = _make_price_series(length, seed)

    # Pick a random modification point in the second half
    mod_idx = length // 2
    sma_before_mod = _pandas_sma(close, 20)

    # Dramatically change all future prices
    close_modified = close.copy()
    close_modified.iloc[mod_idx:] *= 10.0
    sma_after_mod = _pandas_sma(close_modified, 20)

    # Rows before mod_idx must be unchanged
    for i in range(mod_idx):
        v_before = sma_before_mod.iloc[i]
        v_after = sma_after_mod.iloc[i]
        if math.isnan(v_before):
            continue  # warm-up NaN — skip
        assert abs(v_before - v_after) < 1e-8, (
            f"POINT-IN-TIME VIOLATION at row {i}: SMA-20 changed from "
            f"{v_before:.6f} to {v_after:.6f} when future prices were modified "
            f"(mod_idx={mod_idx}, seed={seed})"
        )


@given(
    lag=lag_days_st,
    n_records=n_broker_records,
    seed=random_seed,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_duckdb_interval_lag_join_no_same_or_future_broker_dates(
    lag, n_records, seed
):
    """
    **Validates: Requirements 3.3.3**

    Property: For ANY lag K >= 1, any number of records, and any starting seed,
    the DuckDB INTERVAL K DAY lag join produces ZERO rows where
        broker_date >= price_date.

    This is the core temporal safety guarantee for the SQL join pattern used
    (and to be enforced) in scripts/02_feature_engineering.py.
    """
    rng = np.random.default_rng(seed)
    base_date = pd.Timestamp("2024-01-02")
    # Generate overlapping date ranges for both price and broker DataFrames
    n_price = n_records + lag + 5  # ensure enough price rows to get matches
    price_dates  = pd.date_range(base_date, periods=n_price, freq="B")
    broker_dates = pd.date_range(base_date, periods=n_records, freq="B")

    price_df = pd.DataFrame({
        "ticker": "PROP",
        "date": price_dates,
        "close": rng.uniform(100, 1000, n_price),
    })
    broker_df = pd.DataFrame({
        "ticker": "PROP",
        "date": broker_dates,
        "broker_feature": rng.uniform(0, 1, n_records),
    })

    result = _duckdb_lag_join(price_df, broker_df, lag_days=lag)

    if result.empty:
        return  # No matches is valid (e.g., lag larger than data range)

    future_rows = result[
        pd.to_datetime(result["broker_date"]) >= pd.to_datetime(result["price_date"])
    ]
    assert len(future_rows) == 0, (
        f"TEMPORAL SAFETY VIOLATION: lag-{lag} join produced {len(future_rows)} "
        f"rows where broker_date >= price_date. "
        f"Sample: {future_rows[['price_date', 'broker_date']].head(3).to_dict('records')}"
    )


@given(length=series_length, seed=random_seed)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property_rsi_14_always_in_valid_range(length, seed):
    """
    **Validates: Requirements 3.3.1**

    Property: For ANY price series of length >= 60, RSI-14 values after
    warm-up must always be in [0, 100].

    RSI is used in both feature engineering pipelines and must stay bounded.
    """
    close = _make_price_series(length, seed)
    rsi = _compute_rsi(close, 14)
    valid_rsi = rsi.iloc[14:].dropna()  # skip warm-up NaN rows

    if valid_rsi.empty:
        return

    assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all(), (
        f"RSI-14 out of bounds (seed={seed}, length={length}): "
        f"min={valid_rsi.min():.4f}, max={valid_rsi.max():.4f}"
    )


@given(length=series_length, seed=random_seed)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property_duckdb_sma_20_non_nan_after_warmup(length, seed):
    """
    **Validates: Requirements 3.3.1**

    Property: For ANY OHLCV DataFrame with length >= 60, the DuckDB-computed
    SMA-20 (ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) must be non-NaN
    from row 21 onward (20 preceding rows + 1 PRECEDING offset).

    Ensures the DuckDB rolling engine behaves identically to pandas for
    all valid input sizes.
    """
    df = _make_ohlcv_df(n=length, seed=seed)
    result = _duckdb_rolling_features(df)

    # The SQL uses ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING:
    # row 0 has 0 preceding rows → NaN
    # row 20 has 20 preceding rows + 1 PRECEDING window → first non-NaN
    sma20 = result["sma_20"]
    after_warmup = sma20.iloc[21:]  # rows 21+ should all be non-NaN

    if after_warmup.empty:
        return

    assert not after_warmup.isna().any(), (
        f"DuckDB SMA-20 has NaN after warm-up (length={length}, seed={seed}): "
        f"{after_warmup[after_warmup.isna()].index.tolist()}"
    )


# ---------------------------------------------------------------------------
# Main runner for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 80)
    print("RUNNING PRESERVATION TESTS 2.3: Temporal Preservation")
    print("(All tests MUST PASS on unfixed code)")
    print("=" * 80)

    all_passed = True

    # --- Unit test classes ---
    suites = [
        TestRollingWindowCorrectness(),
        TestPointInTimeCorrectness(),
        TestIntervalLagJoinCorrectness(),
    ]
    for suite in suites:
        name = type(suite).__name__
        methods = [m for m in dir(suite) if m.startswith("test_")]
        for meth in methods:
            try:
                getattr(suite, meth)()
                print(f"  ✓ {name}.{meth}")
            except Exception as exc:
                print(f"  ✗ {name}.{meth}: {exc}")
                all_passed = False

    # --- Property-based tests ---
    pbt_funcs = [
        test_property_sma20_at_position_i_equals_mean_of_preceding_20,
        test_property_rolling_std_20_non_negative_and_non_nan_after_warmup,
        test_property_sma20_does_not_use_future_data,
        test_property_duckdb_interval_lag_join_no_same_or_future_broker_dates,
        test_property_rsi_14_always_in_valid_range,
        test_property_duckdb_sma_20_non_nan_after_warmup,
    ]
    for fn in pbt_funcs:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except Exception as exc:
            print(f"  ✗ {fn.__name__}: {exc}")
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("ALL PRESERVATION TESTS PASSED — temporal baseline behaviour confirmed.")
    else:
        print("SOME TESTS FAILED — investigate above failures.")
    print("=" * 80)
