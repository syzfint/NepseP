"""
SQLAlchemy ORM & Pure-Python Fallback Domain Models for Apex Wealth PMS (Pillar 1).

Entities:
- InvestorVault: Aggregates multiple sub-accounts across distinct legal entities.
- SubAccount: Legal sub-account (PERSONAL, FAMILY, CORPORATE, TRUST) holding cash & equity.
- TMSAccount: Connects to multiple brokerage endpoints (e.g., Broker 58, 45, 34) with isolated socket credentials.
- DematBOID: 16-digit CDSC Demat Beneficiary Owner Identifier mapping physical share depository accounts.
- TaxLot: Granular acquisition lot per BOID & symbol with computed holding_days, CGT rate tier, and promoter lock tracking.
- SettlementLock: T+2 clearing cash and share lock tracker enforcing T_clear = t_exec + 2 days.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from .connection import Base, HAS_SQLALCHEMY


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AccountType(str, enum.Enum):
    PERSONAL = "PERSONAL"
    FAMILY = "FAMILY"
    CORPORATE = "CORPORATE"
    TRUST = "TRUST"


class RiskProfile(str, enum.Enum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    INSTITUTIONAL_QUANT = "INSTITUTIONAL_QUANT"
    SOVEREIGN_ALPHA = "SOVEREIGN_ALPHA"


if HAS_SQLALCHEMY:
    from sqlalchemy import (
        Boolean,
        CheckConstraint,
        DateTime,
        Enum,
        Float,
        ForeignKey,
        Index,
        Integer,
        String,
        Uuid,
    )
    from sqlalchemy.ext.hybrid import hybrid_property
    from sqlalchemy.orm import Mapped, mapped_column, relationship

    class InvestorVault(Base):
        """Master Investor Vault aggregating multiple sub-accounts across legal entities."""

        __tablename__ = "investor_vaults"

        vault_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
        name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            nullable=False,
            default=_utc_now,
        )
        risk_profile: Mapped[str] = mapped_column(
            String(64),
            nullable=False,
            default=RiskProfile.INSTITUTIONAL_QUANT.value,
        )

        sub_accounts: Mapped[List["SubAccount"]] = relationship(
            "SubAccount",
            back_populates="vault",
            cascade="all, delete-orphan",
            lazy="selectin",
        )

    class SubAccount(Base):
        """Sub-account tied to a legal entity within an InvestorVault."""

        __tablename__ = "sub_accounts"
        __table_args__ = (
            CheckConstraint("cash_balance >= 0.0", name="ck_sub_account_non_negative_cash"),
            CheckConstraint("available_equity >= 0.0", name="ck_sub_account_non_negative_equity"),
        )

        account_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
        vault_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            ForeignKey("investor_vaults.vault_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        account_type: Mapped[AccountType] = mapped_column(
            Enum(AccountType, native_enum=False),
            nullable=False,
            default=AccountType.PERSONAL,
        )
        account_label: Mapped[str] = mapped_column(
            String(128),
            nullable=False,
            default="Primary Account",
        )
        cash_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
        available_equity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

        vault: Mapped["InvestorVault"] = relationship("InvestorVault", back_populates="sub_accounts")
        tms_accounts: Mapped[List["TMSAccount"]] = relationship(
            "TMSAccount",
            back_populates="sub_account",
            cascade="all, delete-orphan",
            lazy="selectin",
        )
        demat_boids: Mapped[List["DematBOID"]] = relationship(
            "DematBOID",
            back_populates="sub_account",
            cascade="all, delete-orphan",
            lazy="selectin",
        )
        settlement_locks: Mapped[List["SettlementLock"]] = relationship(
            "SettlementLock",
            back_populates="sub_account",
            cascade="all, delete-orphan",
            lazy="selectin",
        )

    class TMSAccount(Base):
        """Broker Trading Management System (TMS) endpoint credentials & routing configuration."""

        __tablename__ = "tms_accounts"

        tms_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
        sub_account_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            ForeignKey("sub_accounts.account_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        broker_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
        tms_client_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
        encrypted_session_token: Mapped[str] = mapped_column(String(512), nullable=False)

        sub_account: Mapped["SubAccount"] = relationship("SubAccount", back_populates="tms_accounts")
        demat_boids: Mapped[List["DematBOID"]] = relationship(
            "DematBOID",
            back_populates="tms_account",
            cascade="all, delete-orphan",
            lazy="selectin",
        )

    class DematBOID(Base):
        """16-Digit CDSC Demat Beneficiary Owner Identifier mapped to a SubAccount and TMSAccount."""

        __tablename__ = "demat_boids"
        __table_args__ = (
            CheckConstraint("length(boid_id) = 16", name="ck_demat_boid_16_digits"),
            CheckConstraint("total_demat_shares >= 0", name="ck_demat_total_shares_non_negative"),
        )

        boid_id: Mapped[str] = mapped_column(String(16), primary_key=True)
        sub_account_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            ForeignKey("sub_accounts.account_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        tms_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            ForeignKey("tms_accounts.tms_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        dp_name: Mapped[str] = mapped_column(String(128), nullable=False)
        total_demat_shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

        sub_account: Mapped["SubAccount"] = relationship("SubAccount", back_populates="demat_boids")
        tms_account: Mapped["TMSAccount"] = relationship("TMSAccount", back_populates="demat_boids")
        tax_lots: Mapped[List["TaxLot"]] = relationship(
            "TaxLot",
            back_populates="demat_boid",
            cascade="all, delete-orphan",
            lazy="selectin",
        )

    class TaxLot(Base):
        """Individual share acquisition tax lot with holding period & promoter lock-in tracking."""

        __tablename__ = "tax_lots"
        __table_args__ = (
            CheckConstraint("quantity >= 0", name="ck_tax_lot_quantity_non_negative"),
            CheckConstraint("purchase_price > 0.0", name="ck_tax_lot_positive_purchase_price"),
            Index("ix_tax_lots_boid_symbol", "boid_id", "symbol"),
        )

        lot_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
        boid_id: Mapped[str] = mapped_column(
            String(16),
            ForeignKey("demat_boids.boid_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
        quantity: Mapped[int] = mapped_column(Integer, nullable=False)
        purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
        purchase_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
        is_promoter_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
        lock_expiry_date: Mapped[Optional[datetime]] = mapped_column(
            DateTime(timezone=True),
            nullable=True,
        )

        demat_boid: Mapped["DematBOID"] = relationship("DematBOID", back_populates="tax_lots")

        def compute_holding_days(self, reference_time: Optional[datetime] = None) -> int:
            ref = reference_time or _utc_now()
            p_date = self.purchase_date
            if p_date.tzinfo is None:
                p_date = p_date.replace(tzinfo=timezone.utc)
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            return max(0, (ref - p_date).days)

        @hybrid_property
        def holding_days(self) -> int:
            return self.compute_holding_days()

        @hybrid_property
        def cgt_tax_rate(self) -> float:
            return 0.050 if self.holding_days > 365 else 0.075

        def is_currently_promoter_locked(self, reference_time: Optional[datetime] = None) -> bool:
            if not self.is_promoter_locked:
                return False
            if self.lock_expiry_date is None:
                return True
            ref = reference_time or _utc_now()
            expiry = self.lock_expiry_date
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            return ref < expiry

    class SettlementLock(Base):
        """T+2 CDSC clearing and cash settlement lock tracker."""

        __tablename__ = "settlement_locks"
        __table_args__ = (
            CheckConstraint("quantity >= 0", name="ck_settlement_lock_non_negative_qty"),
            CheckConstraint("unsettled_cash_amount >= 0.0", name="ck_settlement_lock_non_negative_cash"),
            Index("ix_settlement_locks_sub_symbol", "sub_account_id", "symbol"),
        )

        lock_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
        sub_account_id: Mapped[uuid.UUID] = mapped_column(
            Uuid(as_uuid=True),
            ForeignKey("sub_accounts.account_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
        quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
        unsettled_cash_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
        execution_timestamp: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            nullable=False,
            default=_utc_now,
        )
        clearing_expiry_timestamp: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            nullable=False,
        )

        sub_account: Mapped["SubAccount"] = relationship("SubAccount", back_populates="settlement_locks")

        def __init__(self, **kwargs: Any) -> None:
            exec_ts = kwargs.get("execution_timestamp") or _utc_now()
            if exec_ts.tzinfo is None:
                exec_ts = exec_ts.replace(tzinfo=timezone.utc)
            kwargs["execution_timestamp"] = exec_ts
            if "clearing_expiry_timestamp" not in kwargs or kwargs["clearing_expiry_timestamp"] is None:
                kwargs["clearing_expiry_timestamp"] = exec_ts + timedelta(days=2)
            super().__init__(**kwargs)

        def is_active(self, reference_time: Optional[datetime] = None) -> bool:
            ref = reference_time or _utc_now()
            expiry = self.clearing_expiry_timestamp
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            return ref < expiry

else:
    # Pure-Python domain objects when SQLAlchemy is not installed in the active Python environment
    class InvestorVault(Base):  # type: ignore[no-redef]
        def __init__(
            self,
            vault_id: Optional[uuid.UUID] = None,
            name: str = "Master Sovereign Vault",
            created_at: Optional[datetime] = None,
            risk_profile: str = RiskProfile.INSTITUTIONAL_QUANT.value,
            sub_accounts: Optional[List["SubAccount"]] = None,
            **kwargs: Any,
        ) -> None:
            self.vault_id = vault_id or uuid.uuid4()
            self.name = name
            self.created_at = created_at or _utc_now()
            self.risk_profile = risk_profile
            self.sub_accounts: List["SubAccount"] = list(sub_accounts) if sub_accounts else []
            for k, v in kwargs.items():
                setattr(self, k, v)

    class SubAccount(Base):  # type: ignore[no-redef]
        def __init__(
            self,
            account_id: Optional[uuid.UUID] = None,
            vault_id: Optional[uuid.UUID] = None,
            account_type: AccountType = AccountType.PERSONAL,
            account_label: str = "Primary Account",
            cash_balance: float = 0.0,
            available_equity: float = 0.0,
            tms_accounts: Optional[List["TMSAccount"]] = None,
            demat_boids: Optional[List["DematBOID"]] = None,
            settlement_locks: Optional[List["SettlementLock"]] = None,
            **kwargs: Any,
        ) -> None:
            self.account_id = account_id or uuid.uuid4()
            self.vault_id = vault_id or uuid.uuid4()
            self.account_type = account_type if isinstance(account_type, AccountType) else AccountType(str(account_type))
            self.account_label = account_label
            self.cash_balance = float(cash_balance)
            self.available_equity = float(available_equity)
            self.tms_accounts: List["TMSAccount"] = list(tms_accounts) if tms_accounts else []
            self.demat_boids: List["DematBOID"] = list(demat_boids) if demat_boids else []
            self.settlement_locks: List["SettlementLock"] = list(settlement_locks) if settlement_locks else []
            for k, v in kwargs.items():
                setattr(self, k, v)

    class TMSAccount(Base):  # type: ignore[no-redef]
        def __init__(
            self,
            tms_id: Optional[uuid.UUID] = None,
            sub_account_id: Optional[uuid.UUID] = None,
            broker_code: str = "58",
            tms_client_code: str = "",
            encrypted_session_token: str = "",
            demat_boids: Optional[List["DematBOID"]] = None,
            **kwargs: Any,
        ) -> None:
            self.tms_id = tms_id or uuid.uuid4()
            self.sub_account_id = sub_account_id or uuid.uuid4()
            self.broker_code = broker_code
            self.tms_client_code = tms_client_code
            self.encrypted_session_token = encrypted_session_token
            self.demat_boids: List["DematBOID"] = list(demat_boids) if demat_boids else []
            for k, v in kwargs.items():
                setattr(self, k, v)

    class DematBOID(Base):  # type: ignore[no-redef]
        def __init__(
            self,
            boid_id: str,
            sub_account_id: Optional[uuid.UUID] = None,
            tms_id: Optional[uuid.UUID] = None,
            dp_name: str = "CDSC Depository",
            total_demat_shares: int = 0,
            tax_lots: Optional[List["TaxLot"]] = None,
            **kwargs: Any,
        ) -> None:
            self.boid_id = str(boid_id)
            self.sub_account_id = sub_account_id or uuid.uuid4()
            self.tms_id = tms_id or uuid.uuid4()
            self.dp_name = dp_name
            self.total_demat_shares = int(total_demat_shares)
            self.tax_lots: List["TaxLot"] = list(tax_lots) if tax_lots else []
            for k, v in kwargs.items():
                setattr(self, k, v)

    class TaxLot(Base):  # type: ignore[no-redef]
        def __init__(
            self,
            boid_id: str,
            symbol: str,
            quantity: int,
            purchase_price: float,
            purchase_date: datetime,
            lot_id: Optional[uuid.UUID] = None,
            is_promoter_locked: bool = False,
            lock_expiry_date: Optional[datetime] = None,
            **kwargs: Any,
        ) -> None:
            self.lot_id = lot_id or uuid.uuid4()
            self.boid_id = str(boid_id)
            self.symbol = str(symbol)
            self.quantity = int(quantity)
            self.purchase_price = float(purchase_price)
            self.purchase_date = purchase_date
            self.is_promoter_locked = bool(is_promoter_locked)
            self.lock_expiry_date = lock_expiry_date
            for k, v in kwargs.items():
                setattr(self, k, v)

        def compute_holding_days(self, reference_time: Optional[datetime] = None) -> int:
            ref = reference_time or _utc_now()
            p_date = self.purchase_date
            if p_date.tzinfo is None:
                p_date = p_date.replace(tzinfo=timezone.utc)
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            return max(0, (ref - p_date).days)

        @property
        def holding_days(self) -> int:
            return self.compute_holding_days()

        @property
        def cgt_tax_rate(self) -> float:
            return 0.050 if self.holding_days > 365 else 0.075

        def is_currently_promoter_locked(self, reference_time: Optional[datetime] = None) -> bool:
            if not self.is_promoter_locked:
                return False
            if self.lock_expiry_date is None:
                return True
            ref = reference_time or _utc_now()
            expiry = self.lock_expiry_date
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            return ref < expiry

    class SettlementLock(Base):  # type: ignore[no-redef]
        def __init__(
            self,
            sub_account_id: Optional[uuid.UUID] = None,
            symbol: str = "",
            quantity: int = 0,
            unsettled_cash_amount: float = 0.0,
            execution_timestamp: Optional[datetime] = None,
            clearing_expiry_timestamp: Optional[datetime] = None,
            lock_id: Optional[uuid.UUID] = None,
            **kwargs: Any,
        ) -> None:
            self.lock_id = lock_id or uuid.uuid4()
            self.sub_account_id = sub_account_id or uuid.uuid4()
            self.symbol = str(symbol)
            self.quantity = int(quantity)
            self.unsettled_cash_amount = float(unsettled_cash_amount)
            exec_ts = execution_timestamp or _utc_now()
            if exec_ts.tzinfo is None:
                exec_ts = exec_ts.replace(tzinfo=timezone.utc)
            self.execution_timestamp = exec_ts
            self.clearing_expiry_timestamp = clearing_expiry_timestamp or (exec_ts + timedelta(days=2))
            for k, v in kwargs.items():
                setattr(self, k, v)

        def is_active(self, reference_time: Optional[datetime] = None) -> bool:
            ref = reference_time or _utc_now()
            expiry = self.clearing_expiry_timestamp
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            return ref < expiry
