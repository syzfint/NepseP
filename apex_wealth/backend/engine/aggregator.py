"""
Pillar 1 — Multi-Account Aggregator & Lock Tracking Engine (`engine/aggregator.py`).

Responsibilities:
1. Multi-Account Consolidated Ledger:
   Computes available position vector x_available(t) across M sub-accounts:
     x_available(t) = x_gross(t) - x_settlement_lock(t) - x_promoter_lock(t)
2. Regulatory Clearing Safeguards:
   - T+2 Cash Lock Tracker: Enforces T_clear = t_exec + 2 days. Prevents recycling
     unsettled cash for secondary trade allocations if
       R_lock = (sum NAV_unsettled_T+2) / NAV_total > 0.30.
   - Promoter Share Lock-in Watch: Monitors 3-year mandatory lock-ins (e.g., Hydropower IPOs).
     Forces weight restriction w_i = 0 for locked assets and raises a
     `WARN_FUT_PROMOTER_CLIFF` alert 14 days prior to lock-in expiry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import uuid

import numpy as np

from database.models import (
    AccountType,
    DematBOID,
    InvestorVault,
    SettlementLock,
    SubAccount,
    TaxLot,
    TMSAccount,
)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class PromoterCliffWarning:
    """Alert emitted when a promoter lock-in lot is within the 14-day expiry window."""

    code: str
    symbol: str
    boid_id: str
    lot_id: str
    locked_quantity: int
    lock_expiry_date: str
    days_remaining: float
    forced_weight_restriction: float
    message: str


@dataclass
class SubAccountPositionSummary:
    """Aggregated position & cash state for an individual SubAccount."""

    account_id: str
    account_type: str
    account_label: str
    broker_code: str
    tms_client_code: str
    boid_id: str
    cash_balance: float
    unsettled_cash_locked: float
    available_cash: float
    available_equity: float
    gross_positions: Dict[str, int]
    settlement_locked_positions: Dict[str, int]
    promoter_locked_positions: Dict[str, int]
    available_positions: Dict[str, int]


@dataclass
class ConsolidatedVaultLedger:
    """Consolidated multi-account position vectors, NAV breakdown, and clearing safeguards."""

    vault_id: str
    vault_name: str
    as_of_timestamp: str
    symbols: List[str]
    x_gross: Dict[str, int]
    x_settlement_lock: Dict[str, int]
    x_promoter_lock: Dict[str, int]
    x_available: Dict[str, int]
    x_gross_vector: List[int]
    x_settlement_lock_vector: List[int]
    x_promoter_lock_vector: List[int]
    x_available_vector: List[int]
    total_cash: float
    unsettled_cash_t2: float
    available_cash: float
    total_equity_market_value: float
    locked_shares_market_value: float
    nav_total: float
    r_lock_ratio: float
    c_locked_ratio: float
    s_locked_ratio: float
    is_secondary_allocation_blocked: bool
    weight_restrictions: Dict[str, Optional[float]]
    promoter_cliff_warnings: List[PromoterCliffWarning] = field(default_factory=list)
    sub_account_summaries: List[SubAccountPositionSummary] = field(default_factory=list)


class MultiAccountAggregator:
    """
    Institutional Multi-Account Consolidated Ledger & Lock Tracking Engine.
    """

    MAX_T2_LOCK_RATIO: float = 0.30
    PROMOTER_CLIFF_DAYS_THRESHOLD: int = 14

    def __init__(self, reference_time: Optional[datetime] = None) -> None:
        self.reference_time: datetime = _ensure_utc(
            reference_time or datetime.now(timezone.utc)
        )

    def consolidate_vault(
        self,
        vault: InvestorVault,
        market_prices: Dict[str, float],
        reference_time: Optional[datetime] = None,
    ) -> ConsolidatedVaultLedger:
        """
        Compute the consolidated multi-account ledger and position vectors across M sub-accounts:
            x_available(t) = x_gross(t) - x_settlement_lock(t) - x_promoter_lock(t)

        Also evaluates T+2 settlement cash lock ratio R_lock and 3-year promoter lock-in cliffs.
        """
        ref_time = _ensure_utc(reference_time or self.reference_time)

        all_symbols_set = set(market_prices.keys())
        for sub in vault.sub_accounts:
            for boid in sub.demat_boids:
                for lot in boid.tax_lots:
                    all_symbols_set.add(lot.symbol)
            for lock in sub.settlement_locks:
                all_symbols_set.add(lock.symbol)

        symbols = sorted(all_symbols_set)
        x_gross: Dict[str, int] = {sym: 0 for sym in symbols}
        x_settlement_lock: Dict[str, int] = {sym: 0 for sym in symbols}
        x_promoter_lock: Dict[str, int] = {sym: 0 for sym in symbols}
        x_available: Dict[str, int] = {sym: 0 for sym in symbols}

        total_cash = 0.0
        unsettled_cash_t2 = 0.0
        promoter_warnings: List[PromoterCliffWarning] = []
        weight_restrictions: Dict[str, Optional[float]] = {}
        sub_summaries: List[SubAccountPositionSummary] = []

        for sub in vault.sub_accounts:
            sub_gross: Dict[str, int] = {sym: 0 for sym in symbols}
            sub_settle_lock: Dict[str, int] = {sym: 0 for sym in symbols}
            sub_promoter_lock: Dict[str, int] = {sym: 0 for sym in symbols}

            sub_unsettled_cash = 0.0
            for s_lock in sub.settlement_locks:
                if s_lock.is_active(ref_time):
                    sub_settle_lock[s_lock.symbol] = (
                        sub_settle_lock.get(s_lock.symbol, 0) + int(s_lock.quantity)
                    )
                    sub_unsettled_cash += float(s_lock.unsettled_cash_amount)

            primary_boid = sub.demat_boids[0].boid_id if sub.demat_boids else "1301000000000000"
            primary_broker = (
                sub.tms_accounts[0].broker_code if sub.tms_accounts else "58"
            )
            primary_client_code = (
                sub.tms_accounts[0].tms_client_code if sub.tms_accounts else "NEPSE-INST-01"
            )

            for boid in sub.demat_boids:
                for lot in boid.tax_lots:
                    sym = lot.symbol
                    qty = int(lot.quantity)
                    sub_gross[sym] = sub_gross.get(sym, 0) + qty

                    if lot.is_currently_promoter_locked(ref_time):
                        sub_promoter_lock[sym] = sub_promoter_lock.get(sym, 0) + qty
                        weight_restrictions[sym] = 0.0

                        if lot.lock_expiry_date is not None:
                            expiry_utc = _ensure_utc(lot.lock_expiry_date)
                            days_rem = (expiry_utc - ref_time).total_seconds() / 86400.0
                            if 0.0 <= days_rem <= float(self.PROMOTER_CLIFF_DAYS_THRESHOLD):
                                promoter_warnings.append(
                                    PromoterCliffWarning(
                                        code="WARN_FUT_PROMOTER_CLIFF",
                                        symbol=sym,
                                        boid_id=boid.boid_id,
                                        lot_id=str(lot.lot_id),
                                        locked_quantity=qty,
                                        lock_expiry_date=expiry_utc.isoformat(),
                                        days_remaining=round(days_rem, 2),
                                        forced_weight_restriction=0.0,
                                        message=(
                                            f"Promoter share lock-in cliff for {sym} (BOID {boid.boid_id}, "
                                            f"{qty:,} shares) expires in {days_rem:.1f} days "
                                            f"({expiry_utc.date().isoformat()}). Weight forced w_{sym}=0."
                                        ),
                                    )
                                )

            sub_avail: Dict[str, int] = {}
            for sym in symbols:
                avail_qty = max(
                    0,
                    sub_gross[sym] - sub_settle_lock[sym] - sub_promoter_lock[sym],
                )
                sub_avail[sym] = avail_qty
                x_gross[sym] += sub_gross[sym]
                x_settlement_lock[sym] += sub_settle_lock[sym]
                x_promoter_lock[sym] += sub_promoter_lock[sym]
                x_available[sym] += avail_qty

            total_cash += float(sub.cash_balance)
            unsettled_cash_t2 += sub_unsettled_cash
            sub_avail_cash = max(0.0, float(sub.cash_balance) - sub_unsettled_cash)

            # Calculate sub-account available equity dynamically if market prices exist
            sub_avail_mkt_val = sum(
                sub_avail[sym] * float(market_prices.get(sym, 0.0)) for sym in symbols
            )
            computed_avail_equity = max(
                float(sub.available_equity),
                sub_avail_cash + sub_avail_mkt_val,
            )

            sub_summaries.append(
                SubAccountPositionSummary(
                    account_id=str(sub.account_id),
                    account_type=(
                        sub.account_type.value
                        if isinstance(sub.account_type, AccountType)
                        else str(sub.account_type)
                    ),
                    account_label=sub.account_label,
                    broker_code=primary_broker,
                    tms_client_code=primary_client_code,
                    boid_id=primary_boid,
                    cash_balance=round(float(sub.cash_balance), 2),
                    unsettled_cash_locked=round(sub_unsettled_cash, 2),
                    available_cash=round(sub_avail_cash, 2),
                    available_equity=round(computed_avail_equity, 2),
                    gross_positions={k: v for k, v in sub_gross.items() if v > 0},
                    settlement_locked_positions={
                        k: v for k, v in sub_settle_lock.items() if v > 0
                    },
                    promoter_locked_positions={
                        k: v for k, v in sub_promoter_lock.items() if v > 0
                    },
                    available_positions={k: v for k, v in sub_avail.items() if v > 0},
                )
            )

        # Compute consolidated market values and ratios
        total_gross_shares = sum(x_gross.values())
        total_locked_shares = sum(
            min(x_gross[s], x_settlement_lock[s] + x_promoter_lock[s]) for s in symbols
        )

        total_equity_mv = sum(
            x_gross[s] * float(market_prices.get(s, 0.0)) for s in symbols
        )
        locked_shares_mv = sum(
            (x_settlement_lock[s] + x_promoter_lock[s]) * float(market_prices.get(s, 0.0))
            for s in symbols
        )
        settle_locked_shares_mv = sum(
            x_settlement_lock[s] * float(market_prices.get(s, 0.0)) for s in symbols
        )

        nav_total = max(1.0, total_cash + total_equity_mv)
        nav_unsettled_t2 = unsettled_cash_t2 + settle_locked_shares_mv
        r_lock_ratio = float(np.clip(nav_unsettled_t2 / nav_total, 0.0, 1.0))

        c_locked_ratio = (
            float(np.clip(unsettled_cash_t2 / max(1.0, total_cash), 0.0, 1.0))
            if total_cash > 0
            else 0.0
        )
        s_locked_ratio = (
            float(np.clip(total_locked_shares / max(1, total_gross_shares), 0.0, 1.0))
            if total_gross_shares > 0
            else float(np.clip(locked_shares_mv / max(1.0, total_equity_mv), 0.0, 1.0))
        )

        # If any symbol has all gross shares locked by promoter lock or active promoter lock lot, force w_i = 0
        for sym in symbols:
            if x_promoter_lock[sym] > 0:
                weight_restrictions[sym] = 0.0

        return ConsolidatedVaultLedger(
            vault_id=str(vault.vault_id),
            vault_name=vault.name,
            as_of_timestamp=ref_time.isoformat(),
            symbols=symbols,
            x_gross=x_gross,
            x_settlement_lock=x_settlement_lock,
            x_promoter_lock=x_promoter_lock,
            x_available=x_available,
            x_gross_vector=[x_gross[s] for s in symbols],
            x_settlement_lock_vector=[x_settlement_lock[s] for s in symbols],
            x_promoter_lock_vector=[x_promoter_lock[s] for s in symbols],
            x_available_vector=[x_available[s] for s in symbols],
            total_cash=round(total_cash, 2),
            unsettled_cash_t2=round(unsettled_cash_t2, 2),
            available_cash=round(max(0.0, total_cash - unsettled_cash_t2), 2),
            total_equity_market_value=round(total_equity_mv, 2),
            locked_shares_market_value=round(locked_shares_mv, 2),
            nav_total=round(nav_total, 2),
            r_lock_ratio=round(r_lock_ratio, 4),
            c_locked_ratio=round(c_locked_ratio, 4),
            s_locked_ratio=round(s_locked_ratio, 4),
            is_secondary_allocation_blocked=(r_lock_ratio > self.MAX_T2_LOCK_RATIO),
            weight_restrictions=weight_restrictions,
            promoter_cliff_warnings=promoter_warnings,
            sub_account_summaries=sub_summaries,
        )

    def can_allocate_secondary_trade(
        self,
        ledger: ConsolidatedVaultLedger,
        proposed_cash_commitment: float = 0.0,
    ) -> Tuple[bool, str]:
        """
        Verify whether secondary trade allocation is permitted under the T+2 Cash Lock safeguard:
            R_lock = (sum NAV_unsettled_T+2) / NAV_total <= 0.30
        and ensure proposed cash does not consume unsettled T+2 proceeds.
        """
        if ledger.r_lock_ratio > self.MAX_T2_LOCK_RATIO:
            return (
                False,
                (
                    f"Blocked by T+2 Cash Lock Safeguard: R_lock={ledger.r_lock_ratio:.2%} "
                    f"exceeds 30.00% regulatory ceiling."
                ),
            )
        if proposed_cash_commitment > ledger.available_cash:
            return (
                False,
                (
                    f"Blocked by T+2 Settlement Lock: Proposed commitment NPR {proposed_cash_commitment:,.2f} "
                    f"exceeds settled available cash NPR {ledger.available_cash:,.2f} "
                    f"(NPR {ledger.unsettled_cash_t2:,.2f} locked in T+2 clearing)."
                ),
            )
        return True, "ELIGIBLE_FOR_EXECUTION"


def create_default_institutional_vault(
    reference_time: Optional[datetime] = None,
) -> Tuple[InvestorVault, Dict[str, float]]:
    """
    Construct a rich, realistic 4-sub-account Institutional InvestorVault
    spanning Personal, Family, Corporate, and Trust legal entities across Brokers 58, 45, 34, and 49
    with 16-digit CDSC BOIDs, LTCGT/STCGT tax lots, T+2 settlement locks, and a Hydropower IPO
    promoter share lock-in cliff (UPPER) expiring in 11 days.
    """
    ref = _ensure_utc(reference_time or datetime.now(timezone.utc))

    market_prices: Dict[str, float] = {
        "NABIL": 1245.0,
        "NICA": 890.0,
        "SCB": 612.0,
        "CHDC": 1620.0,
        "HIDCL": 324.0,
        "UPPER": 215.0,
        "SHIVM": 595.0,
        "NTC": 945.0,
        "NRIC": 780.0,
        "HDL": 1980.0,
        "GBIME": 248.0,
        "SANIMA": 312.0,
        "EBL": 584.0,
        "CIT": 2340.0,
        "BPCL": 410.0,
        "API": 204.0,
    }

    vault = InvestorVault(
        vault_id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
        name="Sovereign Himalaya Multi-Family & Institutional Vault",
        created_at=ref - timedelta(days=950),
        risk_profile="INSTITUTIONAL_QUANT",
    )

    # Sub-Account 1: Personal Sovereign Account (Broker 58 - Naasa Securities)
    sub_personal = SubAccount(
        account_id=uuid.UUID("a1111111-0000-0000-0000-000000000001"),
        vault_id=vault.vault_id,
        account_type=AccountType.PERSONAL,
        account_label="Personal Alpha Desk (TMS #58)",
        cash_balance=4_250_000.0,
        available_equity=18_400_000.0,
    )
    tms_58 = TMSAccount(
        tms_id=uuid.UUID("b1111111-0000-0000-0000-000000000058"),
        sub_account_id=sub_personal.account_id,
        broker_code="58",
        tms_client_code="TMS58-NP-99401",
        encrypted_session_token="aes256gcm:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    )
    boid_personal = DematBOID(
        boid_id="1301010000482910",
        sub_account_id=sub_personal.account_id,
        tms_id=tms_58.tms_id,
        dp_name="Global IME Capital Ltd (DP 10100)",
        total_demat_shares=12_800,
    )
    boid_personal.tax_lots = [
        # NABIL: Tax-loss harvest lot + LTCGT lot + STCGT lot
        TaxLot(
            boid_id=boid_personal.boid_id,
            symbol="NABIL",
            quantity=1200,
            purchase_price=1310.0,  # Loss lot (cost > current 1245)
            purchase_date=ref - timedelta(days=210),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_personal.boid_id,
            symbol="NABIL",
            quantity=2800,
            purchase_price=980.0,  # Long-term CGT lot (5.0%, >365d)
            purchase_date=ref - timedelta(days=540),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_personal.boid_id,
            symbol="NABIL",
            quantity=600,
            purchase_price=1120.0,  # Short-term CGT lot (7.5%, <=365d)
            purchase_date=ref - timedelta(days=95),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_personal.boid_id,
            symbol="SCB",
            quantity=4200,
            purchase_price=515.0,
            purchase_date=ref - timedelta(days=480),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_personal.boid_id,
            symbol="NTC",
            quantity=4000,
            purchase_price=885.0,
            purchase_date=ref - timedelta(days=620),
            is_promoter_locked=False,
        ),
    ]
    sub_personal.tms_accounts = [tms_58]
    sub_personal.demat_boids = [boid_personal]
    sub_personal.settlement_locks = [
        SettlementLock(
            sub_account_id=sub_personal.account_id,
            symbol="SCB",
            quantity=400,
            unsettled_cash_amount=650_000.0,
            execution_timestamp=ref - timedelta(hours=18),
            clearing_expiry_timestamp=ref + timedelta(hours=30),
        )
    ]

    # Sub-Account 2: Family Office Trust Account (Broker 45 - Imperial Securities)
    sub_family = SubAccount(
        account_id=uuid.UUID("a2222222-0000-0000-0000-000000000002"),
        vault_id=vault.vault_id,
        account_type=AccountType.FAMILY,
        account_label="Family Endowment Trust (TMS #45)",
        cash_balance=5_800_000.0,
        available_equity=24_600_000.0,
    )
    tms_45 = TMSAccount(
        tms_id=uuid.UUID("b2222222-0000-0000-0000-000000000045"),
        sub_account_id=sub_family.account_id,
        broker_code="45",
        tms_client_code="TMS45-FAM-21084",
        encrypted_session_token="aes256gcm:4a44dc15364204a80fe80e9039455cc1608281820fe2b24f1e5233ade6af1dd5",
    )
    boid_family = DematBOID(
        boid_id="1301060001928374",
        sub_account_id=sub_family.account_id,
        tms_id=tms_45.tms_id,
        dp_name="Nabil Investment Banking Ltd (DP 10600)",
        total_demat_shares=19_500,
    )
    boid_family.tax_lots = [
        TaxLot(
            boid_id=boid_family.boid_id,
            symbol="CHDC",
            quantity=5500,
            purchase_price=1340.0,
            purchase_date=ref - timedelta(days=430),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_family.boid_id,
            symbol="NICA",
            quantity=6000,
            purchase_price=940.0,  # Tax-loss harvest candidate (cost 940 > LTP 890)
            purchase_date=ref - timedelta(days=390),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_family.boid_id,
            symbol="SHIVM",
            quantity=5000,
            purchase_price=520.0,
            purchase_date=ref - timedelta(days=510),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_family.boid_id,
            symbol="CIT",
            quantity=3000,
            purchase_price=2080.0,
            purchase_date=ref - timedelta(days=700),
            is_promoter_locked=False,
        ),
    ]
    sub_family.tms_accounts = [tms_45]
    sub_family.demat_boids = [boid_family]
    sub_family.settlement_locks = [
        SettlementLock(
            sub_account_id=sub_family.account_id,
            symbol="CHDC",
            quantity=300,
            unsettled_cash_amount=920_000.0,
            execution_timestamp=ref - timedelta(hours=11),
            clearing_expiry_timestamp=ref + timedelta(hours=37),
        )
    ]

    # Sub-Account 3: Corporate Treasury Account (Broker 34 - Vision Securities)
    sub_corporate = SubAccount(
        account_id=uuid.UUID("a3333333-0000-0000-0000-000000000003"),
        vault_id=vault.vault_id,
        account_type=AccountType.CORPORATE,
        account_label="Himalaya Quantitative Corp Treasury (TMS #34)",
        cash_balance=9_400_000.0,
        available_equity=36_200_000.0,
    )
    tms_34 = TMSAccount(
        tms_id=uuid.UUID("b3333333-0000-0000-0000-000000000034"),
        sub_account_id=sub_corporate.account_id,
        broker_code="34",
        tms_client_code="TMS34-CORP-77012",
        encrypted_session_token="aes256gcm:7902699be42c8a8e46fbbb4501726517e86b22c56a189f7625a6da49081b2451",
    )
    boid_corporate = DematBOID(
        boid_id="1301120004455667",
        sub_account_id=sub_corporate.account_id,
        tms_id=tms_34.tms_id,
        dp_name="NIMB Ace Capital Ltd (DP 11200)",
        total_demat_shares=38_000,
    )
    boid_corporate.tax_lots = [
        TaxLot(
            boid_id=boid_corporate.boid_id,
            symbol="NRIC",
            quantity=9500,
            purchase_price=690.0,
            purchase_date=ref - timedelta(days=450),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_corporate.boid_id,
            symbol="HDL",
            quantity=4500,
            purchase_price=2110.0,  # Tax-loss harvest candidate
            purchase_date=ref - timedelta(days=310),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_corporate.boid_id,
            symbol="HIDCL",
            quantity=14000,
            purchase_price=260.0,
            purchase_date=ref - timedelta(days=590),
            is_promoter_locked=False,
        ),
        # 3-Year Hydropower Promoter Lock-in Lot expiring in 11 days!
        TaxLot(
            boid_id=boid_corporate.boid_id,
            symbol="UPPER",
            quantity=10000,
            purchase_price=100.0,
            purchase_date=ref - timedelta(days=1084),  # ~3 years ago
            is_promoter_locked=True,
            lock_expiry_date=ref + timedelta(days=11),  # Triggers WARN_FUT_PROMOTER_CLIFF (<= 14 days)
        ),
    ]
    sub_corporate.tms_accounts = [tms_34]
    sub_corporate.demat_boids = [boid_corporate]
    sub_corporate.settlement_locks = [
        SettlementLock(
            sub_account_id=sub_corporate.account_id,
            symbol="NRIC",
            quantity=500,
            unsettled_cash_amount=1_180_000.0,
            execution_timestamp=ref - timedelta(hours=6),
            clearing_expiry_timestamp=ref + timedelta(hours=42),
        )
    ]

    # Sub-Account 4: Sovereign Institutional Sub-Fund (Broker 49 - Online Securities)
    sub_trust = SubAccount(
        account_id=uuid.UUID("a4444444-0000-0000-0000-000000000004"),
        vault_id=vault.vault_id,
        account_type=AccountType.CORPORATE,
        account_label="Sovereign Co-Investment Feeder (TMS #49)",
        cash_balance=3_650_000.0,
        available_equity=15_800_000.0,
    )
    tms_49 = TMSAccount(
        tms_id=uuid.UUID("b4444444-0000-0000-0000-000000000049"),
        sub_account_id=sub_trust.account_id,
        broker_code="49",
        tms_client_code="TMS49-INST-55190",
        encrypted_session_token="aes256gcm:2c624232cdd221771294dfbb310aca000a0df6ac8b66b696d90ef06fdefb64a3",
    )
    boid_trust = DematBOID(
        boid_id="1301170008877665",
        sub_account_id=sub_trust.account_id,
        tms_id=tms_49.tms_id,
        dp_name="Siddhartha Capital Ltd (DP 11700)",
        total_demat_shares=24_200,
    )
    boid_trust.tax_lots = [
        TaxLot(
            boid_id=boid_trust.boid_id,
            symbol="EBL",
            quantity=8200,
            purchase_price=510.0,
            purchase_date=ref - timedelta(days=490),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_trust.boid_id,
            symbol="SANIMA",
            quantity=9000,
            purchase_price=285.0,
            purchase_date=ref - timedelta(days=410),
            is_promoter_locked=False,
        ),
        TaxLot(
            boid_id=boid_trust.boid_id,
            symbol="GBIME",
            quantity=7000,
            purchase_price=232.0,
            purchase_date=ref - timedelta(days=520),
            is_promoter_locked=False,
        ),
    ]
    sub_trust.tms_accounts = [tms_49]
    sub_trust.demat_boids = [boid_trust]
    sub_trust.settlement_locks = [
        SettlementLock(
            sub_account_id=sub_trust.account_id,
            symbol="EBL",
            quantity=200,
            unsettled_cash_amount=390_000.0,
            execution_timestamp=ref - timedelta(hours=22),
            clearing_expiry_timestamp=ref + timedelta(hours=26),
        )
    ]

    vault.sub_accounts = [sub_personal, sub_family, sub_corporate, sub_trust]
    return vault, market_prices
