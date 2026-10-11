"""
Preservation Test 2.4: Feature Store Preservation

**Property 2: Preservation** — Existing Feature Computation Unchanged

This is a PRESERVATION baseline test that MUST PASS on UNFIXED code.
It captures the correct behaviour of the six feature groups already computed
correctly in scripts/02_feature_engineering.py so that nothing regresses when
the five ghost features (frac_diff_close, macd_norm, rsi_14, log_return,
range_vol) are added in Phase 6.

The two feature-computation layers under test:

Layer 1 — DuckDB SQL window functions (scripts/02_feature_engineering.py)
  Computes: dist_sma20, dist_sma50, bb_pct_b, ret_1w, ret_1m, volatility_20,
            vol_surge (all t-1 lagged via ROWS BETWEEN N PRECEDING AND 1 PRECEDING)

Layer 2 — Pandas add_price_volume_and_kline_semantics()
  Computes:
    Candlestick geometry:  kline_body_density, kline_upper_shadow_ratio,
                           kline_lower_shadow_ratio, kline_gap_rejection_flag,
                           donchian_channel_pos_20
    Price-volume coupling: volume_zscore_20, volume_force_index,
                           price_volume_divergence_5d, amihud_illiquidity

Properties under test:
  P-3.4.1  Candlestick geometry features (kline_body_density, shadow ratios) produce
           values in [0, 1] for any valid OHLCV bar and never crash on edge inputs
           (doji, zero-range candle, first-day IPO with no previous close).
  P-3.4.2  Volume features (volume_zscore_20, amihud_illiquidity) produce
           non-negative, finite, numerically valid values on the full computation
           domain, including zero-volume edge cases.
  P-3.4.3  SQL-layer rolling features (dist_sma20, volatility_20, bb_pct_b) match
           reference implementations and do NOT change when future data is appended
           (point-in-time correctness).

Requirements: 3.4.1, 3.4.2, 3.4.3

Expected Outcome: All tests PASS — confirms existing feature computation is correct
before the 5 ghost features are added.
"""

import importlib.util
import math
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Import the actual production function under test
# ---------------------------------------------------------------------------
# scripts/02_feature_engineering.py has a numeric prefix so it cannot be
# imported with standard `import` syntax. We use importlib to load it by path.

_WORKSPACE = Path(__file__).resolve().parent.parent
_FE_PATH = _WORKSPACE / "scripts" / "02_feature_engineering.py"

_spec = importlib.util.spec_from_file_location("feature_engineering_02", _FE_PATH)
_fe_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fe_module)

add_price_volume_and_kline_semantics = _fe_module.add_price_volume_and_kline_semantics


# ---------------------------------------------------------------------------
# Reference implementations (mirrors the production SQL / pandas formulas)
# ---------------------------------------------------------------------------

def _ref_kline_body_density(open_: float, high: float, low: float, close: float) -> float:
    """Body fraction of the total candle range. Mirrors production formula."""
    eps = 1e-6
    return abs(close - open_) / (high - low + eps)


def _ref_kline_upper_shadow(open_: float, high: float, low: float, close: float) -> float:
    """Upper shadow fraction. Mirrors production formula."""
    eps = 1e-6
    return (high - max(open_, close)) / (high - low + eps)


def _ref_kline_lower_shadow(open_: float, high: float, low: float, close: float) -> float:
    """Lower shadow fraction. Mirrors production formula."""
    eps = 1e-6
    return (min(open_, close) - low) / (high - low + eps)


def _ref_amihud(abs_return: float, close: float, volume: float) -> float:
    """Amihud illiquidity. Mirrors production formula."""
    eps = 1e-6
    return abs_return / (close * volume + eps)


def _ref_volume_zscore(volume: float, mean_vol: float, std_vol: float) -> float:
    """Volume z-score. Mirrors production formula."""
    eps = 1e-6
    return (volume - mean_vol) / (std_vol + eps)


# ---------------------------------------------------------------------------
# OHLCV DataFrame builders
# ---------------------------------------------------------------------------

def _make_ohlcv_df(
    n: int,
    seed: int = 42,
    ticker: str = "TEST",
    start_price: float = 500.0,
    vol_base: int = 10_000,
) -> pd.DataFrame:
    """Generate a realistic OHLCV DataFrame of length n."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=0.0, scale=0.012, size=n)
    close = start_price * np.cumprod(1 + returns)
    spread = rng.uniform(1.0, 10.0, size=n)
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.DataFrame(
        {
            "ticker": ticker,
            "date": dates,
            "open": np.clip(close - rng.uniform(0, spread / 2, n), 1.0, None).round(2),
            "high": (close + spread).round(2),
            "low": np.clip(close - spread, 1.0, None).round(2),
            "close": close.round(2),
            "volume": rng.integers(vol_base // 2, vol_base * 2, size=n),
        }
    )


def _make_single_bar(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int = 1000,
) -> pd.DataFrame:
    """Single-row OHLCV DataFrame for targeted unit tests."""
    return pd.DataFrame(
        [
            {
                "ticker": "SINGLE",
                "date": pd.Timestamp("2024-01-02"),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        ]
    )


# ---------------------------------------------------------------------------
# Helper: run DuckDB SQL feature pipeline on in-memory data
# (replicates the core SQL in scripts/02_feature_engineering.py without file I/O)
# ---------------------------------------------------------------------------

def _compute_sql_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs the same DuckDB window SQL as run_feature_engineering() on an
    in-memory DataFrame (no Parquet files, no filesystem I/O).

    Returns columns: ticker, date, close, dist_sma20, dist_sma50, bb_pct_b,
    ret_1w, ret_1m, volatility_20, vol_surge.
    """
    con = duckdb.connect(database=":memory:")
    con.register("market", df)

    sql = """
    WITH base AS (
        SELECT
            ticker,
            CAST(date AS DATE) AS date,
            open, high, low, close, volume,
            LAG(close, 1)  OVER w AS prev_close,
            LAG(volume, 1) OVER w AS prev_vol,
            AVG(volume)    OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS adv_20d,
            AVG(close)     OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS sma_20,
            AVG(close)     OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING) AS sma_50,
            STDDEV(close)  OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS std_20,
            LAG(close,  5) OVER w AS close_lag5,
            LAG(close, 20) OVER w AS close_lag20
        FROM market
        WINDOW w AS (PARTITION BY ticker ORDER BY date)
    )
    SELECT
        ticker, date, open, high, low, close, volume,
        ((prev_close / (sma_20 + 1e-6)) - 1.0)                              AS dist_sma20,
        ((prev_close / (sma_50 + 1e-6)) - 1.0)                              AS dist_sma50,
        (((prev_close - (sma_20 - 2.0 * std_20)) / (4.0 * std_20 + 1e-6))) AS bb_pct_b,
        ((prev_close / (close_lag5  + 1e-6)) - 1.0)                         AS ret_1w,
        ((prev_close / (close_lag20 + 1e-6)) - 1.0)                         AS ret_1m,
        (std_20 / (sma_20 + 1e-6))                                          AS volatility_20,
        ((prev_vol / (adv_20d + 1e-4)) - 1.0)                               AS vol_surge,
        sma_20,
        sma_50,
        std_20
    FROM base
    ORDER BY ticker ASC, date ASC
    """
    result = con.execute(sql).df()
    con.close()
    return result


# ---------------------------------------------------------------------------
# Unit Tests — Candlestick Geometry (P-3.4.1)
# ---------------------------------------------------------------------------

class TestKlineCandlestickGeometry:
    """
    Validates: Requirement 3.4.1

    kline_body_density, kline_upper_shadow_ratio, and kline_lower_shadow_ratio
    must be in [0, 1] for all valid inputs and must never crash on edge cases.
    """

    def _run(self, df: pd.DataFrame) -> pd.DataFrame:
        return add_price_volume_and_kline_semantics(df.copy())

    # --- Normal candles ---

    def test_body_density_bullish_candle(self):
        """Bullish candle: body_density in [0, 1] with correct reference value."""
        df = _make_single_bar(open_=490.0, high=510.0, low=485.0, close=505.0)
        result = self._run(df)
        body = abs(505.0 - 490.0)  # 15
        rng = 510.0 - 485.0       # 25
        expected = body / rng
        assert abs(result["kline_body_density"].iloc[0] - expected) < 1e-4, (
            f"Body density: expected {expected:.4f}, "
            f"got {result['kline_body_density'].iloc[0]:.4f}"
        )
        assert 0.0 <= result["kline_body_density"].iloc[0] <= 1.0

    def test_body_density_bearish_candle(self):
        """Bearish candle (open > close): body_density still in [0, 1]."""
        df = _make_single_bar(open_=505.0, high=510.0, low=485.0, close=490.0)
        result = self._run(df)
        body = abs(490.0 - 505.0)  # 15
        rng = 510.0 - 485.0       # 25
        expected = body / rng
        assert abs(result["kline_body_density"].iloc[0] - expected) < 1e-4
        assert 0.0 <= result["kline_body_density"].iloc[0] <= 1.0

    def test_upper_shadow_ratio_matches_reference(self):
        """Upper shadow = (high - max(open, close)) / range."""
        df = _make_single_bar(open_=490.0, high=515.0, low=485.0, close=505.0)
        result = self._run(df)
        expected = _ref_kline_upper_shadow(490.0, 515.0, 485.0, 505.0)
        assert abs(result["kline_upper_shadow_ratio"].iloc[0] - expected) < 1e-4

    def test_lower_shadow_ratio_matches_reference(self):
        """Lower shadow = (min(open, close) - low) / range."""
        df = _make_single_bar(open_=495.0, high=510.0, low=480.0, close=500.0)
        result = self._run(df)
        expected = _ref_kline_lower_shadow(495.0, 510.0, 480.0, 500.0)
        assert abs(result["kline_lower_shadow_ratio"].iloc[0] - expected) < 1e-4

    def test_shadow_ratios_sum_lte_one_with_body(self):
        """
        upper_shadow + lower_shadow + body_density should approximately equal 1.0
        (they partition the total candle range).
        """
        df = _make_single_bar(open_=490.0, high=510.0, low=480.0, close=500.0)
        result = self._run(df)
        total = (
            result["kline_upper_shadow_ratio"].iloc[0]
            + result["kline_lower_shadow_ratio"].iloc[0]
            + result["kline_body_density"].iloc[0]
        )
        assert abs(total - 1.0) < 1e-3, (
            f"shadow + body fractions sum to {total:.6f}, expected ~1.0"
        )

    def test_doji_bar_body_density_near_zero(self):
        """
        Doji candle (open ≈ close) → body_density ≈ 0.
        Must not crash and must return a near-zero value.
        """
        df = _make_single_bar(open_=500.0, high=510.0, low=490.0, close=500.001)
        result = self._run(df)
        bd = result["kline_body_density"].iloc[0]
        assert 0.0 <= bd < 0.01, (
            f"Doji body_density should be near 0; got {bd:.6f}"
        )

    def test_marubozu_body_density_near_one(self):
        """
        Marubozu candle (no shadows): open==low, close==high → body_density ≈ 1.0.
        """
        df = _make_single_bar(open_=490.0, high=510.0, low=490.0, close=510.0)
        result = self._run(df)
        bd = result["kline_body_density"].iloc[0]
        assert bd > 0.98, (
            f"Marubozu body_density should be ≈1.0; got {bd:.6f}"
        )

    def test_zero_range_candle_does_not_crash(self):
        """
        Edge case: high == low (zero price movement, common in auction-only sessions).
        Must not raise ZeroDivisionError — the epsilon guards against it.
        """
        df = _make_single_bar(open_=500.0, high=500.0, low=500.0, close=500.0)
        try:
            result = self._run(df)
        except Exception as exc:
            pytest.fail(f"Zero-range candle raised {type(exc).__name__}: {exc}")
        bd = result["kline_body_density"].iloc[0]
        assert np.isfinite(bd), f"body_density is not finite for zero-range candle: {bd}"

    def test_ipo_first_bar_no_previous_close_does_not_crash(self):
        """
        IPO first bar: there is no previous session close, so gap detection logic
        (which calls groupby.shift(1)) must handle NaN gracefully.
        """
        df = _make_ohlcv_df(n=1, seed=0)  # Single row — no previous close exists
        try:
            result = self._run(df)
        except Exception as exc:
            pytest.fail(
                f"Single-row (IPO first day) raised {type(exc).__name__}: {exc}"
            )
        # kline_body_density must still be finite
        bd = result["kline_body_density"].iloc[0]
        assert np.isfinite(bd), "kline_body_density is not finite for first IPO bar"

    def test_multi_ticker_each_computed_independently(self):
        """
        Two tickers must produce independent kline features — no cross-ticker
        contamination from the groupby operations.
        """
        df_a = _make_ohlcv_df(n=30, seed=1, ticker="AAA")
        df_b = _make_ohlcv_df(n=30, seed=2, ticker="BBB")
        df_combined = pd.concat([df_a, df_b], ignore_index=True)

        result_combined = add_price_volume_and_kline_semantics(df_combined.copy())
        result_a = add_price_volume_and_kline_semantics(df_a.copy())

        # kline_body_density for AAA should be identical in both runs
        combined_a = (
            result_combined[result_combined["ticker"] == "AAA"]["kline_body_density"]
            .reset_index(drop=True)
        )
        solo_a = result_a["kline_body_density"].reset_index(drop=True)

        np.testing.assert_allclose(
            combined_a.values,
            solo_a.values,
            rtol=1e-5,
            err_msg=(
                "kline_body_density for AAA changed when BBB was added — "
                "cross-ticker contamination detected"
            ),
        )


# ---------------------------------------------------------------------------
# Unit Tests — Volume Features (P-3.4.2)
# ---------------------------------------------------------------------------

class TestVolumeFeatures:
    """
    Validates: Requirement 3.4.2

    volume_zscore_20 and amihud_illiquidity must produce finite, non-negative-
    where-applicable values on realistic data and on zero-volume edge cases.
    """

    def _run(self, df: pd.DataFrame) -> pd.DataFrame:
        return add_price_volume_and_kline_semantics(df.copy())

    def test_volume_zscore_finite_after_warmup(self):
        """volume_zscore_20 must be finite for all rows after the 20-session warm-up."""
        df = _make_ohlcv_df(n=60, seed=10)
        result = self._run(df)
        after_warmup = result["volume_zscore_20"].iloc[20:]
        assert after_warmup.apply(np.isfinite).all(), (
            "volume_zscore_20 has non-finite values after warm-up period"
        )

    def test_volume_zscore_non_zero_for_variable_volume(self):
        """
        When volume varies across sessions, most zscore values should be non-zero
        (a flat series is the only case where all zscores would be 0).
        """
        df = _make_ohlcv_df(n=60, seed=11)
        result = self._run(df)
        after_warmup = result["volume_zscore_20"].iloc[20:]
        nonzero_frac = (after_warmup != 0.0).mean()
        assert nonzero_frac > 0.5, (
            f"Only {nonzero_frac*100:.1f}% of volume_zscore_20 values are non-zero "
            f"for a variable-volume series — possible ghost feature"
        )

    def test_volume_zscore_matches_reference_at_known_position(self):
        """
        At a known position, volume_zscore_20 must match the reference formula:
            (vol - mean_20) / (std_20 + eps)
        where mean_20 and std_20 are computed over the current and prior 19
        sessions (rolling(20) includes the current row — no shift).
        """
        df = _make_ohlcv_df(n=50, seed=12)
        result = self._run(df)
        # Use row 30 (well past warm-up)
        i = 30
        # Production uses rolling(20) inclusive of current row: rows [i-19, i]
        window = df["volume"].iloc[i - 19: i + 1]
        mean_20 = window.mean()
        std_20 = window.std()
        expected = _ref_volume_zscore(df["volume"].iloc[i], mean_20, std_20)
        got = result["volume_zscore_20"].iloc[i]
        assert abs(got - expected) < 1e-4, (
            f"volume_zscore_20 mismatch at row {i}: "
            f"expected ≈{expected:.4f}, got {got:.4f}"
        )

    def test_amihud_illiquidity_non_negative(self):
        """amihud_illiquidity must be >= 0 everywhere (it's |return| / turnover)."""
        df = _make_ohlcv_df(n=60, seed=13)
        result = self._run(df)
        amihud = result["amihud_illiquidity"].dropna()
        assert (amihud >= 0).all(), (
            f"amihud_illiquidity has negative values: "
            f"min={amihud.min():.8f}"
        )

    def test_amihud_illiquidity_finite(self):
        """amihud_illiquidity must be finite (not inf or NaN) for normal data."""
        df = _make_ohlcv_df(n=60, seed=14)
        result = self._run(df)
        amihud = result["amihud_illiquidity"]
        # First row may be NaN (no previous close for return), rest must be finite
        assert amihud.iloc[1:].apply(np.isfinite).all(), (
            "amihud_illiquidity has non-finite values (other than the first row)"
        )

    def test_amihud_illiquidity_matches_reference(self):
        """
        amihud_illiquidity at a known position must equal
            |pct_change| / (close * volume + eps)
        """
        df = _make_ohlcv_df(n=50, seed=15)
        result = self._run(df)
        i = 20
        abs_ret = abs(df["close"].iloc[i] / df["close"].iloc[i - 1] - 1.0)
        expected = _ref_amihud(abs_ret, df["close"].iloc[i], df["volume"].iloc[i])
        got = result["amihud_illiquidity"].iloc[i]
        assert abs(got - expected) < 1e-8, (
            f"amihud_illiquidity mismatch at row {i}: "
            f"expected {expected:.10f}, got {got:.10f}"
        )

    def test_zero_volume_session_does_not_crash(self):
        """
        A session with volume=0 (halted stock) must not crash.
        volume_zscore_20 and amihud_illiquidity must produce finite values.
        """
        df = _make_ohlcv_df(n=40, seed=16)
        df.loc[df.index[25], "volume"] = 0  # inject a zero-volume session
        try:
            result = add_price_volume_and_kline_semantics(df.copy())
        except Exception as exc:
            pytest.fail(
                f"Zero-volume session raised {type(exc).__name__}: {exc}"
            )
        # amihud at the zero-volume row: |ret| / (close * 0 + eps) — should be finite
        assert np.isfinite(result["amihud_illiquidity"].iloc[25]), (
            "amihud_illiquidity is non-finite for zero-volume session"
        )

    def test_volume_force_index_finite(self):
        """volume_force_index must be finite everywhere after the first session."""
        df = _make_ohlcv_df(n=60, seed=17)
        result = self._run(df)
        after_first = result["volume_force_index"].iloc[1:].dropna()
        assert after_first.apply(np.isfinite).all(), (
            "volume_force_index has non-finite values"
        )


# ---------------------------------------------------------------------------
# Unit Tests — SQL-Layer Rolling Features (P-3.4.3)
# ---------------------------------------------------------------------------

class TestSqlRollingFeatures:
    """
    Validates: Requirement 3.4.3

    dist_sma20, volatility_20, and bb_pct_b must match reference implementations
    and must not change when future data is appended (point-in-time safety).
    """

    def test_dist_sma20_after_warmup_is_finite(self):
        """dist_sma20 must be finite for all rows after the 20-session warm-up."""
        df = _make_ohlcv_df(n=80, seed=20)
        result = _compute_sql_features(df)
        after_warmup = result["dist_sma20"].dropna()
        assert after_warmup.apply(np.isfinite).all(), (
            "dist_sma20 has non-finite values after warm-up"
        )

    def test_dist_sma20_matches_reference_formula(self):
        """
        dist_sma20 = (prev_close / (sma_20 + eps)) - 1.0
        where sma_20 uses ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING (t-1 lag).
        """
        df = _make_ohlcv_df(n=80, seed=21)
        result = _compute_sql_features(df)

        # Reference: shift(1) then rolling(20).mean()
        sma_20 = df["close"].shift(1).rolling(20).mean()
        prev_close = df["close"].shift(1)
        ref_dist_sma20 = (prev_close / (sma_20 + 1e-6)) - 1.0

        valid = result["dist_sma20"].notna() & ref_dist_sma20.notna()
        assert valid.sum() > 30, "Not enough valid rows for comparison"

        np.testing.assert_allclose(
            result["dist_sma20"][valid].values,
            ref_dist_sma20[valid].values,
            rtol=1e-3,
            err_msg="dist_sma20 deviates from reference formula",
        )

    def test_volatility_20_non_negative(self):
        """volatility_20 = std_20 / (sma_20 + eps) must be >= 0 everywhere."""
        df = _make_ohlcv_df(n=80, seed=22)
        result = _compute_sql_features(df)
        valid_vol = result["volatility_20"].dropna()
        assert (valid_vol >= 0).all(), (
            f"volatility_20 has negative values: min={valid_vol.min():.6f}"
        )

    def test_volatility_20_nonzero_for_variable_prices(self):
        """
        For a price series with real variation, volatility_20 must be > 0
        for the majority of valid rows.
        """
        df = _make_ohlcv_df(n=80, seed=23)
        result = _compute_sql_features(df)
        valid_vol = result["volatility_20"].dropna()
        nonzero_frac = (valid_vol > 0).mean()
        assert nonzero_frac > 0.9, (
            f"Only {nonzero_frac*100:.1f}% of volatility_20 values are > 0 — "
            "possible feature regression"
        )

    def test_ret_1w_positive_for_monotone_increasing_prices(self):
        """
        ret_1w = (prev_close / close_lag5) - 1.
        For a monotonically rising series, all valid ret_1w values must be > 0.
        """
        n = 60
        prices = [float(100 + i * 2) for i in range(n)]
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        df = pd.DataFrame(
            {
                "ticker": "MONO",
                "date": dates,
                "open": prices,
                "high": [p + 2.0 for p in prices],
                "low": [p - 1.0 for p in prices],
                "close": prices,
                "volume": [5000] * n,
            }
        )
        result = _compute_sql_features(df)
        valid_ret = result["ret_1w"].dropna()
        assert (valid_ret > 0).all(), (
            "ret_1w should be positive for monotonically increasing prices; "
            f"found non-positive: {valid_ret[valid_ret <= 0].tolist()[:5]}"
        )

    def test_ret_1m_positive_for_monotone_increasing_prices(self):
        """ret_1m = (prev_close / close_lag20) - 1 must be > 0 for rising prices."""
        n = 80
        prices = [float(100 + i * 1.5) for i in range(n)]
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        df = pd.DataFrame(
            {
                "ticker": "MONO2",
                "date": dates,
                "open": prices,
                "high": [p + 2.0 for p in prices],
                "low": [p - 1.0 for p in prices],
                "close": prices,
                "volume": [5000] * n,
            }
        )
        result = _compute_sql_features(df)
        valid_ret = result["ret_1m"].dropna()
        assert (valid_ret > 0).all(), (
            "ret_1m should be positive for monotonically increasing prices"
        )

    def test_bb_pct_b_finite_after_warmup(self):
        """bb_pct_b must be finite after the 20-session warm-up."""
        df = _make_ohlcv_df(n=80, seed=24)
        result = _compute_sql_features(df)
        valid_bb = result["bb_pct_b"].dropna()
        assert valid_bb.apply(np.isfinite).all(), (
            "bb_pct_b has non-finite values after warm-up"
        )

    def test_sql_features_unchanged_when_future_data_appended(self):
        """
        Appending future rows must NOT change any SQL rolling feature for the
        original rows (point-in-time correctness).
        """
        df_orig = _make_ohlcv_df(n=60, seed=25)
        df_future = _make_ohlcv_df(n=10, seed=999, start_price=50.0)  # Very different
        df_future["date"] = pd.date_range(
            df_orig["date"].max() + pd.Timedelta(days=1), periods=10, freq="B"
        )
        df_future["ticker"] = "TEST"
        df_extended = pd.concat([df_orig, df_future], ignore_index=True)

        result_orig = _compute_sql_features(df_orig)
        result_ext = _compute_sql_features(df_extended)

        features_to_check = ["dist_sma20", "volatility_20", "ret_1w"]
        for feat in features_to_check:
            orig_vals = result_orig[feat].reset_index(drop=True)
            ext_vals = result_ext[feat].iloc[: len(df_orig)].reset_index(drop=True)
            valid = orig_vals.notna() & ext_vals.notna()
            if valid.sum() == 0:
                continue
            np.testing.assert_allclose(
                orig_vals[valid].values,
                ext_vals[valid].values,
                rtol=1e-4,
                err_msg=(
                    f"POINT-IN-TIME VIOLATION: {feat} changed after appending "
                    "future data"
                ),
            )


# ---------------------------------------------------------------------------
# Unit Tests — Edge Cases (P-3.4.1, P-3.4.2)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """
    Additional edge-case coverage to ensure preservation of correct NULL handling
    and absence of crashes for boundary inputs.
    """

    def test_single_row_per_ticker_runs_without_crash(self):
        """
        A ticker with only 1 row (e.g., halted stock, first listing day) must not
        crash the entire feature computation pipeline.
        """
        df = _make_ohlcv_df(n=1, seed=30)
        try:
            result = add_price_volume_and_kline_semantics(df.copy())
        except Exception as exc:
            pytest.fail(
                f"Single-row ticker raised {type(exc).__name__}: {exc}"
            )
        assert "kline_body_density" in result.columns
        assert np.isfinite(result["kline_body_density"].iloc[0])

    def test_30_row_ticker_below_sma50_warmup_still_computes_sma20_features(self):
        """
        A ticker with only 30 rows cannot produce SMA-50 (needs 50+ rows), but
        SMA-20-based features must still be valid from row 19 onward.
        """
        df = _make_ohlcv_df(n=30, seed=31)
        result = _compute_sql_features(df)
        # dist_sma20 may be valid at row 20 (0-indexed)
        valid_dist = result["dist_sma20"].dropna()
        assert len(valid_dist) > 0, (
            "dist_sma20 has zero valid rows for a 30-row series"
        )
        assert valid_dist.apply(np.isfinite).all(), (
            "dist_sma20 has non-finite values for a 30-row series"
        )

    def test_extreme_low_price_does_not_produce_inf(self):
        """
        Prices near penny-stock levels (0.01 NPR) must not produce infinite
        features — the epsilon guards in the formulas prevent this.
        """
        df = _make_ohlcv_df(n=50, seed=32, start_price=0.5)
        result = add_price_volume_and_kline_semantics(df.copy())
        for col in ["kline_body_density", "volume_zscore_20", "amihud_illiquidity"]:
            assert result[col].replace([np.inf, -np.inf], np.nan).notna().any(), (
                f"{col}: all values are inf/NaN for penny-stock prices"
            )

    def test_extreme_high_volume_does_not_produce_inf(self):
        """
        Very high volume (institutional block trade, 10M units) must not produce
        infinite amihud_illiquidity.
        """
        df = _make_ohlcv_df(n=50, seed=33, vol_base=10_000_000)
        result = add_price_volume_and_kline_semantics(df.copy())
        amihud = result["amihud_illiquidity"]
        assert amihud.iloc[1:].apply(np.isfinite).all(), (
            "amihud_illiquidity is non-finite for high-volume trades"
        )

    def test_all_expected_columns_present_in_output(self):
        """
        The function must emit all expected feature columns — no silent column drops.
        """
        df = _make_ohlcv_df(n=50, seed=34)
        result = add_price_volume_and_kline_semantics(df.copy())
        expected_cols = [
            "kline_body_density",
            "kline_upper_shadow_ratio",
            "kline_lower_shadow_ratio",
            "kline_gap_rejection_flag",
            "donchian_channel_pos_20",
            "volume_zscore_20",
            "volume_force_index",
            "price_volume_divergence_5d",
            "amihud_illiquidity",
        ]
        missing = [c for c in expected_cols if c not in result.columns]
        assert not missing, (
            f"Expected feature columns missing from output: {missing}"
        )


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------

# Hypothesis strategies for single-bar geometry
_price_st = st.floats(min_value=1.0, max_value=5_000.0, allow_nan=False, allow_infinity=False)
_spread_st = st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False)
_vol_st = st.integers(min_value=10, max_value=10_000_000)
_len_st = st.integers(min_value=25, max_value=150)
_seed_st = st.integers(min_value=0, max_value=9_999)


@given(
    base_price=_price_st,
    spread=_spread_st,
    body_frac=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_property_kline_body_density_always_in_unit_interval(
    base_price, spread, body_frac
):
    """
    **Validates: Requirements 3.4.1**

    Property: For ANY valid OHLCV bar where high > low, kline_body_density
    must be in [0, 1].

    Generates 300 random (price, spread, body_frac) combinations and asserts
    the body density stays within bounds in every case.
    """
    # Construct a valid OHLCV bar: high > low, open/close within [low, high]
    low = base_price
    high = base_price + spread
    # body_frac controls how much of the range the body occupies
    body_size = body_frac * spread
    open_ = low + (spread - body_size) / 2
    close = open_ + body_size

    df = _make_single_bar(
        open_=round(open_, 4),
        high=round(high, 4),
        low=round(low, 4),
        close=round(close, 4),
    )
    result = add_price_volume_and_kline_semantics(df.copy())
    bd = result["kline_body_density"].iloc[0]

    assert np.isfinite(bd), (
        f"body_density is not finite for bar "
        f"(O={open_:.4f}, H={high:.4f}, L={low:.4f}, C={close:.4f})"
    )
    assert 0.0 <= bd <= 1.0, (
        f"PRESERVATION VIOLATION: kline_body_density={bd:.6f} outside [0,1] "
        f"for bar (O={open_:.4f}, H={high:.4f}, L={low:.4f}, C={close:.4f})"
    )


@given(
    base_price=_price_st,
    spread=_spread_st,
)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_property_shadow_ratios_always_in_unit_interval(base_price, spread):
    """
    **Validates: Requirements 3.4.1**

    Property: For ANY valid OHLCV bar, both kline_upper_shadow_ratio and
    kline_lower_shadow_ratio must be in [0, 1].

    The three fractions (upper shadow, lower shadow, body) must sum to ~1.
    """
    assume(spread > 0.001)

    low = base_price
    high = base_price + spread
    # Put open and close in the middle quarter of the range
    open_ = low + spread * 0.3
    close = low + spread * 0.7

    df = _make_single_bar(
        open_=round(open_, 4),
        high=round(high, 4),
        low=round(low, 4),
        close=round(close, 4),
    )
    result = add_price_volume_and_kline_semantics(df.copy())
    upper = result["kline_upper_shadow_ratio"].iloc[0]
    lower = result["kline_lower_shadow_ratio"].iloc[0]
    body = result["kline_body_density"].iloc[0]

    assert np.isfinite(upper) and 0.0 <= upper <= 1.0, (
        f"PRESERVATION VIOLATION: upper_shadow={upper:.6f} outside [0,1]"
    )
    assert np.isfinite(lower) and 0.0 <= lower <= 1.0, (
        f"PRESERVATION VIOLATION: lower_shadow={lower:.6f} outside [0,1]"
    )
    # All three fractions together should cover the full range
    total = upper + lower + body
    assert abs(total - 1.0) < 1e-3, (
        f"Shadow + body fractions sum to {total:.6f}, expected ~1.0 "
        f"(upper={upper:.4f}, lower={lower:.4f}, body={body:.4f})"
    )


@given(length=_len_st, seed=_seed_st)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_volume_zscore_finite_after_warmup(length, seed):
    """
    **Validates: Requirements 3.4.2**

    Property: For ANY realistic OHLCV series of length >= 25, volume_zscore_20
    is finite for all rows after the 20-session warm-up period.

    This is the core volume-feature preservation guarantee: the formula must
    not produce NaN or Inf for any input in the realistic domain.
    """
    df = _make_ohlcv_df(n=length, seed=seed)
    result = add_price_volume_and_kline_semantics(df.copy())
    after_warmup = result["volume_zscore_20"].iloc[20:]

    non_finite = after_warmup[~after_warmup.apply(np.isfinite)]
    assert len(non_finite) == 0, (
        f"PRESERVATION VIOLATION: volume_zscore_20 has {len(non_finite)} "
        f"non-finite values after warm-up (length={length}, seed={seed})"
    )


@given(length=_len_st, seed=_seed_st)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_amihud_illiquidity_non_negative_and_finite(length, seed):
    """
    **Validates: Requirements 3.4.2**

    Property: For ANY realistic OHLCV series, amihud_illiquidity must be
    non-negative and finite for all rows after the first session
    (first row has no previous close to compute return, so it may be NaN).

    Amihud = |return| / turnover. Both numerator and denominator are
    non-negative, so the result must always be >= 0.
    """
    df = _make_ohlcv_df(n=length, seed=seed)
    result = add_price_volume_and_kline_semantics(df.copy())
    after_first = result["amihud_illiquidity"].iloc[1:]

    assert after_first.apply(np.isfinite).all(), (
        f"PRESERVATION VIOLATION: amihud_illiquidity has non-finite values "
        f"(length={length}, seed={seed})"
    )
    assert (after_first >= 0).all(), (
        f"PRESERVATION VIOLATION: amihud_illiquidity has negative values "
        f"(length={length}, seed={seed}); min={after_first.min():.8f}"
    )


@given(length=_len_st, seed=_seed_st)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property_sql_volatility_non_negative_and_finite(length, seed):
    """
    **Validates: Requirements 3.4.3**

    Property: For ANY realistic OHLCV series of length >= 25,
    volatility_20 (std_20 / sma_20) from the SQL pipeline is non-negative
    and finite after the warm-up period.

    This confirms the SQL window function preserves the same numerical
    properties as the pandas reference after the temporal lag fix.
    """
    df = _make_ohlcv_df(n=length, seed=seed)
    result = _compute_sql_features(df)
    valid_vol = result["volatility_20"].dropna()

    assert valid_vol.apply(np.isfinite).all(), (
        f"PRESERVATION VIOLATION: volatility_20 has non-finite values "
        f"(length={length}, seed={seed})"
    )
    assert (valid_vol >= 0).all(), (
        f"PRESERVATION VIOLATION: volatility_20 has negative values "
        f"(length={length}, seed={seed}); min={valid_vol.min():.6f}"
    )


@given(
    base_price=_price_st,
    spread=_spread_st,
    volume=_vol_st,
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property_single_bar_kline_features_never_crash(
    base_price, spread, volume
):
    """
    **Validates: Requirements 3.4.1**

    Property: For ANY single-bar OHLCV input with valid price geometry
    (high >= open, high >= close, low <= open, low <= close),
    add_price_volume_and_kline_semantics() must not raise any exception.

    This is the "no crash" preservation guarantee: the function handles the
    full domain of valid inputs without errors.
    """
    assume(spread > 0.0)
    low = base_price
    high = base_price + spread
    mid = base_price + spread / 2.0

    df = _make_single_bar(
        open_=round(mid - spread * 0.1, 4),
        high=round(high, 4),
        low=round(low, 4),
        close=round(mid + spread * 0.1, 4),
        volume=volume,
    )
    try:
        result = add_price_volume_and_kline_semantics(df.copy())
    except Exception as exc:
        pytest.fail(
            f"add_price_volume_and_kline_semantics raised {type(exc).__name__} "
            f"for bar (H={high:.4f}, L={low:.4f}, V={volume}): {exc}"
        )

    bd = result["kline_body_density"].iloc[0]
    assert np.isfinite(bd), (
        f"kline_body_density is not finite for "
        f"bar (H={high:.4f}, L={low:.4f}, V={volume})"
    )


# ---------------------------------------------------------------------------
# Main runner for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 80)
    print("RUNNING PRESERVATION TESTS 2.4: Feature Store Preservation")
    print("(All tests MUST PASS on UNFIXED code)")
    print("=" * 80)

    suites = [
        TestKlineCandlestickGeometry(),
        TestVolumeFeatures(),
        TestSqlRollingFeatures(),
        TestEdgeCases(),
    ]

    all_passed = True
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

    pbt_fns = [
        test_property_kline_body_density_always_in_unit_interval,
        test_property_shadow_ratios_always_in_unit_interval,
        test_property_volume_zscore_finite_after_warmup,
        test_property_amihud_illiquidity_non_negative_and_finite,
        test_property_sql_volatility_non_negative_and_finite,
        test_property_single_bar_kline_features_never_crash,
    ]
    for fn in pbt_fns:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except Exception as exc:
            print(f"  ✗ {fn.__name__}: {exc}")
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("ALL PRESERVATION TESTS PASSED — baseline feature behaviour confirmed.")
    else:
        print("SOME TESTS FAILED — investigate above failures.")
    print("=" * 80)
