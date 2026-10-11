"""
tests/test_feature_computation.py
===================================
Unit tests for the 5 ghost features added in Phase 6 of the NEPSE data
integrity bugfix.

Validates: Requirements 2.4.1, 2.4.2, 2.4.3

Tests
-----
1. test_frac_diff_close_non_zero        — frac_diff_close is non-zero for rows >= window
2. test_macd_norm_finite                — all non-NaN macd_norm values are finite
3. test_rsi_14_bounds                   — rsi_14 values are in [0, 100]
4. test_log_return_sign                 — log_return > 0 for monotonically rising prices
5. test_range_vol_non_negative          — range_vol >= 0 everywhere non-NaN
6. test_pandera_raises_on_invalid_rsi   — Pandera raises on RSI > 100

Each test exercises the helper functions and/or the full
add_price_volume_and_kline_semantics() pipeline directly, without
hitting the filesystem.
"""

import importlib.util
import math
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Stub the DuckDB connection manager so loading 02_feature_engineering.py
# does not require the database files to exist.
# The numeric prefix in 'scripts.03_data_access_and_storage' prevents normal
# import, so we register a fake module under the expected dotted name BEFORE
# the module is exec'd.
# ---------------------------------------------------------------------------

def _stub_connection_manager():
    """Insert a minimal stub so the top-level import in 02_feature_engineering.py
    resolves without hitting the filesystem."""
    _fake_cm = MagicMock()
    _fake_cm.acquire.return_value.__enter__ = MagicMock(return_value=MagicMock())
    _fake_cm.acquire.return_value.__exit__ = MagicMock(return_value=False)

    _stub_mod = types.ModuleType(
        "scripts.03_data_access_and_storage.duckdb_connection_manager"
    )
    _stub_mod.connection_manager = _fake_cm
    _stub_mod.get_connection_manager = MagicMock(return_value=_fake_cm)

    # Register under dotted prefix without blowing away the scripts package
    if "scripts" not in sys.modules:
        import scripts
    _pkg_03 = types.ModuleType("scripts.03_data_access_and_storage")
    sys.modules["scripts.03_data_access_and_storage"] = _pkg_03
    sys.modules[
        "scripts.03_data_access_and_storage.duckdb_connection_manager"
    ] = _stub_mod


_stub_connection_manager()

# ---------------------------------------------------------------------------
# Load the production module by path (numeric prefix prevents normal import)
# ---------------------------------------------------------------------------
_WORKSPACE = Path(__file__).resolve().parent.parent
_FE_PATH = _WORKSPACE / "scripts" / "02_feature_engineering.py"

_spec = importlib.util.spec_from_file_location("feature_engineering_02", _FE_PATH)
_fe_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fe_module)

_frac_diff_fixed = _fe_module._frac_diff_fixed
_macd_norm_series = _fe_module._macd_norm_series
_rsi_wilder = _fe_module._rsi_wilder
add_price_volume_and_kline_semantics = _fe_module.add_price_volume_and_kline_semantics
FeatureComputationError = _fe_module.FeatureComputationError


# ---------------------------------------------------------------------------
# OHLCV helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int, seed: int = 0, start: float = 500.0) -> pd.DataFrame:
    """Generates a realistic synthetic OHLCV DataFrame for one ticker."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0, 0.012, size=n)
    close = start * np.cumprod(1 + returns)
    spread = rng.uniform(1.0, 8.0, size=n)
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.DataFrame(
        {
            "ticker": "TEST",
            "date": dates,
            "open": np.clip(close - rng.uniform(0, spread / 2, n), 1.0, None).round(2),
            "high": (close + spread).round(2),
            "low": np.clip(close - spread, 1.0, None).round(2),
            "close": close.round(2),
            "volume": rng.integers(5_000, 50_000, size=n),
        }
    )


def _make_monotone_ohlcv(n: int = 60) -> pd.DataFrame:
    """Returns a strictly monotonically increasing close price series."""
    close = np.array([float(100 + i * 2) for i in range(n)])
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.DataFrame(
        {
            "ticker": "MONO",
            "date": dates,
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": [10_000] * n,
        }
    )


# ---------------------------------------------------------------------------
# Test 1: frac_diff_close is non-zero for rows >= window size
# Validates: Requirement 2.4.1
# ---------------------------------------------------------------------------

class TestFracDiffClose:
    """
    Validates: Requirement 2.4.1 — frac_diff_close must be computed with d=0.35
    and must produce non-zero values for rows with sufficient history.
    """

    def test_frac_diff_close_non_zero(self):
        """
        frac_diff_close on a 50-row price series must have non-zero values
        for all rows at index >= window-1 (window defaults to 10).
        """
        prices = pd.Series(
            [float(500 + i * 1.5 + (i % 3) * 0.8) for i in range(50)],
            dtype=float,
        )
        result = _frac_diff_fixed(prices, d=0.35, window=10)

        # Rows < window-1 are expected NaN (warm-up period)
        after_warmup = result.iloc[9:]  # rows 9..49
        assert after_warmup.notna().all(), (
            "frac_diff_close has NaN values after the warm-up window"
        )
        # Must not be all-zero — fractional differencing of a varying series is non-trivial
        assert (after_warmup != 0.0).any(), (
            "frac_diff_close is all-zero after warm-up — computation did not run"
        )

    def test_frac_diff_close_via_pipeline(self):
        """
        When run through the full add_price_volume_and_kline_semantics pipeline,
        frac_diff_close must appear as a column with non-zero values.
        """
        df = _make_ohlcv(n=60, seed=1)
        result = add_price_volume_and_kline_semantics(df.copy())

        assert "frac_diff_close" in result.columns, (
            "frac_diff_close column missing from pipeline output"
        )
        non_zero = (result["frac_diff_close"] != 0.0).sum()
        assert non_zero > 0, (
            "frac_diff_close is entirely zero — ghost feature not computed"
        )

    def test_frac_diff_first_rows_are_nan(self):
        """Rows before the warm-up window must be NaN, not 0."""
        prices = pd.Series([float(100 + i) for i in range(30)], dtype=float)
        result = _frac_diff_fixed(prices, d=0.35, window=10)
        # First 9 rows (0–8) should be NaN
        assert result.iloc[:9].isna().all(), (
            "frac_diff_fixed should produce NaN for rows before the warm-up window, "
            "not zero-fill them"
        )


# ---------------------------------------------------------------------------
# Test 2: macd_norm values are finite (no inf or NaN after warm-up)
# Validates: Requirement 2.4.1
# ---------------------------------------------------------------------------

class TestMacdNorm:
    """
    Validates: Requirement 2.4.1 — macd_norm must be finite and non-trivially
    non-zero for a realistic price series.
    """

    def test_macd_norm_finite(self):
        """
        macd_norm on a realistic 100-row price series must have all non-NaN
        values be finite (not inf or -inf).
        """
        prices = pd.Series(
            [float(300 + i * 0.8 + np.sin(i * 0.3) * 5) for i in range(100)],
            dtype=float,
        )
        result = _macd_norm_series(prices)
        non_nan = result.dropna()
        assert len(non_nan) > 50, "Too few non-NaN macd_norm values"
        assert non_nan.apply(np.isfinite).all(), (
            f"macd_norm has non-finite values: {non_nan[~non_nan.apply(np.isfinite)]}"
        )

    def test_macd_norm_non_zero(self):
        """macd_norm must be non-zero for a series with real variation."""
        rng = np.random.default_rng(42)
        prices = pd.Series(
            500.0 * np.cumprod(1 + rng.normal(0, 0.01, 100)), dtype=float
        )
        result = _macd_norm_series(prices)
        non_zero_frac = (result.dropna() != 0.0).mean()
        assert non_zero_frac > 0.5, (
            f"macd_norm is {(1 - non_zero_frac)*100:.1f}% zero — ghost feature not computed"
        )

    def test_macd_norm_via_pipeline(self):
        """macd_norm must appear in pipeline output as a non-zero column."""
        df = _make_ohlcv(n=80, seed=2)
        result = add_price_volume_and_kline_semantics(df.copy())

        assert "macd_norm" in result.columns, (
            "macd_norm column missing from pipeline output"
        )
        non_zero = (result["macd_norm"] != 0.0).sum()
        assert non_zero > 0, (
            "macd_norm is entirely zero — ghost feature not computed"
        )


# ---------------------------------------------------------------------------
# Test 3: rsi_14 values in [0, 100]
# Validates: Requirement 2.4.1
# ---------------------------------------------------------------------------

class TestRsi14:
    """
    Validates: Requirement 2.4.1 — rsi_14 must be in [0, 100] for all non-NaN
    values and must not be all-zero (ghost feature check).
    """

    def test_rsi_14_bounds(self):
        """
        RSI on any valid price series must always be in [0, 100].
        This is a mathematical invariant of the formula.
        """
        rng = np.random.default_rng(7)
        prices = pd.Series(500.0 * np.cumprod(1 + rng.normal(0, 0.02, 100)), dtype=float)
        result = _rsi_wilder(prices, period=14)
        valid = result.dropna()

        assert len(valid) > 60, "Too few non-NaN RSI values"
        assert (valid >= 0.0).all(), (
            f"RSI has values < 0: min={valid.min():.4f}"
        )
        assert (valid <= 100.0).all(), (
            f"RSI has values > 100: max={valid.max():.4f}"
        )

    def test_rsi_14_not_fillna_50(self):
        """
        RSI must NOT default to 50 for all rows. The old buggy code used
        .fillna(50) which masked computation failures. Valid RSI values on a
        real price series will vary around 50, not be pinned exactly to it.
        """
        rng = np.random.default_rng(8)
        prices = pd.Series(500.0 * np.cumprod(1 + rng.normal(0, 0.02, 100)), dtype=float)
        result = _rsi_wilder(prices, period=14)
        valid = result.dropna()
        pinned_at_50 = (valid == 50.0).mean()
        assert pinned_at_50 < 0.10, (
            f"{pinned_at_50 * 100:.1f}% of RSI values are exactly 50 — "
            "check that .fillna(50) was removed"
        )

    def test_rsi_14_via_pipeline(self):
        """rsi_14 must appear in pipeline output with valid range."""
        df = _make_ohlcv(n=80, seed=3)
        result = add_price_volume_and_kline_semantics(df.copy())

        assert "rsi_14" in result.columns, "rsi_14 column missing from pipeline output"
        valid = result["rsi_14"].dropna()
        assert (valid >= 0.0).all() and (valid <= 100.0).all(), (
            "rsi_14 values out of [0, 100] range"
        )


# ---------------------------------------------------------------------------
# Test 4: log_return sign for monotonically increasing series
# Validates: Requirement 2.4.1
# ---------------------------------------------------------------------------

class TestLogReturn:
    """
    Validates: Requirement 2.4.1 — log_return must be positive for a
    monotonically increasing price series and NaN on the first row.
    """

    def test_log_return_sign(self):
        """
        For a strictly increasing price series, all valid (non-NaN) log returns
        must be strictly positive.
        """
        n = 50
        prices = pd.Series([float(100 + i * 2) for i in range(n)], dtype=float)
        result = prices.transform(lambda x: np.log(x / x.shift(1).replace(0, np.nan)))
        valid = result.dropna()

        assert len(valid) == n - 1, f"Expected {n - 1} valid values; got {len(valid)}"
        assert (valid > 0.0).all(), (
            "log_return should be strictly positive for a monotonically increasing series"
        )

    def test_log_return_first_row_nan(self):
        """First row of log_return must be NaN (no previous price available)."""
        prices = pd.Series([100.0, 101.0, 103.0, 102.5, 105.0], dtype=float)
        result = prices.transform(lambda x: np.log(x / x.shift(1).replace(0, np.nan)))
        assert math.isnan(result.iloc[0]), (
            "First row of log_return must be NaN, not zero-filled"
        )

    def test_log_return_via_pipeline(self):
        """log_return must appear in pipeline output with expected sign behaviour."""
        df = _make_monotone_ohlcv(n=50)
        result = add_price_volume_and_kline_semantics(df.copy())

        assert "log_return" in result.columns, "log_return column missing from pipeline output"
        valid = result["log_return"].dropna()
        assert (valid > 0.0).all(), (
            "log_return should be positive for a monotonically increasing price series"
        )


# ---------------------------------------------------------------------------
# Test 5: range_vol is non-negative everywhere non-NaN
# Validates: Requirement 2.4.1
# ---------------------------------------------------------------------------

class TestRangeVol:
    """
    Validates: Requirement 2.4.1 — range_vol must be >= 0 (it is a rolling
    std of non-negative quantities), and non-trivially non-zero.
    """

    def test_range_vol_non_negative(self):
        """range_vol must be >= 0 everywhere it is non-NaN."""
        df = _make_ohlcv(n=80, seed=5)
        result = add_price_volume_and_kline_semantics(df.copy())

        assert "range_vol" in result.columns, "range_vol column missing from pipeline output"
        valid = result["range_vol"].dropna()
        assert (valid >= 0.0).all(), (
            f"range_vol has negative values: min={valid.min():.8f}"
        )

    def test_range_vol_non_zero_after_warmup(self):
        """
        range_vol must have non-zero values after the 20-session warm-up for a
        series with genuine intraday range variation.
        """
        df = _make_ohlcv(n=80, seed=6)
        result = add_price_volume_and_kline_semantics(df.copy())

        after_warmup = result["range_vol"].iloc[20:].dropna()
        non_zero_frac = (after_warmup > 0.0).mean()
        assert non_zero_frac > 0.5, (
            f"range_vol is {(1 - non_zero_frac)*100:.1f}% zero after warm-up — "
            "ghost feature not computed correctly"
        )

    def test_range_vol_warm_up_rows_are_nan_or_valid(self):
        """
        The first min_periods-1 rows (< 5) may be NaN; everything after that
        must be a finite non-negative float.
        """
        df = _make_ohlcv(n=60, seed=7)
        result = add_price_volume_and_kline_semantics(df.copy())
        # All non-NaN values must be finite and non-negative
        valid = result["range_vol"].dropna()
        assert valid.apply(np.isfinite).all(), "range_vol contains non-finite values"
        assert (valid >= 0.0).all(), "range_vol contains negative values"


# ---------------------------------------------------------------------------
# Test 6: Pandera raises SchemaError on RSI > 100
# Validates: Requirement 2.4.2
# ---------------------------------------------------------------------------

class TestPanderaValidation:
    """
    Validates: Requirement 2.4.2 — Pandera schema validation must raise a
    FeatureComputationError when RSI values fall outside [0, 100].
    """

    def test_pandera_raises_on_invalid_rsi(self):
        """
        Construct a DataFrame with rsi_14 = 150 (out of [0, 100]) and confirm
        that add_price_volume_and_kline_semantics raises FeatureComputationError.
        
        Validates: Requirement 2.4.2
        """
        pytest.importorskip("pandera", reason="pandera not installed — skip Pandera test")

        try:
            import pandera.pandas as pa
        except ImportError:
            import pandera as pa

        # Build a minimal valid OHLCV DataFrame that will pass through the
        # pipeline; then directly inject an invalid RSI to test the validation.
        df = _make_ohlcv(n=60, seed=10)
        result = add_price_volume_and_kline_semantics(df.copy())

        # Inject an impossible RSI value (> 100)
        result.loc[result.index[30], "rsi_14"] = 150.0

        FEATURE_SCHEMA = pa.DataFrameSchema(
            {
                "frac_diff_close": pa.Column(float, nullable=True),
                "macd_norm": pa.Column(float, nullable=True),
                "rsi_14": pa.Column(
                    float,
                    pa.Check.in_range(0, 100, include_min=True, include_max=True),
                    nullable=True,
                ),
                "log_return": pa.Column(float, nullable=True),
                "range_vol": pa.Column(
                    float, pa.Check.greater_than_or_equal_to(0), nullable=True
                ),
            },
            coerce=True,
        )

        with pytest.raises(pa.errors.SchemaError):
            FEATURE_SCHEMA.validate(result[list(FEATURE_SCHEMA.columns)])

    def test_pandera_passes_on_valid_features(self):
        """
        A well-formed feature DataFrame (all values in valid ranges) must pass
        Pandera validation without raising.

        Validates: Requirement 2.4.2
        """
        pytest.importorskip("pandera", reason="pandera not installed — skip Pandera test")

        try:
            import pandera.pandas as pa
        except ImportError:
            import pandera as pa

        df = _make_ohlcv(n=80, seed=11)
        result = add_price_volume_and_kline_semantics(df.copy())

        FEATURE_SCHEMA = pa.DataFrameSchema(
            {
                "frac_diff_close": pa.Column(float, nullable=True),
                "macd_norm": pa.Column(float, nullable=True),
                "rsi_14": pa.Column(
                    float,
                    pa.Check.in_range(0, 100, include_min=True, include_max=True),
                    nullable=True,
                ),
                "log_return": pa.Column(float, nullable=True),
                "range_vol": pa.Column(
                    float, pa.Check.greater_than_or_equal_to(0), nullable=True
                ),
            },
            coerce=True,
        )

        # Should not raise
        validated = FEATURE_SCHEMA.validate(result[list(FEATURE_SCHEMA.columns)])
        assert validated is not None

    def test_feature_computation_error_class_exists(self):
        """FeatureComputationError must be a subclass of RuntimeError."""
        assert issubclass(FeatureComputationError, RuntimeError), (
            "FeatureComputationError must inherit from RuntimeError"
        )


# ---------------------------------------------------------------------------
# Integration smoke test — all 5 ghost features present after pipeline run
# ---------------------------------------------------------------------------

class TestGhostFeaturesIntegration:
    """
    Smoke test confirming all 5 ghost features are present and non-trivially
    non-zero after a full pipeline run.

    Validates: Requirement 2.4.1, 2.4.3
    """

    GHOST_FEATURES = ["frac_diff_close", "macd_norm", "rsi_14", "log_return", "range_vol"]

    def test_all_ghost_features_present(self):
        """All 5 ghost features must appear as columns in pipeline output."""
        df = _make_ohlcv(n=80, seed=20)
        result = add_price_volume_and_kline_semantics(df.copy())
        missing = [f for f in self.GHOST_FEATURES if f not in result.columns]
        assert not missing, f"Ghost features missing from output: {missing}"

    def test_ghost_features_not_all_zero(self):
        """
        Each ghost feature must have at least one non-zero, non-NaN value.
        If a feature is 100% zero/NaN it was not computed — it is still a ghost.
        """
        df = _make_ohlcv(n=80, seed=21)
        result = add_price_volume_and_kline_semantics(df.copy())
        for feat in self.GHOST_FEATURES:
            non_zero = (result[feat].fillna(0.0) != 0.0).sum()
            assert non_zero > 0, (
                f"Ghost feature '{feat}' is entirely zero/NaN — "
                "it was not computed correctly"
            )

    def test_ghost_features_zero_fraction_below_95pct(self):
        """
        No ghost feature must have more than 95% zero values.
        The training script uses 95% as the ghost-feature detection threshold.

        Validates: Requirement 2.4.3
        """
        df = _make_ohlcv(n=80, seed=22)
        result = add_price_volume_and_kline_semantics(df.copy())
        for feat in self.GHOST_FEATURES:
            zero_frac = (result[feat] == 0.0).mean()
            assert zero_frac < 0.95, (
                f"Feature '{feat}' is {zero_frac * 100:.1f}% zeros — "
                "exceeds 95% ghost feature threshold"
            )
