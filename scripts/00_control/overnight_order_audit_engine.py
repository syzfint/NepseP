#!/usr/bin/env python3
"""
scripts/00_control/overnight_order_audit_engine.py

AUTOMATED OVERNIGHT & PRE-OPEN ORDER AUDIT ENGINE
=================================================
Executes systematically during the pre-open auction phase (parameterized
for NEPSE 10:35-10:40 AM, or CSE 10:15 AM).

Multi-Factor Evaluation & FIX Operational Actions:
1. Overnight NLP News Sentiment (S_news in [-1.0, 1.0]):
   If S_news < -0.40 on active BUY limit order -> Immediate Cancel (FIX 35=F).
2. Pre-Open Order Imbalance (OI):
   OI = (BidVol_pre - AskVol_pre) / (BidVol_pre + AskVol_pre)
   If OI < -0.50 on active BUY limit order -> Immediate Cancel (FIX 35=F).
3. Theoretical Opening Price (TOP) Slippage:
   If |P_limit - P_TOP| / P_TOP > 0.03 (3% divergence) -> Modify Limit Price to P_TOP (FIX 35=G).
4. Relative Spread Guard:
   If RelativeSpread > 8.0% -> Pause order activation (Hold in queue state).
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from multi_broker_router import MultiBrokerRouter, RoutedOrderRecord

logger = logging.getLogger("OvernightOrderAuditEngine")


@dataclass
class PreOpenAuditAuditTicket:
    cl_ord_id: str
    symbol: str
    side: str
    limit_price: float
    quantity: int
    overnight_sentiment: float          # S_news in [-1.0, 1.0]
    pre_open_imbalance: float           # OI in [-1.0, 1.0]
    top_price: float                    # Theoretical Opening Price
    relative_spread: float              # Relative Bid-Ask spread
    action_taken: str                   # "RETAIN", "CANCEL", "MODIFY_PRICE", "PAUSE_SPREAD"
    fix_message_type: Optional[str]     # "35=F", "35=G", or None
    adjusted_price: Optional[float] = None
    reason: str = ""


class OvernightOrderAuditEngine:
    """
    Automated pre-open audit engine that protects queued orders against
    overnight disclosures and opening cross imbalances.
    """

    def __init__(
        self,
        sentiment_threshold: float = -0.40,
        imbalance_threshold: float = -0.50,
        top_slippage_threshold: float = 0.03,
        spread_pause_threshold: float = 0.08,
    ):
        self.sentiment_threshold = sentiment_threshold
        self.imbalance_threshold = imbalance_threshold
        self.top_slippage_threshold = top_slippage_threshold
        self.spread_pause_threshold = spread_pause_threshold

    @staticmethod
    def calculate_order_imbalance(bid_volume: int, ask_volume: int) -> float:
        """OI = (BidVol - AskVol) / (BidVol + AskVol)"""
        denom = bid_volume + ask_volume
        if denom == 0:
            return 0.0
        return (bid_volume - ask_volume) / float(denom)

    def evaluate_order(
        self,
        order: RoutedOrderRecord,
        sentiment: float,
        imbalance: float,
        top_price: float,
        relative_spread: float,
    ) -> PreOpenAuditAuditTicket:
        """
        Evaluates a single queued order against the multi-factor criteria.
        """
        cl_id = order.cl_ord_id
        side = order.side.upper()
        p_limit = order.limit_price

        # Check 1: BUY order with severe negative sentiment
        if side == "BUY" and sentiment < self.sentiment_threshold:
            return PreOpenAuditAuditTicket(
                cl_ord_id=cl_id,
                symbol=order.symbol,
                side=side,
                limit_price=p_limit,
                quantity=order.quantity,
                overnight_sentiment=sentiment,
                pre_open_imbalance=imbalance,
                top_price=top_price,
                relative_spread=relative_spread,
                action_taken="CANCEL",
                fix_message_type="35=F",
                reason=f"Overnight news sentiment ({sentiment:.2f}) < {self.sentiment_threshold}",
            )

        # Check 2: BUY order with severe supply imbalance
        if side == "BUY" and imbalance < self.imbalance_threshold:
            return PreOpenAuditAuditTicket(
                cl_ord_id=cl_id,
                symbol=order.symbol,
                side=side,
                limit_price=p_limit,
                quantity=order.quantity,
                overnight_sentiment=sentiment,
                pre_open_imbalance=imbalance,
                top_price=top_price,
                relative_spread=relative_spread,
                action_taken="CANCEL",
                fix_message_type="35=F",
                reason=f"Pre-open excess supply imbalance ({imbalance:.2f}) < {self.imbalance_threshold}",
            )

        # Check 3: Extreme Relative Spread (Extreme bid-ask friction)
        if relative_spread > self.spread_pause_threshold:
            return PreOpenAuditAuditTicket(
                cl_ord_id=cl_id,
                symbol=order.symbol,
                side=side,
                limit_price=p_limit,
                quantity=order.quantity,
                overnight_sentiment=sentiment,
                pre_open_imbalance=imbalance,
                top_price=top_price,
                relative_spread=relative_spread,
                action_taken="PAUSE_SPREAD",
                fix_message_type=None,
                reason=f"Relative spread ({relative_spread:.2%}) > {self.spread_pause_threshold:.2%}",
            )

        # Check 4: TOP Slippage > 3%
        if top_price > 0:
            slippage = abs(p_limit - top_price) / top_price
            if slippage > self.top_slippage_threshold:
                # Modify order limit price to TOP price
                return PreOpenAuditAuditTicket(
                    cl_ord_id=cl_id,
                    symbol=order.symbol,
                    side=side,
                    limit_price=p_limit,
                    quantity=order.quantity,
                    overnight_sentiment=sentiment,
                    pre_open_imbalance=imbalance,
                    top_price=top_price,
                    relative_spread=relative_spread,
                    action_taken="MODIFY_PRICE",
                    fix_message_type="35=G",
                    adjusted_price=round(top_price, 2),
                    reason=f"TOP slippage ({slippage:.2%}) > {self.top_slippage_threshold:.2%}",
                )

        # Check 5: Pass
        return PreOpenAuditAuditTicket(
            cl_ord_id=cl_id,
            symbol=order.symbol,
            side=side,
            limit_price=p_limit,
            quantity=order.quantity,
            overnight_sentiment=sentiment,
            pre_open_imbalance=imbalance,
            top_price=top_price,
            relative_spread=relative_spread,
            action_taken="RETAIN",
            fix_message_type=None,
            reason="All pre-open risk parameters within normal bounds",
        )

    def execute_pre_open_audit(
        self,
        router: MultiBrokerRouter,
        market_telemetry: Dict[str, Dict[str, Any]],
    ) -> List[PreOpenAuditAuditTicket]:
        """
        Executes pre-open audit across all active open orders in the MultiBrokerRouter blotter.
        Dispatches FIX 35=F (Cancel) or FIX 35=G (Replace) accordingly.
        """
        audit_results = []
        for cl_ord_id, order in list(router.order_blotter.items()):
            if order.status not in ["PENDING_NEW", "ACKNOWLEDGED", "REPLACED"]:
                continue

            symbol_data = market_telemetry.get(order.symbol, {})
            sentiment = symbol_data.get("sentiment", 0.0)
            imbalance = symbol_data.get("imbalance", 0.0)
            top_price = symbol_data.get("top_price", order.limit_price)
            rel_spread = symbol_data.get("relative_spread", 0.01)

            ticket = self.evaluate_order(order, sentiment, imbalance, top_price, rel_spread)
            audit_results.append(ticket)

            if ticket.action_taken == "CANCEL":
                logger.info(f"Pre-Open Audit CANCEL on {order.symbol} ({cl_ord_id}): {ticket.reason}")
                router.cancel_order(orig_cl_ord_id=cl_ord_id)
            elif ticket.action_taken == "MODIFY_PRICE" and ticket.adjusted_price is not None:
                logger.info(f"Pre-Open Audit MODIFY on {order.symbol} ({cl_ord_id}) to {ticket.adjusted_price}: {ticket.reason}")
                router.replace_order(
                    orig_cl_ord_id=cl_ord_id,
                    new_price=ticket.adjusted_price,
                    new_qty=order.quantity,
                )
            elif ticket.action_taken == "PAUSE_SPREAD":
                logger.info(f"Pre-Open Audit PAUSE on {order.symbol} ({cl_ord_id}): {ticket.reason}")
                order.status = "PAUSED_SPREAD"
                order.audit_notes.append(ticket.reason)

        return audit_results
