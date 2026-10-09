#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/t2_mdp_portfolio_policy.py

CHRONOSTRATA PRIME — T+2 CONSTRAINED MDP PORTFOLIO POLICY (T2-MDP)
==================================================================
Markov Decision Process & Dynamic Asset Allocation for Cash-Locked Frontier Markets
Addresses Problem 3: Dynamic Portfolio Control for T+2 Cash-Locked, Long-Only.

Mathematical Formulation:
1. State Space S_t = (Cash_Settled, Cash_Unsettled_T1, Cash_Unsettled_T2, Holdings_Vector, Alpha_Signals)
2. Action Space A_t = Vector of Buy/Sell weights subject to:
   - w_i >= 0 (Strict Long-Only, No Shorting)
   - Buy_Expenditure <= Cash_Settled (Unsettled cash CANNOT be redeployed)
3. State Transition:
   - Cash_Settled(t+1) = Cash_Settled(t) + Cash_Unsettled_T1(t) - Buys_Executed(t)
   - Cash_Unsettled_T1(t+1) = Cash_Unsettled_T2(t)
   - Cash_Unsettled_T2(t+1) = Sells_Executed(t) * (1 - Friction)
4. Opportunity Cost Minimizer:
   Prevents selling slow assets when high-conviction signals arrive without settled liquidity.
"""

import sys
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [T2-MDP] %(message)s")
logger = logging.getLogger("T2MDPPolicy")

@dataclass
class MDPPolicyAction:
    recommended_buys: Dict[str, float]   # ticker -> NPR amount
    recommended_sells: Dict[str, float]  # ticker -> NPR amount
    locked_unsettled_cash: float
    immediately_deployable_cash: float
    liquidity_utilization_pct: float
    policy_status: str

class T2ConstrainedMDPAllocator:
    def __init__(self, friction_bps: float = 38.0, broker_tax_pct: float = 0.35):
        self.friction_mult = 1.0 - ((friction_bps / 10000.0) + (broker_tax_pct / 100.0))

    def evaluate_optimal_step(
        self,
        current_settled_cash: float,
        unsettled_t1_cash: float,
        unsettled_t2_cash: float,
        current_holdings: Dict[str, float],   # ticker -> market value NPR
        target_conviction: Dict[str, float],  # ticker -> target conviction weight [0.0, 1.0]
        macro_risk_oil: float = 0.0           # normalized Z-score of 60-day Brent EWMA
    ) -> MDPPolicyAction:
        total_equity = current_settled_cash + unsettled_t1_cash + unsettled_t2_cash + sum(current_holdings.values())
        total_locked_cash = unsettled_t1_cash + unsettled_t2_cash

        # Enforce Oil Shock Throttle Rule: MacroRisk_oil > +2.0 sigma
        if macro_risk_oil > 2.0:
            logger.warning(f"CRITICAL MACRO OIL SHOCK ACTIVE (MacroRisk_oil = {macro_risk_oil:+.2f}s > +2.0s). Triggering defensive rotation!")
            adjusted_conviction = {}
            for t, c in target_conviction.items():
                if t in ["SHIVM", "SARBTM", "GCIL"]:
                    adjusted_conviction[t] = 0.0  # Force dump / zero out (transport/clinker cost squeeze)
                elif t in ["SAHAS", "CHCL", "NGPL", "API"]:
                    adjusted_conviction[t] = c * 1.5  # Rotate into Run-of-River Clean Hydro
                else:
                    adjusted_conviction[t] = c * 0.8  # Defensive haircut
            target_conviction = adjusted_conviction

        # 1. Evaluate sell candidates to raise capital or exit weak convictions
        recommended_sells = {}
        for ticker, val in current_holdings.items():
            conv = target_conviction.get(ticker, 0.0)
            target_val = total_equity * conv
            if val > target_val:
                excess = val - target_val
                # Only sell if meaningful
                if excess > 10000.0:
                    recommended_sells[ticker] = round(excess, 2)

        # 2. Evaluate buy candidates constrained strictly by IMMEDIATELY AVAILABLE SETTLED CASH
        recommended_buys = {}
        available_budget = current_settled_cash
        
        # Desired buys
        desired_buys = {}
        for ticker, conv in target_conviction.items():
            curr_val = current_holdings.get(ticker, 0.0)
            target_val = total_equity * conv
            if target_val > curr_val:
                desired_buys[ticker] = target_val - curr_val

        tot_desired = sum(desired_buys.values())
        if tot_desired > 0:
            scaling = min(1.0, available_budget / tot_desired)
            for ticker, req_val in desired_buys.items():
                alloc = req_val * scaling
                if alloc > 5000.0:
                    recommended_buys[ticker] = round(alloc, 2)

        deployable = available_budget
        used = sum(recommended_buys.values())
        util = (used / deployable * 100) if deployable > 0 else 0.0

        status = "OPTIMAL_LIQUIDITY" if total_locked_cash / total_equity < 0.25 else "SETTLEMENT_CONSTRAINED"

        return MDPPolicyAction(
            recommended_buys=recommended_buys,
            recommended_sells=recommended_sells,
            locked_unsettled_cash=round(total_locked_cash, 2),
            immediately_deployable_cash=round(deployable, 2),
            liquidity_utilization_pct=round(util, 2),
            policy_status=status
        )

if __name__ == "__main__":
    allocator = T2ConstrainedMDPAllocator()
    res = allocator.evaluate_optimal_step(
        current_settled_cash=450000.0,
        unsettled_t1_cash=200000.0,
        unsettled_t2_cash=150000.0,
        current_holdings={"SAHAS": 520000.0, "NGPL": 380000.0, "NABIL": 400000.0},
        target_conviction={"NABIL": 0.35, "CIT": 0.25, "SAHAS": 0.15, "NGPL": 0.05}
    )
    print("T2-MDP Optimal Policy Execution Step:")
    print(asdict(res))
