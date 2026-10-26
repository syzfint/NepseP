"""
scripts/04_backtesting/sovereign_alpha_miner/deflated_sharpe.py

DEFLATED SHARPE RATIO (DSR) & MINIMUM TRACK RECORD LENGTH (MinTRL)
==================================================================
Pure-Python, zero-dependency implementation based on:
- Bailey, D. H., & López de Prado, M. (2014). The Deflated Sharpe Ratio: 
  Correcting for Selection Bias, Backtest Overfitting, and Non-Normality.
  Journal of Portfolio Management, 40(5), 94-107.
"""

import math
import statistics
from typing import List, Dict, Any, Optional, Tuple


def _normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function (Abramowitz & Stegun approximation)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _normal_inv_cdf(p: float) -> float:
    """Rational approximation of inverse normal CDF (Wichura algorithm)."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    if p == 0.5:
        return 0.0

    # Symmetry
    q = p if p < 0.5 else 1.0 - p
    r = math.sqrt(-math.log(q))

    # Rational coefficients
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308

    x = r - ((c2 * r + c1) * r + c0) / (((d3 * r + d2) * r + d1) * r + 1.0)
    return -x if p < 0.5 else x


def compute_sample_moments(returns: List[float]) -> Tuple[float, float, float, float]:
    """Computes (mean, std, skewness, kurtosis) from return series."""
    n = len(returns)
    if n < 4:
        raise ValueError(f"At least 4 return observations required, got {n}")

    mean_ret = statistics.mean(returns)
    variance = statistics.variance(returns)
    std_ret = math.sqrt(variance) if variance > 1e-12 else 1e-6

    # Sample Skewness (Fisher-Pearson)
    m3 = sum((r - mean_ret) ** 3 for r in returns) / n
    skewness = m3 / (std_ret ** 3)

    # Sample Kurtosis (Pearson, normal = 3.0)
    m4 = sum((r - mean_ret) ** 4 for r in returns) / n
    kurtosis = m4 / (std_ret ** 4)

    return mean_ret, std_ret, skewness, kurtosis


def compute_annualized_sharpe(returns: List[float], periods_per_year: int = 240) -> float:
    """Calculates annualized Sharpe Ratio assuming zero risk-free rate."""
    if len(returns) < 2:
        return 0.0
    mean_ret = statistics.mean(returns)
    stdev = statistics.stdev(returns)
    if stdev < 1e-12:
        return 0.0
    daily_sr = mean_ret / stdev
    return daily_sr * math.sqrt(periods_per_year)


def expected_maximum_sharpe(num_trials: int, variance_sr: float, euler_gamma: float = 0.5772156649) -> float:
    """
    Computes expected maximum Sharpe ratio under null hypothesis across N independent trials.
    SR* = sqrt(V[SR]) * ((1 - gamma) * Z^-1(1 - 1/N) + gamma * Z^-1(1 - 1/(N * e)))
    """
    if num_trials <= 1:
        return 0.0
    z1 = _normal_inv_cdf(1.0 - 1.0 / num_trials)
    z2 = _normal_inv_cdf(1.0 - 1.0 / (num_trials * math.e))
    sr_star = math.sqrt(variance_sr) * ((1.0 - euler_gamma) * z1 + euler_gamma * z2)
    return max(0.0, sr_star)


def deflated_sharpe_ratio(
    returns: List[float],
    num_trials: int = 1,
    variance_sr: float = 0.50,
    benchmark_sr: float = 0.0,
    periods_per_year: int = 240
) -> Dict[str, Any]:
    """
    Computes Deflated Sharpe Ratio (DSR) and Minimum Track Record Length (MinTRL).

    Returns:
        dict: {
            "sharpe_annualized": float,
            "deflated_sharpe_ratio": float, # Probability in [0, 1]
            "sr_benchmark_hurdle": float,
            "min_trl_days": float,
            "is_statistically_significant": bool # True if DSR >= 0.95
        }
    """
    n = len(returns)
    if n < 5:
        return {
            "sharpe_annualized": 0.0,
            "deflated_sharpe_ratio": 0.0,
            "sr_benchmark_hurdle": 0.0,
            "min_trl_days": float("inf"),
            "is_statistically_significant": False
        }

    mean_ret, std_ret, skewness, kurtosis = compute_sample_moments(returns)
    sr_daily = mean_ret / std_ret if std_ret > 1e-12 else 0.0
    sr_ann = sr_daily * math.sqrt(periods_per_year)

    # Calculate selection-bias threshold SR*
    if num_trials > 1:
        sr_star = expected_maximum_sharpe(num_trials, variance_sr)
    else:
        sr_star = benchmark_sr

    # Convert annual hurdle to daily domain for statistical test
    sr_star_daily = sr_star / math.sqrt(periods_per_year)

    # Standard error under non-normality:
    # sigma_SR = sqrt((1 - skew*SR + (kurt-1)/4 * SR^2) / (T - 1))
    term = 1.0 - skewness * sr_daily + ((kurtosis - 1.0) / 4.0) * (sr_daily ** 2)
    if term <= 0:
        term = 1e-6
    se_sr = math.sqrt(term / (n - 1))

    # Test statistic Z
    z_stat = (sr_daily - sr_star_daily) / se_sr if se_sr > 1e-12 else 0.0
    dsr_pvalue = _normal_cdf(z_stat)

    # Minimum Track Record Length (MinTRL) at alpha = 0.05 (Z_0.05 = 1.64485)
    z_alpha = 1.6448536269514722
    if sr_daily > sr_star_daily:
        min_trl = 1.0 + term * ((z_alpha / (sr_daily - sr_star_daily)) ** 2)
    else:
        min_trl = float("inf")

    return {
        "sharpe_annualized": round(sr_ann, 4),
        "deflated_sharpe_ratio": round(dsr_pvalue, 4),
        "sr_benchmark_hurdle": round(sr_star, 4),
        "min_trl_days": round(min_trl, 1) if min_trl != float("inf") else -1.0,
        "is_statistically_significant": dsr_pvalue >= 0.95
    }
