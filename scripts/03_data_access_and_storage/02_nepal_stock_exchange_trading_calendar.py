"""
Nepal Trading Calendar & Trading Session Resolution.

Handles:
- NEPSE trading days (Monday to Friday).
- Weekend days (Saturday and Sunday).
- Market holidays and special non-trading sessions.
- Dynamic session index derived from actual historical market records (DuckDB lakehouse).
- Native NEPSE CustomBusinessDay in Pandas.
- Strict timing convention mapping (Publication time -> T0 session & T-1 pre-event cutoff).
"""

import os
from datetime import datetime, date, time, timedelta
from typing import List, Optional, Tuple, Set, Union
from enum import Enum
from pathlib import Path

import duckdb
import pandas as pd
from pandas.tseries.holiday import AbstractHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay
from scripts.03_data_access_and_storage.duckdb_connection_manager import connection_manager


class EventTimingConvention(str, Enum):
    """Timing conventions for corporate announcements and disclosures."""
    PRE_MARKET = "PRE_MARKET"           # Published before 11:00 AM NPT on trading day -> T0 is today
    IN_SESSION = "IN_SESSION"           # Published 11:00 AM - 3:00 PM NPT -> T0 is today
    POST_MARKET = "POST_MARKET"         # Published after 3:00 PM NPT -> T0 is next trading day
    WEEKEND_HOLIDAY = "WEEKEND_HOLIDAY" # Published on Sat/Sun/Holiday -> T0 is next trading day


class NepseHolidayCalendar(AbstractHolidayCalendar):
    """NEPSE Public Holiday Calendar (Dashain, Tihar, Shivaratri, etc.)."""
    rules = []


# NEPSE Weekmask: Monday through Friday (Only Saturday and Sunday are weekends)
NEPSE_WEEKDAYS = "Mon Tue Wed Thu Fri"
NEPSE_BUS_DAY = CustomBusinessDay(
    weekmask=NEPSE_WEEKDAYS,
    calendar=NepseHolidayCalendar()
)


def get_default_db_path() -> Path:
    """Resolve default market master parquet file."""
    curr = Path(__file__).resolve().parent
    candidates = [
        curr.parent.parent / "02_processed_parquet" / "market_master_union.parquet",
        curr.parent / "02_processed_parquet" / "market_master_union.parquet",
        Path.cwd() / "02_processed_parquet" / "market_master_union.parquet"
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def add_nepse_trading_days(start_date: Union[str, datetime, date, pd.Timestamp], n_days: int = 1) -> pd.Timestamp:
    """Add N NEPSE trading days to start_date using Mon-Fri weekmask."""
    ts = pd.to_datetime(start_date)
    return ts + (n_days * NEPSE_BUS_DAY)


def sub_nepse_trading_days(start_date: Union[str, datetime, date, pd.Timestamp], n_days: int = 1) -> pd.Timestamp:
    """Subtract N NEPSE trading days from start_date."""
    ts = pd.to_datetime(start_date)
    return ts - (n_days * NEPSE_BUS_DAY)


def is_nepse_trading_day(d: Union[str, datetime, date, pd.Timestamp]) -> bool:
    """Check if date is a standard NEPSE trading day (Mon-Fri). Friday is OPEN."""
    dt = pd.to_datetime(d)
    return dt.weekday() not in (5, 6)


def get_actual_nepse_trading_dates(
    db_path: Optional[Union[str, Path]] = None,
    min_date: str = "2026-01-01"
) -> List[str]:
    """Query actual verified trading dates directly from DuckDB lakehouse."""
    if db_path is None:
        db_path = get_default_db_path()
    path_str = str(db_path)
    if not os.path.exists(path_str):
        return []

    with connection_manager.acquire() as con:
        query = f"""
            SELECT DISTINCT CAST(date AS VARCHAR) as trade_date
            FROM '{path_str}'
            WHERE date >= '{min_date}'
            ORDER BY trade_date ASC
        """
        rows = con.execute(query).fetchall()
    trading_dates = [r[0][:10] for r in rows if r[0]]
    return sorted(list(set(trading_dates)))


def get_next_trading_session(
    current_date: Union[str, datetime, date, pd.Timestamp],
    db_path: Optional[Union[str, Path]] = None,
    prefer_actual: bool = True
) -> str:
    """Resolves the next trading session strictly after current_date."""
    curr_str = pd.to_datetime(current_date).strftime("%Y-%m-%d")
    if prefer_actual:
        if db_path is None:
            db_path = get_default_db_path()
        trading_dates = get_actual_nepse_trading_dates(db_path=db_path)
        future_dates = [d for d in trading_dates if d > curr_str]
        if future_dates:
            return future_dates[0]
            
    next_dt = add_nepse_trading_days(curr_str, 1)
    return next_dt.strftime("%Y-%m-%d")


def get_prev_trading_session(
    current_date: Union[str, datetime, date, pd.Timestamp],
    db_path: Optional[Union[str, Path]] = None,
    prefer_actual: bool = True
) -> str:
    """Resolves the prior trading session strictly before current_date."""
    curr_str = pd.to_datetime(current_date).strftime("%Y-%m-%d")
    if prefer_actual:
        if db_path is None:
            db_path = get_default_db_path()
        trading_dates = get_actual_nepse_trading_dates(db_path=db_path)
        past_dates = [d for d in trading_dates if d < curr_str]
        if past_dates:
            return past_dates[-1]
            
    prev_dt = sub_nepse_trading_days(curr_str, 1)
    return prev_dt.strftime("%Y-%m-%d")


def format_session_label(d: Union[str, datetime, date, pd.Timestamp], fmt: str = "%Y-%m-%d (%A)") -> str:
    """Format date with full weekday name."""
    dt = pd.to_datetime(d)
    return dt.strftime(fmt)


class NepseTradingCalendar:
    """NEPSE Trading Calendar supporting trading-session offsets and timing conventions."""
    def __init__(self, active_trading_dates: Optional[List[str]] = None, db_path: Optional[Union[str, Path]] = None):
        if active_trading_dates is not None:
            self.trading_dates: List[str] = sorted(list(set(active_trading_dates)))
        elif db_path and os.path.exists(str(db_path)):
            self.trading_dates = get_actual_nepse_trading_dates(db_path=db_path, min_date="2000-01-01")
        else:
            default_p = get_default_db_path()
            if default_p.exists():
                self.trading_dates = get_actual_nepse_trading_dates(db_path=default_p, min_date="2000-01-01")
            else:
                self.trading_dates = []

        self._date_set: Set[str] = set(self.trading_dates)
        self._date_to_idx: dict = {d: i for i, d in enumerate(self.trading_dates)}

    def load_from_csv(self, csv_path: str):
        """Build trading calendar from actual market records with active trading sessions."""
        df = pd.read_csv(csv_path, usecols=['trade_date', 'close_price'])
        valid = df[df['close_price'].notna() & (df['close_price'] > 0)]
        dates = sorted(valid['trade_date'].dropna().astype(str).unique().tolist())
        self.trading_dates = dates
        self._date_set = set(dates)
        self._date_to_idx = {d: i for i, d in enumerate(self.trading_dates)}

    def is_weekend(self, d: Union[date, datetime, pd.Timestamp]) -> bool:
        """Weekend days are Saturday (5) and Sunday (6). Friday (4) is a trading day."""
        dt = pd.to_datetime(d)
        return dt.weekday() in (5, 6)

    def is_trading_day(self, date_str: str) -> bool:
        """Check if date is a verified trading session."""
        if self.trading_dates:
            return date_str in self._date_set
        return is_nepse_trading_day(date_str)

    def next_trading_day(self, start_date_str: str) -> str:
        """Get the first trading day strictly AFTER start_date_str."""
        if self.trading_dates:
            for d in self.trading_dates:
                if d > start_date_str:
                    return d
        return add_nepse_trading_days(start_date_str, 1).strftime("%Y-%m-%d")

    def prev_trading_day(self, start_date_str: str) -> str:
        """Get the last trading day strictly BEFORE start_date_str."""
        if self.trading_dates:
            for d in reversed(self.trading_dates):
                if d < start_date_str:
                    return d
        return sub_nepse_trading_days(start_date_str, 1).strftime("%Y-%m-%d")

    def resolve_event_t0_and_t_minus_1(
        self, published_npt: datetime
    ) -> Tuple[str, str, EventTimingConvention]:
        """
        Resolves publication datetime to:
        1. Target trading session T0
        2. Strictly prior trading session T-1 (pre-event cutoff)
        3. Event timing convention used
        
        NEPSE trading hours: 11:00 AM to 3:00 PM (15:00) NPT.
        """
        pub_date = published_npt.date()
        pub_time = published_npt.time()
        pub_date_str = pub_date.strftime("%Y-%m-%d")

        # Determine convention
        if self.is_weekend(pub_date) or (self.trading_dates and pub_date_str not in self._date_set):
            convention = EventTimingConvention.WEEKEND_HOLIDAY
            t0_candidate = self.next_trading_day(pub_date_str)
        elif pub_time < time(11, 0):
            convention = EventTimingConvention.PRE_MARKET
            t0_candidate = pub_date_str
        elif pub_time <= time(15, 0):
            convention = EventTimingConvention.IN_SESSION
            t0_candidate = pub_date_str
        else:
            convention = EventTimingConvention.POST_MARKET
            t0_candidate = self.next_trading_day(pub_date_str)

        if self.trading_dates and t0_candidate not in self._date_set:
            t0_date = self.next_trading_day(pub_date_str)
        else:
            t0_date = t0_candidate

        t_minus_1_date = self.prev_trading_day(t0_date)
        return t0_date, t_minus_1_date, convention

    def get_session_offset(self, anchor_date: str, offset: int) -> Optional[str]:
        """
        Returns trading session at +offset or -offset relative to anchor_date.
        offset=0 returns anchor_date if it's a trading date.
        offset=1 returns T+1 trading session, offset=-1 returns T-1 trading session.
        """
        if not self.trading_dates:
            if offset >= 0:
                return add_nepse_trading_days(anchor_date, offset).strftime("%Y-%m-%d")
            else:
                return sub_nepse_trading_days(anchor_date, abs(offset)).strftime("%Y-%m-%d")

        if anchor_date not in self._date_to_idx:
            if offset >= 0:
                return add_nepse_trading_days(anchor_date, offset).strftime("%Y-%m-%d")
            else:
                return sub_nepse_trading_days(anchor_date, abs(offset)).strftime("%Y-%m-%d")
        
        idx = self._date_to_idx[anchor_date]
        target_idx = idx + offset
        if 0 <= target_idx < len(self.trading_dates):
            return self.trading_dates[target_idx]
        return None

    def get_session_offsets_map(self, anchor_date: str, offsets: List[int]) -> dict:
        """Returns dict of {offset: date_str} for valid offsets."""
        res = {}
        for off in offsets:
            dt = self.get_session_offset(anchor_date, off)
            if dt:
                res[off] = dt
        return res
