#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/hawkes_broker_cascade.py

APEXMARKETENGINE — SELF-EXCITING HAWKES PROCESS FOR BROKER CASCADES
===================================================================
Models incoming aggressive block buys from dominant institutional brokers
(e.g., Broker 58, 45, 49) as a self-exciting temporal point process.

Mathematical Architecture:
1. Conditional Intensity:
   lambda(t) = mu + sum_{t_i < t} alpha * exp(-beta * (t - t_i))
   - mu    : Exogenous background arrival rate of institutional trades
   - alpha : Excitation magnitude (impact of a single trade on future arrivals)
   - beta  : Decay rate (memory dissipation speed)
2. Branching Ratio:
   eta = alpha / beta in [0, 1)
   - eta < 0.50 : Sub-critical, stable Poisson-like arrivals
   - 0.50 <= eta < 0.85 : Moderately excited accumulation
   - eta >= 0.85 : Super-critical clustering; cascade imminent before circuit freeze
3. Microstructure Utility:
   Detects institutional copy-trading cascades in low-float NEPSE scrips 5–15 minutes
   before the +10% upper circuit ask wall is exhausted.
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
from scipy.optimize import minimize

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [HawkesCascade] %(message)s"
)
logger = logging.getLogger("HawkesCascade")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class HawkesParameters:
    mu: float             # Background baseline arrival rate
    alpha: float          # Excitation multiplier
    beta: float           # Exponential decay rate
    branching_ratio: float# eta = alpha / beta
    log_likelihood: float
    is_supercritical: bool
    cascade_hazard_score: float  # Scale 0.0 - 100.0


@dataclass
class BrokerCascadeAlert:
    symbol: str
    target_broker_id: str
    event_timestamp: str
    trade_count_window: int
    current_intensity: float
    branching_ratio: float
    regime: str           # "QUIET", "ACCUMULATING", "SUPERCRITICAL_CASCADE"
    circuit_freeze_probability: float
    recommended_action: str


class HawkesBrokerCascadeEngine:
    """Self-Exciting Point Process Engine for Sovereign Broker Order Flow."""

    def __init__(self, dominant_brokers: Optional[List[str]] = None):
        self.dominant_brokers = dominant_brokers or ["58", "45", "49", "28", "34"]

    def _neg_log_likelihood(self, params: np.ndarray, timestamps: np.ndarray, T_end: float) -> float:
        """
        Computes negative log-likelihood of a 1D exponential Hawkes process:
        LL = sum_{i=1}^n ln(lambda(t_i)) - Lambda(T_end)
        where Lambda(T) = mu * T + (alpha / beta) * sum_{i=1}^n [1 - exp(-beta * (T - t_i))]
        """
        mu, alpha, beta = params
        if mu <= 1e-6 or alpha < 0.0 or beta <= alpha or beta <= 1e-6:
            return 1e9

        n = len(timestamps)
        # Recursive calculation of R(i) = sum_{j < i} exp(-beta * (t_i - t_j))
        r = np.zeros(n)
        for i in range(1, n):
            dt = timestamps[i] - timestamps[i - 1]
            r[i] = np.exp(-beta * dt) * (r[i - 1] + 1.0)

        intensities = mu + alpha * r
        if np.any(intensities <= 0):
            return 1e9

        term1 = np.sum(np.log(intensities))
        # Integrated intensity
        term2 = mu * T_end + (alpha / beta) * np.sum(1.0 - np.exp(-beta * (T_end - timestamps)))
        return -(term1 - term2)

    def fit(self, timestamps_seconds: np.ndarray, T_end: Optional[float] = None) -> HawkesParameters:
        """Fits Hawkes parameters (mu, alpha, beta) via Maximum Likelihood Estimation (MLE)."""
        if len(timestamps_seconds) < 3:
            return HawkesParameters(
                mu=0.01, alpha=0.0, beta=1.0, branching_ratio=0.0,
                log_likelihood=0.0, is_supercritical=False, cascade_hazard_score=0.0
            )

        ts = np.sort(timestamps_seconds)
        t0 = ts[0]
        ts_rel = ts - t0
        T = (ts_rel[-1] + 60.0) if T_end is None else (T_end - t0)

        # Initial parameter estimates
        dt_mean = np.mean(np.diff(ts_rel)) if len(ts_rel) > 1 else 60.0
        init_mu = max(1e-4, 1.0 / dt_mean * 0.4)
        init_beta = max(0.01, 2.0 / dt_mean)
        init_alpha = init_beta * 0.45  # initial branching ratio ~0.45

        init_params = np.array([init_mu, init_alpha, init_beta])
        bounds = [(1e-5, 5.0), (0.0, 10.0), (1e-4, 10.0)]

        res = minimize(
            self._neg_log_likelihood,
            init_params,
            args=(ts_rel, T),
            method="L-BFGS-B",
            bounds=bounds
        )

        mu, alpha, beta = res.x
        branching_ratio = round(alpha / beta, 4) if beta > 0 else 0.0
        hazard_score = min(100.0, round((branching_ratio ** 1.5) * 100.0, 2))
        is_super = bool(branching_ratio >= 0.85)

        return HawkesParameters(
            mu=round(float(mu), 5),
            alpha=round(float(alpha), 5),
            beta=round(float(beta), 5),
            branching_ratio=branching_ratio,
            log_likelihood=round(float(-res.fun), 2),
            is_supercritical=is_super,
            cascade_hazard_score=hazard_score
        )

    def evaluate_broker_stream(
        self,
        symbol: str,
        trades: List[Dict[str, Any]],
        as_of_time: Optional[str] = None
    ) -> BrokerCascadeAlert:
        """
        Evaluates trades for a specific symbol, filtering for dominant institutional brokers
        and calculating real-time cascade probability.
        """
        now_iso = as_of_time or datetime.now(timezone.utc).isoformat()
        
        # Filter for dominant broker aggressive buys
        dom_trades = [
            t for t in trades
            if str(t.get("buyerBrokerId", t.get("buyer_broker", ""))) in self.dominant_brokers
        ]

        if len(dom_trades) < 3:
            return BrokerCascadeAlert(
                symbol=symbol,
                target_broker_id="ALL_DOMINANT",
                event_timestamp=now_iso,
                trade_count_window=len(dom_trades),
                current_intensity=0.01,
                branching_ratio=0.0,
                regime="QUIET",
                circuit_freeze_probability=0.05,
                recommended_action="PASSIVE_OBSERVE"
            )

        # Convert trade timestamps to relative seconds
        ts_sec = []
        for t in dom_trades:
            ts_str = t.get("tradeTime", t.get("time", ""))
            try:
                # Handle HH:MM:SS format
                parts = [int(p) for p in ts_str.split(":")[:3]]
                sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
                ts_sec.append(sec)
            except Exception:
                ts_sec.append(len(ts_sec) * 30)

        ts_arr = np.array(ts_sec, dtype=float)
        params = self.fit(ts_arr)

        # Compute instantaneous intensity at latest trade
        r_last = 0.0
        for i in range(len(ts_arr) - 1):
            r_last = np.exp(-params.beta * (ts_arr[-1] - ts_arr[i])) * (r_last + 1.0)
        cur_intensity = round(params.mu + params.alpha * r_last, 4)

        if params.branching_ratio >= 0.85:
            regime = "SUPERCRITICAL_CASCADE"
            action = "IMMEDIATE_FRONT_RUN_BUY_BEFORE_CIRCUIT_LOCK"
            circuit_prob = 0.88
        elif params.branching_ratio >= 0.50:
            regime = "ACCUMULATING"
            action = "PREPARE_LIMIT_ORDER_STAGING"
            circuit_prob = 0.45
        else:
            regime = "QUIET"
            action = "PASSIVE_OBSERVE"
            circuit_prob = 0.10

        return BrokerCascadeAlert(
            symbol=symbol,
            target_broker_id="DOMINANT_CLUSTER",
            event_timestamp=now_iso,
            trade_count_window=len(dom_trades),
            current_intensity=cur_intensity,
            branching_ratio=params.branching_ratio,
            regime=regime,
            circuit_freeze_probability=circuit_prob,
            recommended_action=action
        )


if __name__ == "__main__":
    engine = HawkesBrokerCascadeEngine()
    
    # Simulate an institutional accumulation burst by Broker 58 (e.g. 15 trades clustering tightly)
    sim_times = [
        "11:15:00", "11:15:45", "11:16:10", "11:16:22", "11:16:30",
        "11:16:34", "11:16:38", "11:16:40", "11:16:42", "11:16:43"
    ]
    sim_trades = [{"buyer_broker": "58", "time": t, "qty": 500} for t in sim_times]

    alert = engine.evaluate_broker_stream("CHCL", sim_trades)
    print("\n" + "=" * 70)
    print("      HAWKES SELF-EXCITING BROKER CASCADE DETECTOR TEST")
    print("=" * 70)
    print(f"Symbol:                   {alert.symbol}")
    print(f"Cluster Trades:           {alert.trade_count_window} trades")
    print(f"Current Intensity lambda(t): {alert.current_intensity:.4f} trades/sec")
    print(f"Branching Ratio (eta):    {alert.branching_ratio:.4f} (Threshold: 0.85)")
    print(f"Cascade Regime:           {alert.regime}")
    print(f"Circuit Lockup Risk:      {alert.circuit_freeze_probability*100:.1f}%")
    print(f"Tactical Action:          {alert.recommended_action}")
    print("=" * 70)
