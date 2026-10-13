#!/usr/bin/env python3
"""
scripts/00_control/margin_bridge_engine.py

CASH FLOW FORECASTING AND MARGIN BRIDGE ENGINE (T+2 SETTLEMENT)
==============================================================
Synchronizes multi-broker execution feeds with predictive T+2 Demat accounting
and counterparty collateral buffers.

Core Capabilities:
1. Mathematical Forecasting of Net T+2 Cash:
   C_{t+2} = C_current + sum(V_sell * (1 - tau)) - sum(V_buy * (1 + tau)) + DeltaCash_corp
2. Broker Tier Classification:
   - Class A (Tier-1 Clearing Member):
     Leverage M_leverage = 4.0x, Maintenance M_maint = 15%, Haircut H_A = 15%
   - Class B (Standard / Retail Member):
     Leverage M_leverage = 1.5x, Maintenance M_maint = 30%, Haircut H_B = 35%
3. Real-Time Available Liquidity Buffer (L_avail, b):
   L_avail, b = C_settled, b + sum(MarketValue_i, b * (1 - H_i, b)) * M_leverage - M_utilized
4. Deficit Prevention:
   Automated routing to Class A or fund transfer if projected C_{t+2} < 0.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("MarginBridgeEngine")


class BrokerClass(str, Enum):
    CLASS_A = "CLASS_A"  # Tier-1 Clearing Member
    CLASS_B = "CLASS_B"  # Standard / Retail Broker


@dataclass
class BrokerFacilityProfile:
    broker_id: str
    broker_class: BrokerClass
    leverage_multiplier: float
    maintenance_margin_pct: float
    equity_haircut_pct: float
    settled_cash: float
    utilized_margin: float = 0.0
    settlement_offset_allowed: bool = True  # True if T+2 netting permitted


@dataclass
class CollateralPosition:
    symbol: str
    quantity: int
    market_price: float

    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price


@dataclass
class SettlementForecastReport:
    as_of_date: str
    settlement_date_t2: str
    current_cash: float
    projected_t2_cash: float
    total_buy_outflow: float
    total_sell_inflow: float
    corporate_cash_inflow: float
    fee_drag: float
    deficit_detected: bool
    broker_buffers: Dict[str, float]
    recommended_broker_id: str


class MarginBridgeEngine:
    """
    Manages multi-broker T+2 settlement ledgers, margin requirements,
    and collateral allocation.
    """

    def __init__(
        self,
        transaction_fee_pct: float = 0.00415,  # 0.40% Broker + 0.015% SEBON
    ):
        self.transaction_fee_pct = transaction_fee_pct
        self.broker_profiles: Dict[str, BrokerFacilityProfile] = {}
        self.collateral_portfolios: Dict[str, List[CollateralPosition]] = {}

        # Default setup
        self.register_broker(
            broker_id="BROKER_CLASS_A_CLEARING",
            broker_class=BrokerClass.CLASS_A,
            leverage=4.0,
            maintenance_margin=0.15,
            haircut=0.15,
            settled_cash=5_000_000.0,
            netting_allowed=True,
        )
        self.register_broker(
            broker_id="BROKER_CLASS_B_RETAIL",
            broker_class=BrokerClass.CLASS_B,
            leverage=1.5,
            maintenance_margin=0.30,
            haircut=0.35,
            settled_cash=1_000_000.0,
            netting_allowed=False,
        )

    def register_broker(
        self,
        broker_id: str,
        broker_class: BrokerClass,
        leverage: float,
        maintenance_margin: float,
        haircut: float,
        settled_cash: float,
        netting_allowed: bool = True,
    ):
        self.broker_profiles[broker_id] = BrokerFacilityProfile(
            broker_id=broker_id,
            broker_class=broker_class,
            leverage_multiplier=leverage,
            maintenance_margin_pct=maintenance_margin,
            equity_haircut_pct=haircut,
            settled_cash=settled_cash,
            settlement_offset_allowed=netting_allowed,
        )
        self.collateral_portfolios[broker_id] = []

    def set_collateral(self, broker_id: str, positions: List[CollateralPosition]):
        self.collateral_portfolios[broker_id] = positions

    def calculate_available_liquidity(self, broker_id: str) -> float:
        """
        L_avail, b = C_settled, b + sum(MarketValue_i, b * (1 - H_i, b)) * M_leverage - M_utilized
        """
        prof = self.broker_profiles.get(broker_id)
        if not prof:
            return 0.0

        positions = self.collateral_portfolios.get(broker_id, [])
        collateral_val = sum(pos.market_value * (1.0 - prof.equity_haircut_pct) for pos in positions)

        l_avail = prof.settled_cash + (collateral_val * prof.leverage_multiplier) - prof.utilized_margin
        return max(l_avail, 0.0)

    def forecast_t2_cash_position(
        self,
        current_cash: float,
        buy_orders_value: float,
        sell_orders_value: float,
        corporate_actions_cash: float = 0.0,
        fee_rate: Optional[float] = None,
    ) -> float:
        """
        C_{t+2} = C_current + sum(V_sell * (1 - tau)) - sum(V_buy * (1 + tau)) + DeltaCash_corp
        """
        tau = self.transaction_fee_pct if fee_rate is None else fee_rate
        net_sell = sell_orders_value * (1.0 - tau)
        gross_buy = buy_orders_value * (1.0 + tau)

        c_t2 = current_cash + net_sell - gross_buy + corporate_actions_cash
        return c_t2

    def evaluate_settlement_and_route(
        self,
        current_cash: float,
        buy_value: float,
        sell_value: float,
        corporate_actions: float = 0.0,
    ) -> SettlementForecastReport:
        """
        Evaluates systemic T+2 net cash and identifies the optimal broker host.
        """
        c_t2 = self.forecast_t2_cash_position(
            current_cash=current_cash,
            buy_orders_value=buy_value,
            sell_orders_value=sell_value,
            corporate_actions_cash=corporate_actions,
        )

        tau = self.transaction_fee_pct
        fee_drag = (buy_value * tau) + (sell_value * tau)
        is_deficit = c_t2 < 0.0

        buffers = {}
        best_broker = ""
        max_buffer = -1.0

        for b_id in self.broker_profiles:
            buf = self.calculate_available_liquidity(b_id)
            buffers[b_id] = buf
            if buf > max_buffer:
                max_buffer = buf
                best_broker = b_id

        return SettlementForecastReport(
            as_of_date="T_TODAY",
            settlement_date_t2="T_PLUS_2",
            current_cash=current_cash,
            projected_t2_cash=round(c_t2, 2),
            total_buy_outflow=round(buy_value * (1.0 + tau), 2),
            total_sell_inflow=round(sell_value * (1.0 - tau), 2),
            corporate_cash_inflow=corporate_actions,
            fee_drag=round(fee_drag, 2),
            deficit_detected=is_deficit,
            broker_buffers=buffers,
            recommended_broker_id=best_broker,
        )
