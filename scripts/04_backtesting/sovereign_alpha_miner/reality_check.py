"""
scripts/04_backtesting/sovereign_alpha_miner/reality_check.py

WHITE'S REALITY CHECK & HANSEN'S SUPERIOR PREDICTIVE ABILITY (SPA)
===================================================================
Pure-Python, zero-dependency implementations based on:
- White, H. (2000). A Reality Check for Data Snooping. Econometrica, 68(5), 1097-1126.
- Hansen, P. R. (2005). A Test for Superior Predictive Ability. JBES, 23(4), 365-380.
- Politis, D. N., & Romano, J. P. (1994). The Stationary Bootstrap. JASA, 89(428), 1303-1313.
"""

import math
import random
import statistics
from typing import List, Dict, Any, Tuple


def stationary_bootstrap_indices(n_samples: int, mean_block_len: float = 10.0, seed: int = 42) -> List[int]:
    """
    Generates stationary bootstrap resampling indices using geometric block lengths.
    Politis & Romano (1994).
    """
    rng = random.Random(seed)
    prob_new_block = 1.0 / max(1.0, mean_block_len)
    indices = []
    current_idx = rng.randint(0, n_samples - 1)

    for _ in range(n_samples):
        indices.append(current_idx)
        if rng.random() < prob_new_block:
            current_idx = rng.randint(0, n_samples - 1)
        else:
            current_idx = (current_idx + 1) % n_samples

    return indices


def whites_reality_check_and_spa(
    excess_returns_matrix: List[List[float]],
    num_bootstrap: int = 200,
    mean_block_len: float = 10.0,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Calculates White's Reality Check (RC) p-value and Hansen's SPA p-value across candidate factors.

    Args:
        excess_returns_matrix: Shape (T, M) representing excess returns over benchmark for M strategies.
        num_bootstrap: Number of bootstrap iterations (default 200).
        mean_block_len: Expected block length for stationary bootstrap.
        seed: Random seed for exact reproducibility.

    Returns:
        dict: {
            "white_rc_pvalue": float,
            "hansen_spa_pvalue": float,
            "best_strategy_mean": float,
            "test_statistic": float,
            "is_significant": bool # True if SPA p-value <= 0.05
        }
    """
    t_periods = len(excess_returns_matrix)
    if t_periods < 10:
        return {
            "white_rc_pvalue": 1.0,
            "hansen_spa_pvalue": 1.0,
            "best_strategy_mean": 0.0,
            "test_statistic": 0.0,
            "is_significant": False
        }

    m_strategies = len(excess_returns_matrix[0])
    sqrt_t = math.sqrt(t_periods)

    # 1. Compute sample means and variances for each strategy
    sample_means = []
    sample_vars = []
    for m in range(m_strategies):
        col = [excess_returns_matrix[t][m] for t in range(t_periods)]
        mu = statistics.mean(col)
        var = statistics.variance(col) if t_periods > 1 else 1e-6
        sample_means.append(mu)
        sample_vars.append(max(var, 1e-8))

    # Standardized test statistics for each strategy: d_bar * sqrt(T) / omega
    t_stats = [
        sample_means[m] * sqrt_t / math.sqrt(sample_vars[m])
        for m in range(m_strategies)
    ]
    t_max = max(t_stats)
    best_strategy_idx = max(range(m_strategies), key=lambda m: t_stats[m])

    # 2. Hansen's SPA centering rule:
    # mu_spa = mu if mu >= -sqrt((omega^2 / T) * 2 * ln(ln(T))) else 0
    hansen_threshold = math.sqrt(2.0 * math.log(max(1.1, math.log(t_periods)))) if t_periods > 3 else 0.0
    centered_means_spa = []
    for m in range(m_strategies):
        sigma = math.sqrt(sample_vars[m])
        limit = -(sigma / sqrt_t) * hansen_threshold
        if sample_means[m] >= limit:
            centered_means_spa.append(sample_means[m])
        else:
            centered_means_spa.append(0.0)

    # 3. Bootstrap distribution under the null
    rc_exceed_count = 0
    spa_exceed_count = 0

    for b in range(num_bootstrap):
        boot_idx = stationary_bootstrap_indices(t_periods, mean_block_len, seed=seed + b * 13)

        boot_t_stats_rc = []
        boot_t_stats_spa = []

        for m in range(m_strategies):
            sigma = math.sqrt(sample_vars[m])
            # Resampled mean
            boot_mean = sum(excess_returns_matrix[i][m] for i in boot_idx) / t_periods

            # White's RC centering: subtract full sample mean
            t_b_rc = (boot_mean - sample_means[m]) * sqrt_t / sigma
            boot_t_stats_rc.append(t_b_rc)

            # Hansen's SPA centering: subtract mu_spa
            t_b_spa = (boot_mean - centered_means_spa[m]) * sqrt_t / sigma
            boot_t_stats_spa.append(t_b_spa)

        max_b_rc = max(boot_t_stats_rc)
        max_b_spa = max(boot_t_stats_spa)

        if max_b_rc >= t_max:
            rc_exceed_count += 1
        if max_b_spa >= t_max:
            spa_exceed_count += 1

    rc_pvalue = rc_exceed_count / num_bootstrap
    spa_pvalue = spa_exceed_count / num_bootstrap

    return {
        "white_rc_pvalue": round(rc_pvalue, 4),
        "hansen_spa_pvalue": round(spa_pvalue, 4),
        "best_strategy_mean": round(sample_means[best_strategy_idx], 6),
        "test_statistic": round(t_max, 4),
        "is_significant": spa_pvalue <= 0.05
    }
