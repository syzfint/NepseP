#!/usr/bin/env python3
"""
Hierarchical Risk Parity (HRP) Portfolio Allocator
==================================================
Uses skfolio.optimization.HierarchicalRiskParity to compute robust,
quasi-diagonalized asset allocations for certified NEPSE candidates.

Features:
  1. Chronos Predictive Uncertainty Shrinkage: Scales asset variances by
     (P90 - P10) uncertainty spread to penalize unstable forecasts.
  2. T+2 Demat & Circuit Limit Constraints: Enforces 3% min and 20% max weights.
  3. Defensive Cash Allocation: Allocates cash reserve when overall breadth is bearish.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

try:
    from skfolio.optimization import HierarchicalRiskParity
    from skfolio.measures import RiskMeasure
except ImportError:
    HierarchicalRiskParity = None
    RiskMeasure = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("hrp_allocator")

BASE_DIR = Path(__file__).resolve().parents[2]


class HRPPortfolioAllocator:
    """Institutional portfolio risk optimizer via skfolio Hierarchical Risk Parity."""

    def __init__(self, min_weight: float = 0.03, max_weight: float = 0.20, cash_buffer: float = 0.10):
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.cash_buffer = cash_buffer

    def allocate(
        self,
        returns_df: pd.DataFrame,
        uncertainty_spreads: Optional[Dict[str, float]] = None,
        market_breadth_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Takes a DataFrame of daily returns for certified symbols.
        Returns optimal weights and portfolio analytics.
        """
        if returns_df.empty or returns_df.shape[1] == 0:
            return {"weights": {}, "cash_weight": 1.0, "portfolio_stats": {}}

        symbols = list(returns_df.columns)
        n_assets = len(symbols)

        # Single asset edge case
        if n_assets == 1:
            sym = symbols[0]
            w = min(1.0 - self.cash_buffer, self.max_weight)
            return {
                "weights": {sym: round(w, 4)},
                "cash_weight": round(1.0 - w, 4),
                "portfolio_stats": {"expected_return": float(returns_df[sym].mean() * 252)},
            }

        # Apply Chronos uncertainty scaling to returns matrix if available
        scaled_returns = returns_df.copy()
        if uncertainty_spreads:
            for col in scaled_returns.columns:
                spread = uncertainty_spreads.get(col, 10.0)
                # If spread is high, amplify volatility to penalize in HRP tree clustering
                penalty_factor = max(1.0, spread / 8.0)
                scaled_returns[col] = scaled_returns[col] * penalty_factor

        weights_dict = {}

        if HierarchicalRiskParity is not None:
            try:
                hrp = HierarchicalRiskParity(
                    risk_measure=RiskMeasure.VARIANCE if RiskMeasure else "variance"
                )
                hrp.fit(scaled_returns)
                raw_weights = hrp.weights_
                for i, sym in enumerate(symbols):
                    weights_dict[sym] = float(raw_weights[i])
            except Exception as e:
                logger.warning(f"skfolio HRP fit warning: {e}. Falling back to inverse-variance weighting.")
                vols = returns_df.std()
                inv_vols = 1.0 / np.maximum(vols, 1e-4)
                w_norm = inv_vols / inv_vols.sum()
                weights_dict = {sym: float(w_norm[sym]) for sym in symbols}
        else:
            logger.info("skfolio not available, using inverse-volatility weighting.")
            vols = returns_df.std()
            inv_vols = 1.0 / np.maximum(vols, 1e-4)
            w_norm = inv_vols / inv_vols.sum()
            weights_dict = {sym: float(w_norm[sym]) for sym in symbols}

        # Adjust cash buffer based on market breadth
        dynamic_cash = self.cash_buffer
        if market_breadth_pct is not None and market_breadth_pct < 0.40:
            # Bearish breadth: increase cash buffer to 25%
            dynamic_cash = max(0.25, self.cash_buffer)

        # Enforce min/max weight constraints
        investable_capital = 1.0 - dynamic_cash
        constrained_weights = {}
        for sym, w in weights_dict.items():
            constrained_weights[sym] = min(max(w * investable_capital, self.min_weight), self.max_weight)

        # Re-normalize to investable capital
        total_w = sum(constrained_weights.values())
        if total_w > 0:
            for sym in constrained_weights:
                constrained_weights[sym] = round((constrained_weights[sym] / total_w) * investable_capital, 4)

        final_cash = round(1.0 - sum(constrained_weights.values()), 4)

        # Calculate portfolio statistics
        weights_vec = np.array([constrained_weights[s] for s in symbols])
        mean_ret = returns_df.mean().values * 252.0  # Annualized
        cov_matrix = returns_df.cov().values * 252.0

        port_return = float(np.dot(weights_vec, mean_ret))
        port_variance = float(np.dot(weights_vec.T, np.dot(cov_matrix, weights_vec)))
        port_volatility = float(np.sqrt(port_variance)) if port_variance > 0 else 0.0
        sharpe = round(port_return / port_volatility, 2) if port_volatility > 0 else 0.0

        return {
            "weights": constrained_weights,
            "cash_weight": final_cash,
            "portfolio_stats": {
                "expected_annual_return_pct": round(port_return * 100.0, 2),
                "annual_volatility_pct": round(port_volatility * 100.0, 2),
                "annual_sharpe_ratio": sharpe,
                "dynamic_cash_buffer_pct": round(dynamic_cash * 100.0, 2),
            },
        }


def main():
    allocator = HRPPortfolioAllocator()

    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=100)
    data = {
        "NABIL": np.random.normal(0.0005, 0.015, 100),
        "GBIME": np.random.normal(0.0004, 0.016, 100),
        "SHIVM": np.random.normal(0.0008, 0.025, 100),
        "HDL": np.random.normal(0.0003, 0.018, 100),
        "SCB": np.random.normal(0.0006, 0.012, 100),
    }
    df = pd.DataFrame(data, index=dates)
    spreads = {"NABIL": 6.5, "GBIME": 7.0, "SHIVM": 14.5, "HDL": 9.0, "SCB": 5.2}

    res = allocator.allocate(df, uncertainty_spreads=spreads, market_breadth_pct=0.35)
    print("HRP Allocation Result:", res)


if __name__ == "__main__":
    main()
