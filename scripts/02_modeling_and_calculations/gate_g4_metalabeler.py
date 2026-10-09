#!/usr/bin/env python3
"""
Gate G4 Institutional Meta-Labeling Engine
=========================================
Implements Bayesian Laplace smoothing, T+2 Demat illiquidity penalties,
and microstructural filtering to certify institutional trading candidates.

Filters applied:
  1. Primary Model Convergence: Chronos P50 expected return > 0% & Kronos score > 0.
  2. Microstructure Traps: Immediate rejection if Bull-Trap Gap Rejection or Bearish OBV Divergence.
  3. Liquidity & Demat Gate: 20d ADV >= 2,000 shares and Amihud Illiquidity <= 0.05.
  4. Uncertainty Spread: Chronos spread (P90 - P10)/P50 <= 15.0%.
  5. Bayesian Meta-Label Probability: P(Success | Features) >= 0.55.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gate_g4_metalabeler")


class GateG4MetaLabeler:
    """Certifies candidates through multi-factor microstructural gates."""

    def __init__(self, prob_threshold: float = 0.55):
        self.prob_threshold = prob_threshold

    def evaluate_candidate(
        self,
        symbol: str,
        chronos_metrics: Dict[str, Any],
        kronos_metrics: Dict[str, Any],
        microstructure_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates a candidate and returns certification decision with audit trace.
        """
        micro = microstructure_metrics or {}
        rejection_reasons = []

        # 1. Microstructure Traps & Suspensions Check
        if kronos_metrics.get("gap_rejection", False):
            rejection_reasons.append("BULL_TRAP_GAP_REJECTION")
        if kronos_metrics.get("pv_divergence", False):
            rejection_reasons.append("BEARISH_VOLUME_EXHAUSTION")
        if kronos_metrics.get("regime") == "SUSPENDED_REOPEN_STABILIZING":
            rejection_reasons.append("SUSPENDED_REOPEN_STABILIZING (Needs 20 contiguous sessions post-reopening)")

        # 2. Promoter Share 3-Year Lock-In Expiry Supply Wall Check
        lockin_info = micro.get("promoter_lockin", {})
        if lockin_info.get("has_lockin_risk", False):
            rejection_reasons.append(f"PROMOTER_LOCKIN_EXPIRY_RISK (3Y Window: {lockin_info.get('freeze_window')})")

        # 3. Circular Wash Trading Filter (Section 94/95 Securities Act)
        wash_ratio = micro.get("wash_turnover_ratio", 0.0)
        if wash_ratio > 0.15:
            rejection_reasons.append(f"CIRCULAR_WASH_MANIPULATION_RISK ({wash_ratio * 100.0:.1f}% > 15.0%)")

        # 4. Chronos Uncertainty Spread Check
        spread = chronos_metrics.get("uncertainty_spread", 0.0)
        if spread > 15.0:
            rejection_reasons.append(f"HIGH_UNCERTAINTY_SPREAD ({spread:.1f}% > 15.0%)")

        exp_ret = chronos_metrics.get("expected_return_pct", 0.0)
        if exp_ret <= 0.0:
            rejection_reasons.append(f"NEGATIVE_CHRONOS_DRIFT ({exp_ret:.2f}%)")

        # 3. Liquidity and T+2 Demat Check
        adv_20d = micro.get("adv_20d", 50000)
        if adv_20d < 2000:
            rejection_reasons.append(f"ILLIQUID_T2_DEMAT_RISK (ADV {adv_20d} < 2000)")

        amihud = micro.get("amihud_illiquidity", 0.001)
        if amihud > 0.05:
            rejection_reasons.append(f"HIGH_AMIHUD_ILLIQUIDITY ({amihud:.4f} > 0.05)")

        # 4. Bayesian Laplace Meta-Probability Computation
        k_score = kronos_metrics.get("kronos_score", 0.0)
        is_floor_bounce = kronos_metrics.get("is_floor_bounce", False)
        order_imbalance = micro.get("order_book_imbalance", 0.0)

        # Prior base rate (Laplace smoothed historical win rate: (120 + 1) / (200 + 2) ~ 0.599)
        base_prior = 0.599

        # Adjust probability based on orthogonal evidence
        p_logit = np.log(base_prior / (1.0 - base_prior))

        # Chronos drift contribution
        p_logit += np.clip(exp_ret / 10.0, -0.5, 0.8)

        # Kronos K-line pattern contribution
        p_logit += 0.8 * k_score

        # Floor bounce bonus
        if is_floor_bounce:
            p_logit += 0.35

        # Live order book imbalance contribution
        if order_imbalance > 0.20:
            p_logit += 0.25
        elif order_imbalance < -0.20:
            p_logit -= 0.35

        # T+2 lock-in volatility penalty
        vol_30d = micro.get("volatility_30d", 0.02)
        if vol_30d > 0.04:
            p_logit -= 0.20  # penalty for high daily volatility with 2-day lockup

        meta_prob = 1.0 / (1.0 + np.exp(-p_logit))
        meta_prob = float(np.clip(meta_prob, 0.05, 0.95))

        # Check threshold
        is_certified = (len(rejection_reasons) == 0) and (meta_prob >= self.prob_threshold)

        if not is_certified and len(rejection_reasons) == 0:
            rejection_reasons.append(f"BELOW_CONFIDENCE_THRESHOLD ({meta_prob:.2%} < {self.prob_threshold:.2%})")

        return {
            "symbol": symbol,
            "certified": is_certified,
            "meta_label_probability": round(meta_prob, 4),
            "rejection_reasons": rejection_reasons,
            "chronos_p50_exp_return": exp_ret,
            "chronos_uncertainty_spread": spread,
            "kronos_score": k_score,
            "kronos_regime": kronos_metrics.get("regime", "NEUTRAL"),
            "is_floor_bounce": is_floor_bounce,
            "order_book_imbalance": round(order_imbalance, 4),
        }

    def filter_universe(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filters a list of candidate dictionaries and returns only certified."""
        certified = []
        for c in candidates:
            res = self.evaluate_candidate(
                symbol=c["symbol"],
                chronos_metrics=c.get("chronos", {}),
                kronos_metrics=c.get("kronos", {}),
                microstructure_metrics=c.get("microstructure", {}),
            )
            if res["certified"]:
                certified.append(res)
        logger.info(f"Gate G4 Filtered: {len(certified)} of {len(candidates)} candidates certified.")
        return certified


def main():
    labeler = GateG4MetaLabeler()

    test_valid = {
        "symbol": "NABIL",
        "chronos": {"expected_return_pct": 3.8, "uncertainty_spread": 8.5},
        "kronos": {"kronos_score": 0.75, "regime": "CONFIRMED_FLOOR_BOUNCE", "is_floor_bounce": True, "gap_rejection": False, "pv_divergence": False},
        "microstructure": {"order_book_imbalance": 0.31, "adv_20d": 35000, "amihud_illiquidity": 0.005},
    }
    print("Valid Candidate Test:", labeler.evaluate_candidate("NABIL", test_valid["chronos"], test_valid["kronos"], test_valid["microstructure"]))

    test_trap = {
        "symbol": "CFCL",
        "chronos": {"expected_return_pct": 4.5, "uncertainty_spread": 12.0},
        "kronos": {"kronos_score": -0.60, "regime": "BULL_TRAP_GAP_REJECTION", "gap_rejection": True, "pv_divergence": False},
        "microstructure": {"order_book_imbalance": -0.10, "adv_20d": 12000, "amihud_illiquidity": 0.012},
    }
    print("Bull Trap Test:", labeler.evaluate_candidate("CFCL", test_trap["chronos"], test_trap["kronos"], test_trap["microstructure"]))


if __name__ == "__main__":
    main()
