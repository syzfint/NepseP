"""
scripts/04_backtesting/sovereign_alpha_miner/pbo_evaluator.py

PROBABILITY OF BACKTEST OVERFITTING (PBO) & CSCV ENGINE
========================================================
Pure-Python, zero-dependency implementation of:
- Bailey, D. H., Borwein, J., López de Prado, M., & Zhu, Q. J. (2015).
  The Probability of Backtest Overfitting.
  Journal of Computational Finance, 20(4), 39-69.
"""

import math
import itertools
import statistics
from typing import List, Dict, Any, Optional, Tuple


def generate_cscv_splits(num_blocks: int = 16) -> List[Tuple[Tuple[int, ...], Tuple[int, ...]]]:
    """Generates all combinations of C(S, S/2) partitions for in-sample / out-of-sample splits."""
    if num_blocks % 2 != 0:
        raise ValueError("num_blocks must be an even integer (e.g. 8, 10, 12, 16)")
    k = num_blocks // 2
    all_indices = set(range(num_blocks))
    splits = []
    for is_indices in itertools.combinations(range(num_blocks), k):
        oos_indices = tuple(sorted(all_indices - set(is_indices)))
        splits.append((is_indices, oos_indices))
    return splits


def compute_pbo_from_matrix(
    returns_matrix: List[List[float]],
    num_blocks: int = 10,
    max_combos: int = 252
) -> Dict[str, Any]:
    """
    Computes Probability of Backtest Overfitting (PBO) across N strategies / factor variations.

    Args:
        returns_matrix: Shape (T, N) where T = time periods, N = number of strategy variations.
        num_blocks: Even number of time partitions (default 10 -> C(10,5) = 252 splits).
        max_combos: Cap on combinations to keep execution time under 100ms.

    Returns:
        dict: {
            "pbo": float, # Probability in [0, 1], edge requires PBO <= 0.20
            "degradation_slope": float, # Performance degradation slope
            "best_is_strategy_idx": int,
            "sample_splits_count": int,
            "verdict": str # PASS_ROBUST vs REJECT_OVERFITTED
        }
    """
    t_periods = len(returns_matrix)
    if t_periods < num_blocks * 2:
        return {"pbo": 1.0, "degradation_slope": -1.0, "verdict": "REJECT_INSUFFICIENT_DATA"}

    num_strategies = len(returns_matrix[0])
    if num_strategies < 2:
        return {"pbo": 0.0, "degradation_slope": 0.0, "verdict": "PASS_SINGLE_TRIAL"}

    # Partition time periods into contiguous blocks
    block_size = t_periods // num_blocks
    blocks: List[List[List[float]]] = []
    for b in range(num_blocks):
        start_idx = b * block_size
        end_idx = (b + 1) * block_size if b < num_blocks - 1 else t_periods
        blocks.append(returns_matrix[start_idx:end_idx])

    # Pre-calculate mean performance of each strategy within each block
    # block_means[block_idx][strategy_idx]
    block_means = []
    for b_idx in range(num_blocks):
        b_data = blocks[b_idx]
        b_len = len(b_data)
        means = []
        for s_idx in range(num_strategies):
            s_sum = sum(b_data[row][s_idx] for row in range(b_len))
            means.append(s_sum / b_len)
        block_means.append(means)

    splits = generate_cscv_splits(num_blocks)
    if len(splits) > max_combos:
        # Uniform subsample of combinations if C(S, S/2) is large
        step = len(splits) // max_combos
        splits = splits[::step][:max_combos]

    underperformed_count = 0
    total_splits = len(splits)
    logits: List[float] = []

    for is_blocks, oos_blocks in splits:
        # Calculate In-Sample (IS) average return per strategy
        is_len = len(is_blocks)
        oos_len = len(oos_blocks)

        is_perf = [
            sum(block_means[b][s] for b in is_blocks) / is_len
            for s in range(num_strategies)
        ]

        # Calculate Out-of-Sample (OOS) average return per strategy
        oos_perf = [
            sum(block_means[b][s] for b in oos_blocks) / oos_len
            for s in range(num_strategies)
        ]

        # Identify best strategy In-Sample (max IS return)
        best_is_idx = max(range(num_strategies), key=lambda idx: is_perf[idx])

        # Rank of the chosen strategy in Out-of-Sample (relative rank in [0, 1])
        chosen_oos_val = oos_perf[best_is_idx]
        lower_count = sum(1 for val in oos_perf if val < chosen_oos_val)
        equal_count = sum(1 for val in oos_perf if val == chosen_oos_val)
        # Relative rank lambda in [0, 1]
        lambda_rank = (lower_count + 0.5 * equal_count) / num_strategies

        # If chosen strategy performs worse than median OOS strategy, count as overfit
        if lambda_rank < 0.50:
            underperformed_count += 1

        logits.append(lambda_rank)

    pbo = underperformed_count / total_splits if total_splits > 0 else 1.0
    median_rank = statistics.median(logits) if logits else 0.5

    return {
        "pbo": round(pbo, 4),
        "median_oos_rank": round(median_rank, 4),
        "total_splits_evaluated": total_splits,
        "is_overfitted": pbo > 0.20,
        "verdict": "PASS_ROBUST" if pbo <= 0.20 else "REJECT_OVERFITTED"
    }
