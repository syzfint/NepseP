"""
scripts/04_backtesting/sovereign_alpha_miner/lakehouse_vectorizer.py

ZERO-COPY LAKEHOUSE FACTOR VECTORIZER & RANK-IC EVALUATOR
=========================================================
Extracts panel datasets from market_master_union.parquet and computes forward
Spearman RankIC, Information Ratio, and turnover metrics for candidate alpha factors.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
MASTER_PARQUET = BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"
TECH_PARQUET = BASE_DIR / "03_feature_store" / "technical_indicators.parquet"
BROKER_PARQUET = BASE_DIR / "03_feature_store" / "floorsheet_broker_signals.parquet"


def load_factor_panel_data(min_date: str = "2024-01-01", max_date: str = "2026-10-26") -> pd.DataFrame:
    """Loads panel data merging price bars and microstructure features via DuckDB."""
    if not MASTER_PARQUET.exists():
        raise FileNotFoundError(f"Master lakehouse not found at {MASTER_PARQUET}")

    con = duckdb.connect()
    p_master = str(MASTER_PARQUET).replace('\\', '/')
    p_tech = str(TECH_PARQUET).replace('\\', '/') if TECH_PARQUET.exists() else None
    p_broker = str(BROKER_PARQUET).replace('\\', '/') if BROKER_PARQUET.exists() else None

    # Base pricing query
    query = f"""
        SELECT 
            ticker, 
            CAST(date AS DATE) AS date,
            open, high, low, close, volume,
            ROUND(close * volume, 2) AS turnover,
            LEAD(close, 5) OVER (PARTITION BY ticker ORDER BY date ASC) AS fwd_close_5d
        FROM read_parquet('{p_master}')
        WHERE date >= '{min_date}' AND date <= '{max_date}'
          AND security_type IN ('ORDINARY_EQUITY', 'MICROFINANCE')
    """
    df = con.execute(query).df()
    df["fwd_return_5d"] = (df["fwd_close_5d"] - df["close"]) / df["close"]
    return df


def compute_spearman_rank_ic(factor_series: pd.Series, return_series: pd.Series) -> float:
    """Calculates cross-sectional Spearman Rank Correlation (RankIC)."""
    valid_mask = factor_series.notna() & return_series.notna() & np.isfinite(factor_series) & np.isfinite(return_series)
    if valid_mask.sum() < 5:
        return 0.0

    f_rank = factor_series[valid_mask].rank()
    r_rank = return_series[valid_mask].rank()

    cov = np.cov(f_rank, r_rank)[0, 1]
    var_f = np.var(f_rank, ddof=1)
    var_r = np.var(r_rank, ddof=1)

    if var_f <= 1e-12 or var_r <= 1e-12:
        return 0.0

    return float(cov / np.sqrt(var_f * var_r))


def evaluate_factor_candidate(df: pd.DataFrame, factor_col: str) -> Dict[str, Any]:
    """
    Computes time-series mean RankIC, IC Standard Deviation, and Information Ratio (IR).
    """
    dates = df["date"].unique()
    daily_rank_ics: List[float] = []

    for d in dates:
        day_slice = df[df["date"] == d]
        if len(day_slice) < 10:
            continue
        ric = compute_spearman_rank_ic(day_slice[factor_col], day_slice["fwd_return_5d"])
        if np.isfinite(ric):
            daily_rank_ics.append(ric)

    if not daily_rank_ics:
        return {"mean_rank_ic": 0.0, "ic_std": 0.0, "ic_ir": 0.0, "sample_days": 0}

    mean_ic = float(np.mean(daily_rank_ics))
    std_ic = float(np.std(daily_rank_ics, ddof=1)) if len(daily_rank_ics) > 1 else 1e-6
    ir = float(mean_ic / std_ic) if std_ic > 1e-12 else 0.0

    return {
        "mean_rank_ic": round(mean_ic, 4),
        "ic_std": round(std_ic, 4),
        "ic_ir": round(ir, 4),
        "sample_days": len(daily_rank_ics)
    }
