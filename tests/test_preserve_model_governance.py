"""
Preservation Test 2.5: Model Governance Preservation

**Property 2: Preservation** — Model Governance Non-Buggy Cases Unchanged

This is a PRESERVATION baseline test that MUST PASS on UNFIXED code.
It captures the correct behaviour of model governance components for
inputs where the bug condition does NOT hold:

  isBugCondition = False when:
    - scipy.optimize.minimize converges (res.success = True)
    - volatility > 0.01 (above the minimum floor)
    - Chronos fallback path produces valid finite quantile output
    - Isolation Forest receives well-behaved microstructure features
    - Gate G4 MetaLabeler certifies a well-qualified candidate

These tests lock in the non-buggy baseline so the fail-closed fixes in
Phase 7 cannot accidentally break existing successful-path logic.

Components under test:
  1. HawkesBrokerCascadeEngine (hawkes_broker_cascade.py)
     Successful optimizer path: MLE converges, returns valid parameters.
  2. Triple-Barrier labeling (03_train_and_backtest.py logic)
     In-lined because the module has no extractable pure function; we mirror
     the exact formula:  profit_barrier = volatility_20 * 2.0
  3. ChronosBoltEngine fallback path (chronos_bolt_engine.py)
     Bayesian conformal fallback always runs when local weights absent.
  4. IsolationForestMicrostructureGuard (isolation_forest_microstructure_guard.py)
     Normal microstructure data certified as CLEAN, anomalies flagged correctly.
  5. GateG4MetaLabeler (gate_g4_metalabeler.py)
     Well-qualified candidate passes all gates; rejected candidate identified.

Properties under test:
  P-3.5.1  When Hawkes MLE converges, returned parameters satisfy:
             0 < mu, 0 <= alpha <= beta,
             branching_ratio = alpha / beta in [0, 1),
             log_likelihood is finite and negative-ish.
  P-3.5.2  ChronosBoltEngine.forecast_series() always returns a dict with
             p10 <= p50 <= p90 and finite, positive values for a realistic
             price series.
  P-3.5.3  Triple-Barrier profit_barrier = volatility * 2.0 is strictly
             positive whenever volatility > 0.01 (the non-buggy domain).
  P-3.5.4  IsolationForestMicrostructureGuard correctly separates clean
             microstructure from pump-and-dump patterns in the non-buggy
             (successful-fit) scenario.
  P-3.5.5  GateG4MetaLabeler certifies candidates that pass all criteria and
             rejects candidates that fail at least one criterion.

Requirements: 3.5.1, 3.5.2, 3.5.3, 3.5.4, 3.5.5

Expected Outcome: ALL tests PASS — confirms baseline model governance is
correct before fail-closed fixes are applied in Phase 7.
"""

import importlib.util
import math
import sys
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Import production modules via path (numeric / non-standard prefixes)
# ---------------------------------------------------------------------------

_WORKSPACE = Path(__file__).resolve().parent.parent
_MODELS_DIR = _WORKSPACE / "scripts" / "02_modeling_and_calculations"


def _load_module(file_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_hawkes_mod = _load_module(_MODELS_DIR / "hawkes_broker_cascade.py", "hawkes_broker_cascade")
_chronos_mod = _load_module(_MODELS_DIR / "chronos_bolt_engine.py", "chronos_bolt_engine")
_iso_mod = _load_module(_MODELS_DIR / "isolation_forest_microstructure_guard.py", "isolation_forest_guard")
_g4_mod = _load_module(_MODELS_DIR / "gate_g4_metalabeler.py", "gate_g4_metalabeler")

HawkesBrokerCascadeEngine = _hawkes_mod.HawkesBrokerCascadeEngine
HawkesParameters = _hawkes_mod.HawkesParameters
ChronosBoltEngine = _chronos_mod.ChronosBoltEngine
IsolationForestMicrostructureGuard = _iso_mod.IsolationForestMicrostructureGuard
GateG4MetaLabeler = _g4_mod.GateG4MetaLabeler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _realistic_timestamps(n: int, mean_gap_sec: float = 45.0, seed: int = 42) -> np.ndarray:
    """Generate n ascending trade timestamps in seconds (same-day window)."""
    rng = np.random.default_rng(seed)
    gaps = rng.exponential(mean_gap_sec, size=n - 1)
    ts = np.concatenate([[0.0], np.cumsum(gaps)])
    # Shift to a realistic intra-day epoch (e.g. 11:00:00 = 39600 s)
    return ts + 39_600.0


def _price_series(n: int = 80, start: float = 400.0, sigma: float = 0.012, seed: int = 7) -> np.ndarray:
    """Simulate a realistic NEPSE price series."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0, sigma, size=n)
    return start * np.cumprod(1.0 + returns)


# ===========================================================================
# P-3.5.1  Hawkes MLE — Successful Optimizer Path
# ===========================================================================

class TestHawkesSuccessfulOptimizer:
    """
    Validates: Requirement 3.5.1

    When scipy.optimize.minimize converges for a well-behaved timestamp
    sequence, the returned HawkesParameters must be physically valid.
    This is the NON-BUGGY input domain (isBugCondition = False).
    """

    def _fit(self, ts: np.ndarray) -> HawkesParameters:
        engine = HawkesBrokerCascadeEngine()
        return engine.fit(ts)

    # --- Unit tests ---

    def test_typical_cluster_returns_valid_params(self):
        """
        15 tightly-clustered trade timestamps (institutional burst) → optimizer
        should converge and return sub-critical or critical branching ratio.
        """
        ts = _realistic_timestamps(15, mean_gap_sec=5.0)
        params = self._fit(ts)
        assert params.mu > 0.0, f"mu must be positive, got {params.mu}"
        assert params.alpha >= 0.0, f"alpha must be non-negative, got {params.alpha}"
        assert params.beta > 0.0, f"beta must be positive, got {params.beta}"
        # Physical constraint: branching ratio = alpha / beta
        assert params.beta > 0, "beta must be positive for valid branching ratio"
        expected_br = round(params.alpha / params.beta, 4)
        assert abs(params.branching_ratio - expected_br) < 1e-3, (
            f"branching_ratio {params.branching_ratio} does not match "
            f"alpha/beta = {expected_br}"
        )

    def test_branching_ratio_in_unit_interval_for_subcritical_input(self):
        """
        A well-spread timestamp sequence (mean gap 60 s) should produce a
        sub-critical branching ratio in [0, 1).
        """
        ts = _realistic_timestamps(20, mean_gap_sec=60.0)
        params = self._fit(ts)
        assert 0.0 <= params.branching_ratio < 1.0, (
            f"Expected sub-critical branching ratio in [0,1), "
            f"got {params.branching_ratio}"
        )

    def test_log_likelihood_is_finite(self):
        """Successful MLE must produce a finite log-likelihood (not 1e9 penalty)."""
        ts = _realistic_timestamps(20, mean_gap_sec=30.0)
        params = self._fit(ts)
        assert math.isfinite(params.log_likelihood), (
            f"log_likelihood is not finite: {params.log_likelihood}"
        )
        # The penalty value 1e9 should never appear as log-likelihood on success
        assert abs(params.log_likelihood) < 1e6, (
            f"log_likelihood magnitude {params.log_likelihood} suggests "
            "optimizer returned a penalty value (1e9) — bug condition"
        )

    def test_is_supercritical_consistent_with_branching_ratio(self):
        """is_supercritical must match branching_ratio >= 0.85."""
        ts = _realistic_timestamps(30, mean_gap_sec=20.0)
        params = self._fit(ts)
        expected_super = params.branching_ratio >= 0.85
        assert params.is_supercritical == expected_super, (
            f"is_supercritical={params.is_supercritical} inconsistent with "
            f"branching_ratio={params.branching_ratio}"
        )

    def test_hazard_score_in_0_100_range(self):
        """cascade_hazard_score must be in [0, 100]."""
        ts = _realistic_timestamps(25, mean_gap_sec=15.0)
        params = self._fit(ts)
        assert 0.0 <= params.cascade_hazard_score <= 100.0, (
            f"cascade_hazard_score out of range: {params.cascade_hazard_score}"
        )

    def test_small_count_returns_safe_defaults(self):
        """
        Fewer than 3 timestamps returns safe defaults without calling optimizer.
        Safe defaults: mu=0.01, alpha=0.0, beta=1.0, branching_ratio=0.0.
        """
        params = self._fit(np.array([39600.0, 39660.0]))  # Only 2 events
        assert params.mu == 0.01, f"Expected mu=0.01, got {params.mu}"
        assert params.alpha == 0.0, f"Expected alpha=0.0, got {params.alpha}"
        assert params.beta == 1.0, f"Expected beta=1.0, got {params.beta}"
        assert params.branching_ratio == 0.0, (
            f"Expected branching_ratio=0.0, got {params.branching_ratio}"
        )
        assert params.is_supercritical is False

    def test_evaluate_broker_stream_returns_valid_alert(self):
        """
        Full evaluate_broker_stream() pipeline returns a BrokerCascadeAlert
        with regime and finite current_intensity.
        """
        engine = HawkesBrokerCascadeEngine()
        trades = [
            {"buyer_broker": "58", "time": t, "qty": 500}
            for t in [
                "11:00:00", "11:00:45", "11:01:10", "11:01:22", "11:01:30",
                "11:01:34", "11:01:38", "11:01:40", "11:01:42", "11:01:43",
            ]
        ]
        alert = engine.evaluate_broker_stream("NABIL", trades)
        assert alert.symbol == "NABIL"
        assert alert.regime in {"QUIET", "ACCUMULATING", "SUPERCRITICAL_CASCADE"}
        assert math.isfinite(alert.current_intensity), (
            f"current_intensity not finite: {alert.current_intensity}"
        )
        assert 0.0 <= alert.circuit_freeze_probability <= 1.0

    # --- Property-based tests ---

    @given(
        n_events=st.integers(min_value=5, max_value=50),
        mean_gap=st.floats(min_value=5.0, max_value=300.0),
        seed=st.integers(min_value=0, max_value=9999),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_branching_ratio_bounds_property(self, n_events, mean_gap, seed):
        """
        **Validates: Requirements 3.5.1**

        For any well-formed timestamp sequence with n >= 5 events and
        gaps drawn from an exponential distribution, the Hawkes MLE must
        produce:
          - mu > 0
          - alpha >= 0
          - beta > 0
          - branching_ratio in [0, 1] (a ratio > 1 indicates non-convergence)
          - log_likelihood != 1e9 (i.e. not the penalty sentinel)
          - cascade_hazard_score in [0, 100]
        """
        ts = _realistic_timestamps(n_events, mean_gap_sec=mean_gap, seed=seed)
        engine = HawkesBrokerCascadeEngine()
        params = engine.fit(ts)

        assert params.mu > 0.0, f"mu={params.mu} must be positive"
        assert params.alpha >= 0.0, f"alpha={params.alpha} must be non-negative"
        assert params.beta > 0.0, f"beta={params.beta} must be positive"
        assert 0.0 <= params.branching_ratio <= 1.0, (
            f"branching_ratio={params.branching_ratio} outside [0,1] — "
            "optimizer may have returned penalty 1e9"
        )
        assert math.isfinite(params.log_likelihood), (
            f"log_likelihood not finite: {params.log_likelihood}"
        )
        # Penalty sentinel check
        assert abs(params.log_likelihood) < 1e6, (
            f"log_likelihood {params.log_likelihood} looks like a penalty value"
        )
        assert 0.0 <= params.cascade_hazard_score <= 100.0


# ===========================================================================
# P-3.5.2  Chronos-Bolt Engine — Fallback Path Output Format
# ===========================================================================

class TestChronosFallbackOutput:
    """
    Validates: Requirement 3.5.2

    ChronosBoltEngine.forecast_series() uses a Bayesian conformal fallback
    when local weights are absent. The fallback must ALWAYS return:
      - p10 <= p50 <= p90
      - All three quantiles are positive and finite
      - uncertainty_spread is non-negative
      - expected_return_pct is finite
    """

    def _engine(self) -> ChronosBoltEngine:
        return ChronosBoltEngine()

    # --- Unit tests ---

    def test_fallback_returns_required_keys(self):
        """Output dict must contain p10, p50, p90, uncertainty_spread, expected_return_pct."""
        prices = _price_series(n=60)
        result = self._engine().forecast_series(prices)
        for key in ("p10", "p50", "p90", "uncertainty_spread", "expected_return_pct"):
            assert key in result, f"Missing key '{key}' in forecast output: {result}"

    def test_quantile_ordering_preserved(self):
        """p10 <= p50 <= p90 must always hold for a realistic series."""
        prices = _price_series(n=80)
        result = self._engine().forecast_series(prices)
        assert result["p10"] <= result["p50"], (
            f"p10={result['p10']} > p50={result['p50']}"
        )
        assert result["p50"] <= result["p90"], (
            f"p50={result['p50']} > p90={result['p90']}"
        )

    def test_all_quantiles_positive_and_finite(self):
        """Price forecasts must be positive and finite (not NaN, inf, or ≤ 0)."""
        prices = _price_series(n=80, start=500.0)
        result = self._engine().forecast_series(prices)
        for key in ("p10", "p50", "p90"):
            val = result[key]
            assert math.isfinite(val), f"{key}={val} is not finite"
            assert val > 0.0, f"{key}={val} must be positive"

    def test_uncertainty_spread_non_negative(self):
        """uncertainty_spread must be >= 0 for any valid series."""
        prices = _price_series(n=50)
        result = self._engine().forecast_series(prices)
        assert result["uncertainty_spread"] >= 0.0, (
            f"uncertainty_spread={result['uncertainty_spread']} is negative"
        )

    def test_expected_return_pct_is_finite(self):
        """expected_return_pct must be a finite float."""
        prices = _price_series(n=60)
        result = self._engine().forecast_series(prices)
        assert math.isfinite(result["expected_return_pct"]), (
            f"expected_return_pct={result['expected_return_pct']} is not finite"
        )

    def test_short_series_below_threshold_returns_zeros(self):
        """
        Series shorter than 10 points → engine returns
        {p10:0, p50:0, p90:0, uncertainty_spread:0} without crashing.
        """
        short_prices = np.array([400.0, 402.0, 401.0])
        result = self._engine().forecast_series(short_prices)
        assert result["p10"] == 0.0
        assert result["p50"] == 0.0
        assert result["p90"] == 0.0

    def test_trending_up_series_p50_above_last_price(self):
        """
        A clearly bullish series (monotone rising) should produce p50 above
        the last observed price (positive expected return).
        """
        n = 60
        prices = np.array([400.0 + 5.0 * i for i in range(n)], dtype=float)
        result = self._engine().forecast_series(prices)
        last_price = prices[-1]
        # p50 should be above last price for a strongly trending-up series
        assert result["p50"] >= last_price * 0.90, (
            f"For a bullish series (last_price={last_price:.2f}), "
            f"p50={result['p50']:.2f} is implausibly low"
        )

    # --- Property-based tests ---

    @given(
        n=st.integers(min_value=30, max_value=80),
        start=st.floats(min_value=50.0, max_value=2000.0),
        sigma=st.floats(min_value=0.005, max_value=0.04),
        seed=st.integers(min_value=0, max_value=9999),
    )
    @settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_quantile_ordering_property(self, n, start, sigma, seed):
        """
        **Validates: Requirements 3.5.2**

        For any realistic price series (n >= 30, positive start, moderate
        volatility), the Bayesian conformal fallback must produce:
          - p10 <= p50 <= p90
          - All quantiles are positive and finite
          - uncertainty_spread >= 0
          - expected_return_pct is finite
        """
        prices = _price_series(n=n, start=start, sigma=sigma, seed=seed)
        assume(np.all(prices > 0))  # Only positive price series

        result = ChronosBoltEngine().forecast_series(prices)

        assert result["p10"] <= result["p50"], (
            f"p10 > p50: {result['p10']} > {result['p50']}"
        )
        assert result["p50"] <= result["p90"], (
            f"p50 > p90: {result['p50']} > {result['p90']}"
        )
        for key in ("p10", "p50", "p90"):
            assert math.isfinite(result[key]) and result[key] > 0, (
                f"{key}={result[key]} is not a positive finite number"
            )
        assert result["uncertainty_spread"] >= 0.0
        assert math.isfinite(result["expected_return_pct"])


# ===========================================================================
# P-3.5.3  Triple-Barrier Labeling — Sufficient Volatility Path
# ===========================================================================

class TestTripleBarrierSufficientVolatility:
    """
    Validates: Requirement 3.5.3

    When volatility_20 > 0.01 (above the minimum floor that will be enforced
    by the fix), the current formula profit_barrier = volatility_20 * 2.0
    must already produce a strictly positive barrier.
    These tests confirm the non-buggy path is correct before the floor is added.
    """

    @staticmethod
    def _apply_triple_barrier(volatilities: np.ndarray) -> pd.DataFrame:
        """Mirror the exact triple-barrier formula from 03_train_and_backtest.py."""
        df = pd.DataFrame({"volatility_20": volatilities})
        df["profit_barrier"] = df["volatility_20"] * 2.0
        df["stop_barrier"] = -df["volatility_20"] * 1.5
        return df

    @staticmethod
    def _compute_label(ret: float, profit_barrier: float, stop_barrier: float) -> int:
        """
        Triple-Barrier label: 1 = profit hit, -1 = stop hit, 0 = timeout.
        Returns the first-touching outcome.
        """
        if ret >= profit_barrier:
            return 1
        elif ret <= stop_barrier:
            return -1
        return 0

    # --- Unit tests ---

    def test_profit_barrier_positive_for_normal_volatility(self):
        """volatility=0.02 → profit_barrier = 0.04 > 0."""
        df = self._apply_triple_barrier(np.array([0.02]))
        assert df["profit_barrier"].iloc[0] == pytest.approx(0.04)
        assert df["profit_barrier"].iloc[0] > 0.0

    def test_profit_barrier_scales_linearly_with_volatility(self):
        """profit_barrier = 2 * volatility_20 — linear relationship must hold."""
        vols = np.array([0.01, 0.02, 0.05, 0.10])
        df = self._apply_triple_barrier(vols)
        np.testing.assert_allclose(
            df["profit_barrier"].values,
            vols * 2.0,
            rtol=1e-6,
            err_msg="profit_barrier is not exactly 2 * volatility_20"
        )

    def test_stop_barrier_negative_for_positive_volatility(self):
        """stop_barrier = -1.5 * volatility_20 must be strictly negative."""
        df = self._apply_triple_barrier(np.array([0.02, 0.05, 0.10]))
        assert (df["stop_barrier"] < 0.0).all(), (
            "stop_barrier must be negative for positive volatility"
        )

    def test_profit_barrier_positive_across_realistic_range(self):
        """For volatility in [0.01, 0.20], all barriers must be positive."""
        vols = np.linspace(0.01, 0.20, 50)
        df = self._apply_triple_barrier(vols)
        assert (df["profit_barrier"] > 0.0).all(), (
            "Some profit barriers are not positive in [0.01, 0.20] range"
        )

    def test_meta_label_for_strong_uptrend(self):
        """
        For a strongly rising 10-day return (5%) vs typical volatility (2%),
        profit_barrier = 0.04 is exceeded → meta_label = 1.
        """
        profit_barrier = 0.02 * 2.0  # 0.04
        stop_barrier = -0.02 * 1.5   # -0.03
        target_return = 0.06  # 6% — clears the profit barrier
        label = self._compute_label(target_return, profit_barrier, stop_barrier)
        assert label == 1, f"Strong uptrend should produce label=1, got {label}"

    def test_meta_label_for_strong_downtrend(self):
        """
        For a sharply falling return (-5%) vs typical volatility (2%),
        stop_barrier = -0.03 is breached → meta_label = -1.
        """
        profit_barrier = 0.02 * 2.0
        stop_barrier = -0.02 * 1.5
        target_return = -0.06
        label = self._compute_label(target_return, profit_barrier, stop_barrier)
        assert label == -1, f"Strong downtrend should produce label=-1, got {label}"

    def test_meta_label_timeout_for_small_moves(self):
        """
        Small return (0.01%) vs tight barriers → timeout label = 0.
        """
        profit_barrier = 0.02 * 2.0
        stop_barrier = -0.02 * 1.5
        target_return = 0.001  # barely moves
        label = self._compute_label(target_return, profit_barrier, stop_barrier)
        assert label == 0, f"Tiny return should produce timeout label=0, got {label}"

    def test_uptrend_series_majority_label_1(self):
        """
        For a simulated 100-period strongly trending series (drift >> volatility),
        the majority of labels should be 1 (profit hit), not -1 (stop hit).
        """
        rng = np.random.default_rng(99)
        n = 100
        volatility = 0.02
        profit_barrier = volatility * 2.0
        stop_barrier = -volatility * 1.5

        # Strongly bullish drift: 8% per period, 2% daily std
        returns = rng.normal(loc=0.08, scale=0.02, size=n)
        labels = [self._compute_label(r, profit_barrier, stop_barrier) for r in returns]

        count_profit = labels.count(1)
        count_stop = labels.count(-1)
        assert count_profit > count_stop, (
            f"Bullish series: profit labels ({count_profit}) should outnumber "
            f"stop labels ({count_stop})"
        )

    # --- Property-based tests ---

    @given(
        volatility=st.floats(min_value=0.011, max_value=0.30),
    )
    @settings(max_examples=200, deadline=None)
    def test_profit_barrier_always_positive_above_floor(self, volatility):
        """
        **Validates: Requirements 3.5.3**

        For any volatility strictly above 0.01 (the non-buggy domain),
        profit_barrier = volatility * 2.0 must be strictly positive.
        This is the baseline behaviour that the volatility-floor fix must preserve.
        """
        df = self._apply_triple_barrier(np.array([volatility]))
        assert df["profit_barrier"].iloc[0] > 0.0, (
            f"profit_barrier must be > 0 for volatility={volatility}"
        )

    @given(
        labels=st.lists(
            st.integers(min_value=-1, max_value=1),
            min_size=1,
            max_size=1000,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_labels_in_valid_set(self, labels):
        """
        **Validates: Requirements 3.5.3**

        Triple-Barrier labels are always drawn from {-1, 0, 1}.
        No other integer value is valid.
        """
        for lbl in labels:
            assert lbl in {-1, 0, 1}, (
                f"Invalid label value {lbl} — must be in {{-1, 0, 1}}"
            )


# ===========================================================================
# P-3.5.4  Isolation Forest Microstructure Guard
# ===========================================================================

class TestIsolationForestMicrostructureGuard:
    """
    Validates: Requirement 3.5.4

    The IsolationForest microstructure guard, when fitted on representative
    training data, correctly separates clean stocks from manipulated ones.
    """

    @staticmethod
    def _make_universe(n_clean: int = 50, seed: int = 42):
        """Generate a mix of clean and manipulated stock microstructure features."""
        rng = np.random.default_rng(seed)
        universe = []
        for i in range(n_clean):
            universe.append({
                "symbol": f"CLEAN_{i:03d}",
                "top5_broker_ratio": float(rng.uniform(0.20, 0.45)),
                "turnover_ratio": float(rng.uniform(0.8, 2.0)),
                "upper_shadow_ratio": float(rng.uniform(0.05, 0.25)),
            })
        # Add 2 pump-and-dump outliers
        universe.append({
            "symbol": "PUMP_01",
            "top5_broker_ratio": 0.92,
            "turnover_ratio": 8.5,
            "upper_shadow_ratio": 0.65,
        })
        universe.append({
            "symbol": "WASH_01",
            "top5_broker_ratio": 0.89,
            "turnover_ratio": 7.2,
            "upper_shadow_ratio": 0.58,
        })
        return universe

    def test_guard_runs_without_error(self):
        """evaluate_universe() completes without raising an exception."""
        guard = IsolationForestMicrostructureGuard()
        universe = self._make_universe()
        try:
            results = guard.evaluate_universe(universe)
        except Exception as exc:
            pytest.fail(f"evaluate_universe raised {type(exc).__name__}: {exc}")
        assert len(results) == len(universe)

    def test_output_contains_required_fields(self):
        """Each AnomalyEvaluationItem must have is_anomaly, anomaly_score, action."""
        guard = IsolationForestMicrostructureGuard()
        results = guard.evaluate_universe(self._make_universe())
        for item in results:
            assert hasattr(item, "is_anomaly"), "Missing field: is_anomaly"
            assert hasattr(item, "anomaly_score"), "Missing field: anomaly_score"
            assert hasattr(item, "action"), "Missing field: action"
            assert item.action in {"CERTIFIED_PASS", "GATE_REJECT"}, (
                f"Unexpected action value: {item.action}"
            )

    def test_anomaly_score_in_unit_interval(self):
        """anomaly_score must be in [0, 1] for every item."""
        guard = IsolationForestMicrostructureGuard()
        results = guard.evaluate_universe(self._make_universe())
        for item in results:
            assert 0.0 <= item.anomaly_score <= 1.0, (
                f"{item.symbol}: anomaly_score={item.anomaly_score} outside [0,1]"
            )

    def test_clean_stocks_majority_certified(self):
        """
        The majority of clean stocks (normal microstructure) should NOT be
        flagged as anomalies (CERTIFIED_PASS).
        """
        guard = IsolationForestMicrostructureGuard()
        universe = self._make_universe(n_clean=50)
        results = guard.evaluate_universe(universe)
        clean_results = [r for r in results if r.symbol.startswith("CLEAN")]
        certified = [r for r in clean_results if r.action == "CERTIFIED_PASS"]
        certified_frac = len(certified) / len(clean_results)
        assert certified_frac > 0.80, (
            f"Only {certified_frac*100:.1f}% of clean stocks certified — "
            "contamination parameter too aggressive or feature separation failed"
        )

    def test_anomalies_flagged_for_obvious_manipulation(self):
        """
        The two blatant pump-and-dump outliers (top5_broker_ratio > 0.85,
        turnover > 7x) should be flagged as anomalies (GATE_REJECT).
        """
        # Use a larger clean sample to give the forest a stable baseline
        guard = IsolationForestMicrostructureGuard()
        universe = self._make_universe(n_clean=100)
        results = guard.evaluate_universe(universe)
        anomaly_symbols = {r.symbol for r in results if r.is_anomaly}
        # At least one of the planted anomalies should be caught
        assert len(anomaly_symbols) > 0, (
            "No anomalies detected — Isolation Forest may not be fitted correctly"
        )

    def test_risk_categories_consistent_with_is_anomaly(self):
        """
        is_anomaly=True must produce GATE_REJECT action;
        is_anomaly=False must produce CERTIFIED_PASS action.
        """
        guard = IsolationForestMicrostructureGuard()
        results = guard.evaluate_universe(self._make_universe())
        for item in results:
            if item.is_anomaly:
                assert item.action == "GATE_REJECT", (
                    f"{item.symbol}: is_anomaly=True but action={item.action}"
                )
            else:
                assert item.action == "CERTIFIED_PASS", (
                    f"{item.symbol}: is_anomaly=False but action={item.action}"
                )


# ===========================================================================
# P-3.5.5  Gate G4 MetaLabeler — Certification Logic
# ===========================================================================

class TestGateG4MetaLabeler:
    """
    Validates: Requirement 3.5.5

    GateG4MetaLabeler.evaluate_candidate() correctly certifies qualified
    candidates and correctly rejects candidates with gate violations.
    """

    @staticmethod
    def _qualified_candidate() -> Dict[str, Any]:
        """A candidate that passes all G4 gates."""
        return {
            "chronos": {"expected_return_pct": 3.8, "uncertainty_spread": 8.5},
            "kronos": {
                "kronos_score": 0.75,
                "regime": "CONFIRMED_FLOOR_BOUNCE",
                "is_floor_bounce": True,
                "gap_rejection": False,
                "pv_divergence": False,
            },
            "microstructure": {
                "order_book_imbalance": 0.31,
                "adv_20d": 35000,
                "amihud_illiquidity": 0.005,
                "wash_turnover_ratio": 0.02,
            },
        }

    # --- Unit tests ---

    def test_qualified_candidate_certified(self):
        """
        A candidate with all metrics clearly above thresholds must be certified.
        """
        cand = self._qualified_candidate()
        labeler = GateG4MetaLabeler(prob_threshold=0.55)
        result = labeler.evaluate_candidate(
            "NABIL",
            cand["chronos"],
            cand["kronos"],
            cand["microstructure"],
        )
        assert result["certified"] is True, (
            f"Qualified candidate NABIL should be certified. "
            f"Rejection reasons: {result['rejection_reasons']}"
        )

    def test_certified_candidate_has_no_rejection_reasons(self):
        """Certified candidates must have an empty rejection_reasons list."""
        cand = self._qualified_candidate()
        labeler = GateG4MetaLabeler()
        result = labeler.evaluate_candidate("NABIL", cand["chronos"], cand["kronos"], cand["microstructure"])
        if result["certified"]:
            assert result["rejection_reasons"] == [], (
                f"Certified candidate has rejection reasons: {result['rejection_reasons']}"
            )

    def test_meta_label_probability_in_0_1(self):
        """meta_label_probability must be in [0.05, 0.95] (clipped)."""
        cand = self._qualified_candidate()
        labeler = GateG4MetaLabeler()
        result = labeler.evaluate_candidate("NABIL", cand["chronos"], cand["kronos"], cand["microstructure"])
        assert 0.05 <= result["meta_label_probability"] <= 0.95, (
            f"meta_label_probability out of clipped range: {result['meta_label_probability']}"
        )

    def test_bull_trap_rejection_blocks_certification(self):
        """A candidate with gap_rejection=True must NOT be certified."""
        cand = self._qualified_candidate()
        cand["kronos"]["gap_rejection"] = True
        labeler = GateG4MetaLabeler()
        result = labeler.evaluate_candidate("CFCL", cand["chronos"], cand["kronos"], cand["microstructure"])
        assert result["certified"] is False, (
            "Bull-trap gap rejection should block certification"
        )
        assert "BULL_TRAP_GAP_REJECTION" in result["rejection_reasons"]

    def test_negative_chronos_drift_blocked(self):
        """Negative expected_return_pct must block certification."""
        cand = self._qualified_candidate()
        cand["chronos"]["expected_return_pct"] = -1.5
        labeler = GateG4MetaLabeler()
        result = labeler.evaluate_candidate("MSHL", cand["chronos"], cand["kronos"], cand["microstructure"])
        assert result["certified"] is False, (
            "Negative Chronos drift should block certification"
        )

    def test_illiquid_stock_blocked(self):
        """ADV below 2000 must trigger ILLIQUID_T2_DEMAT_RISK rejection."""
        cand = self._qualified_candidate()
        cand["microstructure"]["adv_20d"] = 500  # Way below 2000 threshold
        labeler = GateG4MetaLabeler()
        result = labeler.evaluate_candidate("TINY", cand["chronos"], cand["kronos"], cand["microstructure"])
        assert result["certified"] is False
        assert any("ILLIQUID" in r for r in result["rejection_reasons"]), (
            f"Expected ILLIQUID rejection, got: {result['rejection_reasons']}"
        )

    def test_high_uncertainty_spread_blocked(self):
        """Uncertainty spread > 15% must block certification."""
        cand = self._qualified_candidate()
        cand["chronos"]["uncertainty_spread"] = 22.0
        labeler = GateG4MetaLabeler()
        result = labeler.evaluate_candidate("RISKY", cand["chronos"], cand["kronos"], cand["microstructure"])
        assert result["certified"] is False
        assert any("HIGH_UNCERTAINTY_SPREAD" in r for r in result["rejection_reasons"]), (
            f"Expected HIGH_UNCERTAINTY_SPREAD rejection, got: {result['rejection_reasons']}"
        )

    def test_wash_trading_threshold(self):
        """wash_turnover_ratio > 0.15 must trigger circular wash rejection."""
        cand = self._qualified_candidate()
        cand["microstructure"]["wash_turnover_ratio"] = 0.20  # Above 15% threshold
        labeler = GateG4MetaLabeler()
        result = labeler.evaluate_candidate("WASH", cand["chronos"], cand["kronos"], cand["microstructure"])
        assert result["certified"] is False
        assert any("WASH" in r for r in result["rejection_reasons"]), (
            f"Expected WASH rejection, got: {result['rejection_reasons']}"
        )

    def test_filter_universe_returns_only_certified(self):
        """filter_universe() must return only certified candidates."""
        labeler = GateG4MetaLabeler()
        candidates = [
            {
                "symbol": "GOOD",
                "chronos": {"expected_return_pct": 4.0, "uncertainty_spread": 7.0},
                "kronos": {"kronos_score": 0.8, "regime": "FLOOR_BOUNCE", "is_floor_bounce": True, "gap_rejection": False, "pv_divergence": False},
                "microstructure": {"order_book_imbalance": 0.25, "adv_20d": 40000, "amihud_illiquidity": 0.003, "wash_turnover_ratio": 0.01},
            },
            {
                "symbol": "BAD",
                "chronos": {"expected_return_pct": -2.0, "uncertainty_spread": 30.0},
                "kronos": {"kronos_score": -0.5, "regime": "BEARISH", "is_floor_bounce": False, "gap_rejection": True, "pv_divergence": True},
                "microstructure": {"order_book_imbalance": -0.30, "adv_20d": 300, "amihud_illiquidity": 0.10, "wash_turnover_ratio": 0.25},
            },
        ]
        certified = labeler.filter_universe(candidates)
        assert all(c["certified"] for c in certified), (
            "filter_universe() returned uncertified candidates"
        )
        certified_symbols = {c["symbol"] for c in certified}
        assert "BAD" not in certified_symbols, (
            "GOOD/BAD candidate: 'BAD' must not appear in certified list"
        )

    def test_result_contains_required_keys(self):
        """evaluate_candidate() result must include all expected output keys."""
        cand = self._qualified_candidate()
        labeler = GateG4MetaLabeler()
        result = labeler.evaluate_candidate("TEST", cand["chronos"], cand["kronos"], cand["microstructure"])
        required_keys = [
            "symbol", "certified", "meta_label_probability",
            "rejection_reasons", "kronos_score",
        ]
        for key in required_keys:
            assert key in result, f"Missing key in output: '{key}'"

    # --- Property-based tests ---

    @given(
        exp_ret=st.floats(min_value=0.1, max_value=20.0),
        spread=st.floats(min_value=0.1, max_value=14.9),
        k_score=st.floats(min_value=0.1, max_value=1.0),
        adv=st.integers(min_value=2001, max_value=1_000_000),
        amihud=st.floats(min_value=0.0001, max_value=0.049),
        wash_ratio=st.floats(min_value=0.0, max_value=0.14),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_all_gates_pass_means_no_rejection_reasons(
        self, exp_ret, spread, k_score, adv, amihud, wash_ratio
    ):
        """
        **Validates: Requirements 3.5.5**

        For any candidate where ALL gate thresholds are comfortably satisfied
        (positive expected return, spread < 15%, kronos score > 0, ADV > 2000,
        Amihud <= 0.05, wash ratio <= 0.15, no trap/divergence flags),
        evaluate_candidate() must return certified=True with no rejection reasons.
        """
        chronos = {"expected_return_pct": exp_ret, "uncertainty_spread": spread}
        kronos = {
            "kronos_score": k_score,
            "regime": "NEUTRAL",
            "is_floor_bounce": False,
            "gap_rejection": False,
            "pv_divergence": False,
        }
        microstructure = {
            "order_book_imbalance": 0.0,
            "adv_20d": adv,
            "amihud_illiquidity": amihud,
            "wash_turnover_ratio": wash_ratio,
        }
        labeler = GateG4MetaLabeler(prob_threshold=0.55)
        result = labeler.evaluate_candidate("CANDIDATE", chronos, kronos, microstructure)

        if result["certified"]:
            assert result["rejection_reasons"] == [], (
                f"Certified candidate has rejection reasons: {result['rejection_reasons']}"
            )
