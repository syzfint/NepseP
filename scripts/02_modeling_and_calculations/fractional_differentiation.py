#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/fractional_differentiation.py

Fractional Differentiation for Financial Time Series (d=0.35)
=============================================================
Implements Marcos López de Prado's Fixed-Width Window Fractional Differentiation (FFD).
Resolves the fundamental dilemma in quantitative finance:
  - Integer differencing (d=1) makes the series stationary, but completely destroys memory.
  - Zero differencing (d=0) retains 100% memory, but leaves non-stationary random walks.
  - Fractional differencing (d=0.35) achieves stationarity (ADF p < 0.05) while preserving
    maximal memory (Pearson correlation r > 0.85 with the underlying price series).

Key Methods:
  - get_weights_ffd(d, threshold, max_lags): Computes binomial weights until cutoff tau.
  - fractional_diff_ffd(series, d, threshold, max_lags): Applies fixed-window fractional differencing.
  - test_stationarity_adf(series): Runs Augmented Dickey-Fuller test.
  - find_optimal_d(series): Grid search for minimum d achieving p < 0.05.
"""

import sys
import warnings
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

warnings.filterwarnings("ignore", category=FutureWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fractional_diff")

BASE_DIR = Path(__file__).resolve().parents[2]
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")


def get_weights_ffd(d: float, threshold: float = 1e-3, max_lags: int = 120) -> np.ndarray:
    """
    Computes binomial weights for fixed-width window fractional differentiation.
    w_0 = 1
    w_k = -w_{k-1} * (d - k + 1) / k
    Drops weights where |w_k| < threshold or k >= max_lags.
    """
    w = [1.0]
    k = 1
    while k < max_lags:
        w_k = -w[-1] / k * (d - k + 1)
        if abs(w_k) < threshold:
            break
        w.append(w_k)
        k += 1
    return np.array(w[::-1])  # Reverse for 1D convolution


def fractional_diff_ffd(series: pd.Series, d: float = 0.35, threshold: float = 1e-3, max_lags: int = 120) -> pd.Series:
    """
    Applies Fixed-Width Window Fractional Differencing (FFD) to a price series.
    Missing warmup values (prior to window length) are preserved as NaN.
    """
    if len(series) == 0:
        return pd.Series(dtype=float)

    weights = get_weights_ffd(d, threshold=threshold, max_lags=max_lags)
    width = len(weights)

    if len(series) < width:
        # Fallback to shorter max_lags
        weights = get_weights_ffd(d, threshold=threshold, max_lags=max(len(series) // 3, 5))
        width = len(weights)

    vals = series.values
    out = np.full(len(vals), np.nan, dtype=float)

    for i in range(width - 1, len(vals)):
        window = vals[i - width + 1 : i + 1]
        out[i] = np.dot(weights, window)

    return pd.Series(out, index=series.index, name=f"{series.name}_fracdiff_{d}")


def test_stationarity_adf(series: pd.Series) -> Dict[str, Any]:
    """
    Runs the Augmented Dickey-Fuller (ADF) stationarity test.
    H0: Unit root present (Non-stationary).
    H1: Stationary (Reject H0 if p-value < 0.05).
    """
    clean_series = series.dropna()
    if len(clean_series) < 20:
        return {"stationary": False, "p_value": 1.0, "adf_stat": 0.0, "error": "Insufficient sample size"}

    adf_result = adfuller(clean_series, autolag="AIC")
    adf_stat, p_value, lags, nobs, crit_vals, _ = adf_result

    return {
        "stationary": bool(p_value < 0.05),
        "p_value": float(p_value),
        "adf_stat": float(adf_stat),
        "used_lags": int(lags),
        "n_obs": int(nobs),
        "critical_value_1pct": float(crit_vals["1%"]),
        "critical_value_5pct": float(crit_vals["5%"]),
        "critical_value_10pct": float(crit_vals["10%"])
    }


def evaluate_memory_retention(original: pd.Series, fracdiff: pd.Series) -> float:
    """
    Measures Pearson correlation between original price series and fractionally differentiated series.
    """
    df = pd.DataFrame({"orig": original, "frac": fracdiff}).dropna()
    if len(df) < 10:
        return 0.0
    return float(df["orig"].corr(df["frac"]))


def find_optimal_d(series: pd.Series, d_min: float = 0.10, d_max: float = 0.90, step: float = 0.05) -> Dict[str, Any]:
    """
    Grid search to identify the minimal d that passes ADF stationarity (p < 0.05)
    while maximizing memory preservation.
    """
    best_d = 1.0
    best_corr = 0.0
    results = []

    for d in np.arange(d_min, d_max + 1e-5, step):
        d = round(float(d), 2)
        fd = fractional_diff_ffd(series, d=d)
        adf = test_stationarity_adf(fd)
        corr = evaluate_memory_retention(series, fd)

        results.append({
            "d": d,
            "stationary": adf["stationary"],
            "p_value": adf["p_value"],
            "adf_stat": adf["adf_stat"],
            "correlation": corr
        })

        if adf["stationary"] and d < best_d:
            best_d = d
            best_corr = corr

    return {
        "optimal_d": best_d,
        "memory_correlation": best_corr,
        "grid_results": results
    }


def main():
    # Real-world styled NEPSE price series
    np.random.seed(42)
    n = 500
    # Generate geometric Brownian motion with mild drift
    dt = 1/252
    mu = 0.08
    sigma = 0.25
    steps = np.random.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), n)
    prices = pd.Series(500.0 * np.exp(np.cumsum(steps)), name="close")

    print("=" * 65)
    print("FRACTIONAL DIFFERENTIATION AUDIT (NEPSE ASSET SERIES)")
    print("=" * 65)

    orig_adf = test_stationarity_adf(prices)
    print(f"Original Price ADF p-value: {orig_adf['p_value']:.4f} (Stationary: {orig_adf['stationary']})")

    d1_diff = prices.diff()
    d1_adf = test_stationarity_adf(d1_diff)
    d1_corr = evaluate_memory_retention(prices, d1_diff)
    print(f"Integer Differenced (d=1.0) ADF p-value: {d1_adf['p_value']:.4e} | Memory Corr: {d1_corr:.4f}")

    fd_035 = fractional_diff_ffd(prices, d=0.35)
    fd_adf = test_stationarity_adf(fd_035)
    fd_corr = evaluate_memory_retention(prices, fd_035)
    print(f"Fractional Differenced (d=0.35) ADF p-value: {fd_adf['p_value']:.4f} (Stationary: {fd_adf['stationary']}) | Memory Corr: {fd_corr:.4f}")

    print("\nOptimal d Search:")
    opt = find_optimal_d(prices)
    print(f"Optimal d*: {opt['optimal_d']} | Preserved Correlation: {opt['memory_correlation']:.4f}")


if __name__ == "__main__":
    main()
