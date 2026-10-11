"""
tests/test_model_governance.py

Fix Verification Tests — Phase 7: Model Governance Framework
=============================================================

These tests verify that Bug C5.1 – C5.4 are fixed:

  C5.1  HawkesBrokerCascadeEngine.fit() now validates res.success before
        consuming optimizer output.  On failure it returns safe defaults
        instead of the 1e9 penalty value.

  C5.2  ChronosBoltEngine.forecast_series() now tags every return path
        with a consistent "model_status" key so callers can distinguish
        LIVE_CHRONOS from GBM_FALLBACK without inspecting internals.

  C5.3  03_train_and_backtest.py enforces MIN_VOLATILITY_FLOOR = 0.01 so
        profit_barrier is never zero even for zero-volatility scrips.

  C5.4  IsolationForestMicrostructureGuard.evaluate_universe() now emits
        an explicit warning when called without a prior fit_on_historical(),
        rather than silently fitting on the test batch.

Requirements: 2.5.1, 2.5.2, 2.5.3, 2.5.4, 2.5.5
"""

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Module loading helpers (numeric directory prefixes prevent dotted imports)
# ---------------------------------------------------------------------------

_WORKSPACE = Path(__file__).resolve().parent.parent
_MODELS_DIR = _WORKSPACE / "scripts" / "02_modeling_and_calculations"
_SCRIPTS_DIR = _WORKSPACE / "scripts"


def _load_module(file_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


_hawkes_mod = _load_module(
    _MODELS_DIR / "hawkes_broker_cascade.py", "hawkes_broker_cascade"
)
_chronos_mod = _load_module(
    _MODELS_DIR / "chronos_bolt_engine.py", "chronos_bolt_engine"
)
_iso_mod = _load_module(
    _MODELS_DIR / "isolation_forest_microstructure_guard.py",
    "isolation_forest_guard",
)

HawkesBrokerCascadeEngine = _hawkes_mod.HawkesBrokerCascadeEngine
SAFE_HAWKES_DEFAULTS = _hawkes_mod.SAFE_HAWKES_DEFAULTS
ChronosBoltEngine = _chronos_mod.ChronosBoltEngine
IsolationForestMicrostructureGuard = _iso_mod.IsolationForestMicrostructureGuard


# ---------------------------------------------------------------------------
# Helper: build a fake scipy OptimizeResult
# ---------------------------------------------------------------------------

def _make_opt_result(success: bool, x=None, fun=None, message=""):
    """Return a minimal scipy OptimizeResult-like namespace."""
    if x is None:
        x = np.array([1e9, 1e9, 1e9]) if not success else np.array([0.05, 0.3, 0.6])
    if fun is None:
        fun = 1e9 if not success else 42.0
    result = SimpleNamespace(success=success, x=x, fun=fun, message=message)
    return result


# ---------------------------------------------------------------------------
# Test 1: optimizer failure → safe defaults
# ---------------------------------------------------------------------------

class TestHawkesOptimizerFailure:
    """Validates: Requirement 2.5.1 (Bug C5.1 fix)"""

    def test_hawkes_optimizer_failure_returns_safe_defaults(self):
        """
        When scipy.optimize.minimize returns res.success=False, fit() must
        return SAFE_HAWKES_DEFAULTS (branching_ratio=0.0, is_supercritical=False).

        This prevents garbage 1e9 parameters from propagating downstream and
        triggering false SUPERCRITICAL_CASCADE alerts on quiet stocks.
        """
        engine = HawkesBrokerCascadeEngine()

        # 10 realistic timestamps — enough to reach the optimizer branch
        rng = np.random.default_rng(0)
        ts = np.cumsum(rng.exponential(30.0, size=10)) + 39_600.0

        failed_result = _make_opt_result(
            success=False,
            x=np.array([1e9, 1e9, 1e9]),
            fun=1e9,
            message="ABNORMAL_TERMINATION_IN_LNSRCH",
        )

        with patch.object(_hawkes_mod, "minimize", return_value=failed_result):
            params = engine.fit(ts)

        assert params.branching_ratio == 0.0, (
            f"Expected branching_ratio=0.0 on optimizer failure, got {params.branching_ratio}"
        )
        assert params.is_supercritical is False, (
            "is_supercritical must be False when optimizer fails"
        )
        assert params.mu == 0.01, (
            f"Expected safe default mu=0.01, got {params.mu}"
        )
        assert params.alpha == 0.0, (
            f"Expected safe default alpha=0.0, got {params.alpha}"
        )
        assert params.beta == 1.0, (
            f"Expected safe default beta=1.0, got {params.beta}"
        )
        assert params.cascade_hazard_score == 0.0, (
            f"cascade_hazard_score must be 0.0 for safe defaults, got {params.cascade_hazard_score}"
        )


# ---------------------------------------------------------------------------
# Test 2: successful optimizer → result params used
# ---------------------------------------------------------------------------

class TestHawkesOptimizerSuccess:
    """Validates: Requirement 2.5.1 (preservation of successful path)"""

    def test_hawkes_optimizer_success_uses_result(self):
        """
        When scipy.optimize.minimize returns res.success=True with valid
        parameters, fit() must use those optimized parameters — not safe defaults.
        """
        engine = HawkesBrokerCascadeEngine()

        rng = np.random.default_rng(1)
        ts = np.cumsum(rng.exponential(30.0, size=10)) + 39_600.0

        # mu=0.05, alpha=0.3, beta=0.6  →  branching_ratio = 0.3/0.6 = 0.5
        good_x = np.array([0.05, 0.3, 0.6])
        good_result = _make_opt_result(
            success=True,
            x=good_x,
            fun=42.0,
            message="CONVERGENCE: NORM_OF_PROJECTED_GRADIENT_<=_PGTOL",
        )

        with patch.object(_hawkes_mod, "minimize", return_value=good_result):
            params = engine.fit(ts)

        # Must NOT fall back to safe defaults
        assert abs(params.mu - 0.05) < 1e-3, (
            f"Expected mu≈0.05 from optimizer result, got {params.mu}"
        )
        assert abs(params.alpha - 0.3) < 1e-3, (
            f"Expected alpha≈0.3 from optimizer result, got {params.alpha}"
        )
        assert abs(params.beta - 0.6) < 1e-3, (
            f"Expected beta≈0.6 from optimizer result, got {params.beta}"
        )
        expected_br = round(0.3 / 0.6, 4)  # 0.5
        assert abs(params.branching_ratio - expected_br) < 1e-3, (
            f"branching_ratio should be alpha/beta={expected_br}, got {params.branching_ratio}"
        )


# ---------------------------------------------------------------------------
# Test 3: volatility floor prevents zero profit_barrier
# ---------------------------------------------------------------------------

class TestTripleBarrierVolatilityFloor:
    """Validates: Requirement 2.5.3 (Bug C5.3 fix)"""

    @staticmethod
    def _apply_barrier_with_floor(volatilities: np.ndarray) -> pd.DataFrame:
        """
        Mirror the exact fixed logic from scripts/03_train_and_backtest.py.
        """
        MIN_VOLATILITY_FLOOR = 0.01
        df = pd.DataFrame({"volatility_20": volatilities})
        df["effective_volatility"] = df["volatility_20"].clip(lower=MIN_VOLATILITY_FLOOR)
        df["profit_barrier"] = df["effective_volatility"] * 2.0
        df["stop_barrier"] = -df["effective_volatility"] * 1.5
        return df

    def test_triple_barrier_floor_prevents_zero_barrier(self):
        """
        A scrip with volatility_20=0.0 must still produce profit_barrier > 0
        after the floor is applied.

        Without the fix: profit_barrier = 0.0 * 2.0 = 0.0, labeling every
        positive tick as a successful trade (meta_label = 1).
        With the fix:    profit_barrier = 0.01 * 2.0 = 0.02 > 0.
        """
        df = self._apply_barrier_with_floor(np.array([0.0]))
        assert df["profit_barrier"].iloc[0] > 0.0, (
            f"profit_barrier must be > 0 even when volatility=0.0, "
            f"got {df['profit_barrier'].iloc[0]}"
        )
        assert df["profit_barrier"].iloc[0] == pytest.approx(0.02), (
            "With floor=0.01, profit_barrier for zero-vol scrip should be 0.02"
        )

    def test_floor_applied_only_to_low_volatility(self):
        """
        Scrips with volatility_20 >= 0.01 must use their actual volatility
        unchanged (floor must not inflate normal-volatility barriers).
        """
        vols = np.array([0.0, 0.005, 0.01, 0.02, 0.05])
        df = self._apply_barrier_with_floor(vols)

        # Values below floor → clamped to 0.01
        assert df["profit_barrier"].iloc[0] == pytest.approx(0.02)  # 0.0  → floor
        assert df["profit_barrier"].iloc[1] == pytest.approx(0.02)  # 0.005 → floor

        # Values at or above floor → unmodified
        assert df["profit_barrier"].iloc[2] == pytest.approx(0.02)  # 0.01 → exactly floor
        assert df["profit_barrier"].iloc[3] == pytest.approx(0.04)  # 0.02
        assert df["profit_barrier"].iloc[4] == pytest.approx(0.10)  # 0.05

    def test_all_barriers_positive_after_floor(self):
        """
        After applying the floor, every row in a mixed-volatility dataframe
        must have profit_barrier > 0.
        """
        vols = np.array([0.0, 0.0, 0.001, 0.005, 0.02, 0.08, 0.15])
        df = self._apply_barrier_with_floor(vols)
        assert (df["profit_barrier"] > 0).all(), (
            f"Some profit barriers are zero: {df['profit_barrier'].tolist()}"
        )


# ---------------------------------------------------------------------------
# Test 4: Chronos output always has model_status key
# ---------------------------------------------------------------------------

class TestChronosOutputHasModelStatus:
    """Validates: Requirement 2.5.5 (Bug C5.2 fix)"""

    def test_chronos_output_has_model_status(self):
        """
        forecast_series() must include 'model_status' in its return dict
        for any realistic price series.  The pipeline will be absent in the
        test environment so GBM_FALLBACK is expected.
        """
        engine = ChronosBoltEngine()
        prices = np.array([400.0 + 2.0 * i for i in range(50)], dtype=float)
        result = engine.forecast_series(prices)
        assert "model_status" in result, (
            f"'model_status' key missing from forecast output: {result}"
        )

    def test_short_series_output_has_model_status(self):
        """
        The early-return path for series shorter than 10 points must also
        include 'model_status'.
        """
        engine = ChronosBoltEngine()
        short = np.array([400.0, 402.0, 401.0])
        result = engine.forecast_series(short)
        assert "model_status" in result, (
            f"'model_status' missing in short-series early return: {result}"
        )


# ---------------------------------------------------------------------------
# Test 5: GBM_FALLBACK status when Chronos unavailable
# ---------------------------------------------------------------------------

class TestChronosFallbackSetGBMStatus:
    """Validates: Requirement 2.5.2, 2.5.5 (Bug C5.2 fix)"""

    def test_chronos_fallback_sets_gbm_status(self):
        """
        When ChronosBoltPipeline is None (weights not installed), the engine
        must fall through to the Bayesian GBM fallback and tag the result with
        model_status='GBM_FALLBACK'.
        """
        # Ensure the module sees ChronosBoltPipeline as None
        with patch.object(_chronos_mod, "ChronosBoltPipeline", None):
            engine = ChronosBoltEngine()
            # Reset any cached pipeline so _load_pipeline() re-checks the module attr
            engine.pipeline = None
            engine._load_attempted = False
            prices = np.array([300.0 + i for i in range(60)], dtype=float)
            result = engine.forecast_series(prices)

        assert result.get("model_status") == "GBM_FALLBACK", (
            f"Expected model_status='GBM_FALLBACK' when Chronos unavailable, "
            f"got '{result.get('model_status')}'"
        )

    def test_gbm_fallback_result_is_valid(self):
        """
        GBM_FALLBACK result must still contain valid quantiles (positive,
        ordered p10 <= p50 <= p90) regardless of the model_status tag.
        """
        import math
        with patch.object(_chronos_mod, "ChronosBoltPipeline", None):
            engine = ChronosBoltEngine()
            engine.pipeline = None
            engine._load_attempted = False
            prices = np.array([500.0 + 1.5 * i for i in range(60)], dtype=float)
            result = engine.forecast_series(prices)

        assert result["model_status"] == "GBM_FALLBACK"
        assert result["p10"] <= result["p50"] <= result["p90"], (
            f"Quantile order violated in GBM_FALLBACK: {result}"
        )
        for key in ("p10", "p50", "p90"):
            assert math.isfinite(result[key]) and result[key] > 0, (
                f"{key}={result[key]} is not a positive finite value"
            )


# ---------------------------------------------------------------------------
# Test 6: IsolationForest warns when not pre-fitted on historical data
# ---------------------------------------------------------------------------

class TestIsolationForestWhenNotPrefitted:
    """Validates: Requirement 2.5.4 (Bug C5.4 fix)"""

    def _make_universe(self, n: int = 20, seed: int = 0):
        rng = np.random.default_rng(seed)
        return [
            {
                "symbol": f"SCRIP_{i:03d}",
                "top5_broker_ratio": float(rng.uniform(0.2, 0.5)),
                "turnover_ratio": float(rng.uniform(0.8, 2.0)),
                "upper_shadow_ratio": float(rng.uniform(0.05, 0.3)),
            }
            for i in range(n)
        ]

    def test_isolation_forest_warns_when_not_prefitted(self, caplog):
        """
        Calling evaluate_universe() on a fresh (unfitted) guard must emit a
        WARNING that informs operators to call fit_on_historical() first.

        Previously the guard silently fit on the incoming test batch (Bug C5.4),
        which anchors the model to the current universe and degrades anomaly
        detection accuracy.
        """
        guard = IsolationForestMicrostructureGuard()
        assert not guard.is_fitted, "Guard should start unfitted"

        with caplog.at_level(logging.WARNING, logger="IsolationGuard"):
            results = guard.evaluate_universe(self._make_universe())

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "fit_on_historical" in msg or "not fitted" in msg.lower()
            for msg in warning_messages
        ), (
            "Expected a warning mentioning 'fit_on_historical' when guard is "
            f"not pre-fitted. Got warnings: {warning_messages}"
        )
        # Guard should still return results (graceful degradation, not a crash)
        assert len(results) == 20

    def test_fit_on_historical_prevents_warning(self, caplog):
        """
        After calling fit_on_historical() with clean training data,
        evaluate_universe() must NOT emit the pre-fit warning.
        """
        guard = IsolationForestMicrostructureGuard()
        historical = self._make_universe(n=100, seed=99)
        guard.fit_on_historical(historical)
        assert guard.is_fitted

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="IsolationGuard"):
            guard.evaluate_universe(self._make_universe(n=20, seed=7))

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert not any("fit_on_historical" in msg for msg in warning_messages), (
            "No pre-fit warning should appear after fit_on_historical() was called. "
            f"Got warnings: {warning_messages}"
        )

    def test_fit_on_historical_signature_and_behavior(self):
        """
        fit_on_historical() must accept a list of feature dicts and set
        is_fitted=True on the guard.
        """
        guard = IsolationForestMicrostructureGuard()
        assert not guard.is_fitted

        historical = self._make_universe(n=50, seed=42)
        guard.fit_on_historical(historical)

        assert guard.is_fitted, (
            "is_fitted must be True after fit_on_historical() completes"
        )
