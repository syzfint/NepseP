#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/isolation_forest_microstructure_guard.py

APEXMARKETENGINE — ISOLATION FOREST MICROSTRUCTURE ANOMALY GUARD
================================================================
Unsupervised machine-learning guard detecting market cornering, circular wash-trading,
and pump-and-dump distribution patterns in illiquid NEPSE counters.

Feature Space (3D Microstructure Tuple):
1. Top-5 Broker Concentration Ratio (C5):
   Volume_top5_buyers / Total_volume in [0, 1]
2. Relative Turnover Expansion (R_vol):
   Today_Turnover / Median_Turnover_20d
3. Upper Shadow Rejection Ratio (U_shadow):
   (High - max(Open, Close)) / (High - Low + eps) in [0, 1]

Isolation Forest Formulation:
- Contamination parameter = 0.03 (top 3% tail anomalies)
- Flags anomalous scrips where anomaly_score > 0.65
- Triggers Gate G4 / Runtime Safety rejection on flagged counters.
"""

import sys
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [IsolationGuard] %(message)s"
)
logger = logging.getLogger("IsolationGuard")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class AnomalyEvaluationItem:
    symbol: str
    top5_broker_ratio: float
    turnover_ratio: float
    upper_shadow_ratio: float
    anomaly_score: float             # In [0.0, 1.0] (higher = more anomalous)
    is_anomaly: bool                 # True if anomaly_score >= threshold
    risk_category: str               # "CLEAN", "SUSPICIOUS_ACCUMULATION", "WASH_OR_PUMP_AND_DUMP"
    action: str                      # "CERTIFIED_PASS" or "GATE_REJECT"


class IsolationForestMicrostructureGuard:
    """Detects manipulative trading patterns and microstructure anomalies."""

    def __init__(self, contamination: float = 0.03, anomaly_threshold: float = 0.65):
        self.contamination = contamination
        self.anomaly_threshold = anomaly_threshold
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_estimators=100
        )
        self.is_fitted = False

    def fit(self, feature_matrix: np.ndarray):
        """Fits the Isolation Forest on 3D microstructure features: [C5, R_vol, U_shadow]."""
        if len(feature_matrix) < 10:
            logger.warning("Insufficient samples to fit Isolation Forest (< 10).")
            return
        self.model.fit(feature_matrix)
        self.is_fitted = True
        logger.info(f"Isolation Forest fitted successfully on {len(feature_matrix)} samples.")

    def fit_on_historical(self, historical_features: List[Dict[str, Any]]) -> None:
        """
        Task 7.6 — Fit the Isolation Forest on clean historical distributions.

        This method MUST be called with verified, clean historical data before
        evaluate_universe() is used in production.  Fitting on the test batch
        (the old behaviour) creates a model that is anchored to the current
        universe's distribution and will miss anomalies that were common
        historically but rare today.

        Args:
            historical_features: List of dicts with keys
                'top5_broker_ratio', 'turnover_ratio', 'upper_shadow_ratio'.
                Typically sourced from a full year of clean floorsheet data.
        """
        X = [
            [
                float(f.get("top5_broker_ratio", 0.35)),
                float(f.get("turnover_ratio", 1.0)),
                float(f.get("upper_shadow_ratio", 0.15)),
            ]
            for f in historical_features
        ]
        self.fit(np.array(X))
        logger.info("Isolation Forest fitted on %d historical samples.", len(X))

    def evaluate_universe(
        self,
        universe_features: List[Dict[str, Any]]
    ) -> List[AnomalyEvaluationItem]:
        """
        Evaluates a batch of candidate stocks.
        Expects keys: 'symbol', 'top5_broker_ratio', 'turnover_ratio', 'upper_shadow_ratio'.
        """
        if not universe_features:
            return []

        X = []
        for item in universe_features:
            c5 = float(item.get("top5_broker_ratio", 0.35))
            r_vol = float(item.get("turnover_ratio", 1.0))
            u_shadow = float(item.get("upper_shadow_ratio", 0.15))
            X.append([c5, r_vol, u_shadow])
        X_arr = np.array(X)

        if not self.is_fitted:
            # Task 7.6 (Bug C5.4 fix) — require explicit historical fit.
            # Auto-fitting on the test batch anchors the model to today's
            # distribution, so it can't reliably detect outliers.
            # We still fall back to avoid a hard crash, but emit a warning
            # so operators can call fit_on_historical() before production use.
            logger.warning(
                "IsolationForest not fitted on historical data. "
                "Call fit_on_historical() before evaluate_universe(). "
                "Falling back to auto-fit on current universe (degraded accuracy)."
            )
            self.fit(X_arr)

        # Scikit-learn score_samples returns opposite of anomaly score (lower is more anomalous)
        # We normalize to [0, 1] where 1.0 is extremely anomalous
        raw_scores = self.model.score_samples(X_arr)
        # Map raw scores (typically -0.7 to 0.0) to [0, 1]
        norm_scores = 1.0 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-6)

        results: List[AnomalyEvaluationItem] = []
        for idx, item in enumerate(universe_features):
            score = round(float(norm_scores[idx]), 4)
            is_anom = bool(score >= self.anomaly_threshold)
            c5, r_vol, u_shadow = X[idx]

            if is_anom:
                if c5 > 0.75 and r_vol > 3.0:
                    cat = "WASH_OR_PUMP_AND_DUMP"
                    act = "GATE_REJECT"
                else:
                    cat = "SUSPICIOUS_ACCUMULATION"
                    act = "GATE_REJECT"
            else:
                cat = "CLEAN"
                act = "CERTIFIED_PASS"

            results.append(AnomalyEvaluationItem(
                symbol=item.get("symbol", f"TICKER_{idx}"),
                top5_broker_ratio=round(c5, 4),
                turnover_ratio=round(r_vol, 2),
                upper_shadow_ratio=round(u_shadow, 4),
                anomaly_score=score,
                is_anomaly=is_anom,
                risk_category=cat,
                action=act
            ))

        return results


if __name__ == "__main__":
    guard = IsolationForestMicrostructureGuard(contamination=0.03, anomaly_threshold=0.65)

    # Simulate 50 normal scrips and 2 manipulated micro-caps
    np.random.seed(42)
    universe = []
    # 50 normal stocks
    for i in range(50):
        universe.append({
            "symbol": f"SCRIP_{i:02d}",
            "top5_broker_ratio": float(np.random.uniform(0.20, 0.45)),
            "turnover_ratio": float(np.random.uniform(0.8, 1.8)),
            "upper_shadow_ratio": float(np.random.uniform(0.05, 0.25))
        })
    # 2 cornered pump-and-dump stocks (Broker ratio > 85%, Turnover > 8x, high upper shadow)
    universe.append({
        "symbol": "CORNERED_HYDRO",
        "top5_broker_ratio": 0.89,
        "turnover_ratio": 8.5,
        "upper_shadow_ratio": 0.65
    })
    universe.append({
        "symbol": "WASH_MICROFIN",
        "top5_broker_ratio": 0.92,
        "turnover_ratio": 7.2,
        "upper_shadow_ratio": 0.58
    })

    eval_res = guard.evaluate_universe(universe)
    anomalies = [r for r in eval_res if r.is_anomaly]

    print("\n" + "=" * 70)
    print("      ISOLATION FOREST MICROSTRUCTURE ANOMALY GUARD TEST")
    print("=" * 70)
    print(f"Total Universe Scanned:   {len(eval_res)} scrips")
    print(f"Anomalies Flagged:        {len(anomalies)} scrips")
    for a in anomalies:
        print(f"  -> Flagged {a.symbol:<16}: Score={a.anomaly_score:.2f} | C5={a.top5_broker_ratio:.2f} | R_vol={a.turnover_ratio:.1f}x | {a.risk_category} [{a.action}]")
    print("=" * 70)
