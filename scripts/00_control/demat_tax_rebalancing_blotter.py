#!/usr/bin/env python3
"""
scripts/00_control/demat_tax_rebalancing_blotter.py

APEXMARKETENGINE — DEMAT & MEROSHARE TAX-OPTIMIZED REBALANCING BLOTTER
======================================================================
Reconciles target HRP portfolio allocations with physical CDSC / Meroshare
depository holdings while optimizing SEBON Capital Gains Tax (CGT) and transaction fees.

Statutory Nepalese Capital Market Tax Architecture:
1. Capital Gains Tax (CGT) Brackets (SEBON / Inland Revenue Dept):
   - Individual Short-Term (< 365 calendar days): 7.5% CGT
   - Individual Long-Term (>= 365 calendar days): 5.0% CGT
   - Corporate Institutional: 10.0% CGT
2. Statutory Transaction Fees:
   - SEBON Regulatory Fee: 0.015% of trade turnover
   - DP (Depository Participant) Fee: NPR 25.00 flat per scrip sell
   - Tiered Broker Commission:
     * Up to Rs. 50,000      : 0.40%
     * Rs. 50,001 - 500,000  : 0.37%
     * Rs. 500,001 - 2,000,000: 0.34%
     * Rs. 2,000,001 - 10,000,000: 0.30%
     * Above Rs. 10,000,000  : 0.27%
3. FIFO Share Lot Tax-Loss Harvesting:
   - Tracks individual purchase lots to sell highest-cost lots first or long-term lots to minimize CGT.
"""

import sys
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [DematTaxBlotter] %(message)s"
)
logger = logging.getLogger("DematTaxBlotter")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class DematLot:
    lot_id: str
    symbol: str
    quantity: int
    purchase_price_npr: float
    purchase_date: str          # YYYY-MM-DD
    is_settled_t2: bool = True


@dataclass
class TaxRebalanceTicket:
    ticket_id: str
    symbol: str
    side: str                   # "BUY" or "SELL"
    quantity: int
    limit_price: float
    turnover_npr: float
    estimated_broker_commission: float
    sebon_fee_npr: float
    dp_fee_npr: float
    capital_gains_npr: float
    cgt_liability_npr: float
    holding_period_days: int
    cgt_bracket_applied: str    # "LONG_TERM_5%", "SHORT_TERM_7.5%", "CORPORATE_10%", "N/A_BUY"
    net_settlement_cash_npr: float


@dataclass
class DematRebalancingReport:
    client_demat_id: str
    as_of_date: str
    total_rebalance_turnover_npr: float
    total_cgt_liability_npr: float
    total_transaction_friction_npr: float  # broker + sebon + dp
    effective_friction_bps: float
    tickets: List[Dict[str, Any]]
    summary_notes: str


class DematTaxRebalancingEngine:
    """Tax-aware rebalancing blotter reconciling Meroshare lots with target weights."""

    def __init__(self, investor_type: str = "INDIVIDUAL"):
        self.investor_type = investor_type.upper()  # "INDIVIDUAL" or "CORPORATE"

    def compute_broker_commission(self, trade_turnover: float) -> float:
        """Calculates SEBON statutory tiered brokerage commission."""
        if trade_turnover <= 50_000:
            rate = 0.0040
        elif trade_turnover <= 500_000:
            rate = 0.0037
        elif trade_turnover <= 2_000_000:
            rate = 0.0034
        elif trade_turnover <= 10_000_000:
            rate = 0.0030
        else:
            rate = 0.0027
        return round(trade_turnover * rate, 2)

    def calculate_cgt(
        self,
        cost_price: float,
        sell_price: float,
        qty: int,
        holding_days: int
    ) -> Tuple[float, float, str]:
        """Calculates capital gain and net CGT liability."""
        gain = (sell_price - cost_price) * qty
        if gain <= 0:
            return round(gain, 2), 0.0, "NO_GAIN_OR_LOSS"

        if self.investor_type == "CORPORATE":
            cgt_rate = 0.10
            bracket = "CORPORATE_10%"
        else:
            if holding_days >= 365:
                cgt_rate = 0.05
                bracket = "LONG_TERM_5%"
            else:
                cgt_rate = 0.075
                bracket = "SHORT_TERM_7.5%"

        cgt_val = round(gain * cgt_rate, 2)
        return round(gain, 2), cgt_val, bracket

    def generate_rebalancing_blotter(
        self,
        current_demat_lots: Dict[str, List[DematLot]],
        target_allocations: Dict[str, float],   # symbol -> target_value_npr
        current_prices: Dict[str, float],       # symbol -> latest_close
        client_demat_id: str = "1301090001234567",
        as_of_date: str = "2026-10-07"
    ) -> DematRebalancingReport:
        """
        Computes minimal-turnover buy/sell rebalancing tickets, factoring in FIFO lots and CGT.
        """
        as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
        tickets: List[TaxRebalanceTicket] = []

        total_turnover = 0.0
        total_cgt = 0.0
        total_friction = 0.0

        all_symbols = sorted(list(set(list(current_demat_lots.keys()) + list(target_allocations.keys()))))

        for sym in all_symbols:
            price = current_prices.get(sym, 100.0)
            if price <= 0:
                continue

            lots = current_demat_lots.get(sym, [])
            held_qty = sum(l.quantity for l in lots)
            held_val = held_qty * price

            target_val = target_allocations.get(sym, 0.0)
            target_qty = int(target_val / price)
            target_qty = (target_qty // 10) * 10  # 10-unit board lots

            diff_qty = target_qty - held_qty

            # 1. SELL TICKETS (Over-allocated or exit positions)
            if diff_qty < -9:
                sell_qty_needed = abs(diff_qty)
                # Sort lots FIFO (oldest first to favor 5% long-term tax rate)
                sorted_lots = sorted(lots, key=lambda l: l.purchase_date)

                for lot in sorted_lots:
                    if sell_qty_needed < 10:
                        break
                    lot_sell_qty = min(lot.quantity, sell_qty_needed)
                    lot_sell_qty = (lot_sell_qty // 10) * 10
                    if lot_sell_qty < 10:
                        continue

                    sell_qty_needed -= lot_sell_qty
                    turnover = lot_sell_qty * price
                    comm = self.compute_broker_commission(turnover)
                    sebon = round(turnover * 0.00015, 2)
                    dp_fee = 25.0

                    lot_dt = datetime.strptime(lot.purchase_date, "%Y-%m-%d")
                    holding_days = max(1, (as_of_dt - lot_dt).days)

                    gain, cgt, bracket = self.calculate_cgt(
                        cost_price=lot.purchase_price_npr,
                        sell_price=price,
                        qty=lot_sell_qty,
                        holding_days=holding_days
                    )

                    net_cash = round(turnover - comm - sebon - dp_fee - cgt, 2)

                    tkt = TaxRebalanceTicket(
                        ticket_id=f"TKT-REBAL-{sym}-S-{lot.lot_id}",
                        symbol=sym,
                        side="SELL",
                        quantity=lot_sell_qty,
                        limit_price=price,
                        turnover_npr=turnover,
                        estimated_broker_commission=comm,
                        sebon_fee_npr=sebon,
                        dp_fee_npr=dp_fee,
                        capital_gains_npr=gain,
                        cgt_liability_npr=cgt,
                        holding_period_days=holding_days,
                        cgt_bracket_applied=bracket,
                        net_settlement_cash_npr=net_cash
                    )
                    tickets.append(tkt)
                    total_turnover += turnover
                    total_cgt += cgt
                    total_friction += (comm + sebon + dp_fee)

            # 2. BUY TICKETS (Under-allocated target positions)
            elif diff_qty > 9:
                buy_qty = (diff_qty // 10) * 10
                turnover = buy_qty * price
                comm = self.compute_broker_commission(turnover)
                sebon = round(turnover * 0.00015, 2)
                dp_fee = 0.0 # No DP fee on buys

                tkt = TaxRebalanceTicket(
                    ticket_id=f"TKT-REBAL-{sym}-B-01",
                    symbol=sym,
                    side="BUY",
                    quantity=buy_qty,
                    limit_price=price,
                    turnover_npr=turnover,
                    estimated_broker_commission=comm,
                    sebon_fee_npr=sebon,
                    dp_fee_npr=dp_fee,
                    capital_gains_npr=0.0,
                    cgt_liability_npr=0.0,
                    holding_period_days=0,
                    cgt_bracket_applied="N/A_BUY",
                    net_settlement_cash_npr=round(-(turnover + comm + sebon), 2)
                )
                tickets.append(tkt)
                total_turnover += turnover
                total_friction += (comm + sebon)

        total_costs = total_friction + total_cgt
        eff_friction_bps = round((total_costs / total_turnover * 10_000), 1) if total_turnover > 0 else 0.0

        return DematRebalancingReport(
            client_demat_id=client_demat_id,
            as_of_date=as_of_date,
            total_rebalance_turnover_npr=round(total_turnover, 2),
            total_cgt_liability_npr=round(total_cgt, 2),
            total_transaction_friction_npr=round(total_friction, 2),
            effective_friction_bps=eff_friction_bps,
            tickets=[asdict(t) for t in tickets],
            summary_notes=(
                f"Generated {len(tickets)} tax-optimized rebalance tickets. "
                f"Total turnover: Rs. {total_turnover:,.2f} | CGT liability: Rs. {total_cgt:,.2f}."
            )
        )


if __name__ == "__main__":
    engine = DematTaxRebalancingEngine(investor_type="INDIVIDUAL")

    # Demat holdings: NABIL (bought 400 days ago, long-term 5%) and SHIVM (bought 90 days ago, short-term 7.5%)
    holdings = {
        "NABIL": [DematLot("L01", "NABIL", 200, 450.0, "2025-09-01", True)],
        "SHIVM": [DematLot("L02", "SHIVM", 300, 480.0, "2026-07-05", True)]
    }
    # Targets: exit NABIL, reduce SHIVM to 100 shares, buy NICA (Rs. 100k)
    targets = {
        "NABIL": 0.0,
        "SHIVM": 50_000.0,
        "NICA": 100_000.0
    }
    prices = {"NABIL": 550.0, "SHIVM": 520.0, "NICA": 500.0}

    report = engine.generate_rebalancing_blotter(holdings, targets, prices, as_of_date="2026-10-07")
    print("\n" + "=" * 70)
    print("      DEMAT & MEROSHARE TAX-OPTIMIZED REBALANCING BLOTTER TEST")
    print("=" * 70)
    print(f"Demat Account:            {report.client_demat_id}")
    print(f"Total Rebalance Turnover: Rs. {report.total_rebalance_turnover_npr:,.2f}")
    print(f"Capital Gains Tax (CGT):  Rs. {report.total_cgt_liability_npr:,.2f}")
    print(f"Total Friction (Fees):    Rs. {report.total_transaction_friction_npr:,.2f}")
    print(f"Effective Cost Drag:      {report.effective_friction_bps:.1f} bps")
    print("-" * 70)
    for t in report.tickets:
        print(f"  [{t['side']:<4}] {t['symbol']:<6} x {t['quantity']:<4} @ Rs. {t['limit_price']:.1f} | Turnover: Rs. {t['turnover_npr']:,.0f} | CGT: Rs. {t['cgt_liability_npr']:,.1f} ({t['cgt_bracket_applied']})")
    print("=" * 70)
