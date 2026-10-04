"""
Nepal Trading Calendar & Trading Session Resolution.

Handles:
- NEPSE trading days (Sunday to Thursday).
- Weekend days (Friday and Saturday).
- Market holidays and special non-trading sessions.
- Dynamic session index derived from actual historical market records.
- Strict timing convention mapping (Publication time -> T0 session & T-1 pre-event cutoff).
"""

from datetime import datetime, date, time, timedelta
from typing import List, Optional, Tuple, Set
import pandas as pd
from .models import EventTimingConvention


class NepseTradingCalendar:
    """
    NEPSE Trading Calendar supporting trading-session offsets and timing conventions.
    """
    def __init__(self, active_trading_dates: Optional[List[str]] = None):
        """
        active_trading_dates: list of YYYY-MM-DD strings of verified trading sessions.
        If not provided, standard Sun-Thu schedule is used as fallback.
        """
        if active_trading_dates:
            # Sort and deduplicate
            self.trading_dates: List[str] = sorted(list(set(active_trading_dates)))
            self._date_set: Set[str] = set(self.trading_dates)
            self._date_to_idx: dict = {d: i for i, d in enumerate(self.trading_dates)}
        else:
            self.trading_dates = []
            self._date_set = set()
            self._date_to_idx = {}

    def load_from_csv(self, csv_path: str):
        """Build trading calendar from actual market records with active trading sessions."""
        df = pd.read_csv(csv_path, usecols=['trade_date', 'close_price'])
        valid = df[df['close_price'].notna() & (df['close_price'] > 0)]
        dates = sorted(valid['trade_date'].dropna().astype(str).unique().tolist())
        self.trading_dates = dates
        self._date_set = set(dates)
        self._date_to_idx = {d: i for i, d in enumerate(self.trading_dates)}

    def is_weekend(self, d: date) -> bool:
        """Friday is 4 in python weekday (0=Mon...4=Fri, 5=Sat, 6=Sun).
        In Nepal, Friday and Saturday are weekend days."""
        return d.weekday() in (4, 5)

    def is_trading_day(self, date_str: str) -> bool:
        """Check if date is a verified trading session."""
        if self.trading_dates:
            return date_str in self._date_set
        
        # Fallback to standard Sun-Thu check
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            return not self.is_weekend(d)
        except Exception:
            return False

    def next_trading_day(self, start_date_str: str) -> str:
        """Get the first trading day strictly AFTER start_date_str."""
        if self.trading_dates:
            for d in self.trading_dates:
                if d > start_date_str:
                    return d
            # Fallback if beyond loaded range
        d = datetime.strptime(start_date_str, "%Y-%m-%d").date() + timedelta(days=1)
        while self.is_weekend(d):
            d += timedelta(days=1)
        return d.strftime("%Y-%m-%d")

    def prev_trading_day(self, start_date_str: str) -> str:
        """Get the last trading day strictly BEFORE start_date_str."""
        if self.trading_dates:
            for d in reversed(self.trading_dates):
                if d < start_date_str:
                    return d
        # Fallback
        d = datetime.strptime(start_date_str, "%Y-%m-%d").date() - timedelta(days=1)
        while self.is_weekend(d):
            d -= timedelta(days=1)
        return d.strftime("%Y-%m-%d")

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
            t0_candidate = self.next_trading_day(pub_date_str) if (self.trading_dates and pub_date_str in self._date_set) else self._first_trading_day_on_or_after(pub_date)
        elif pub_time < time(11, 0):
            convention = EventTimingConvention.PRE_MARKET
            t0_candidate = pub_date_str
        elif pub_time <= time(15, 0):
            convention = EventTimingConvention.IN_SESSION
            t0_candidate = pub_date_str
        else:
            convention = EventTimingConvention.POST_MARKET
            t0_candidate = self.next_trading_day(pub_date_str)

        # Ensure t0 is an actual trading day
        if self.trading_dates and t0_candidate not in self._date_set:
            t0_date = self.next_trading_day(pub_date_str)
        else:
            t0_date = t0_candidate

        # T-1 is strictly before T0
        t_minus_1_date = self.prev_trading_day(t0_date)

        return t0_date, t_minus_1_date, convention

    def _first_trading_day_on_or_after(self, d: date) -> str:
        d_str = d.strftime("%Y-%m-%d")
        if self.trading_dates:
            for td in self.trading_dates:
                if td >= d_str:
                    return td
        curr = d
        while self.is_weekend(curr):
            curr += timedelta(days=1)
        return curr.strftime("%Y-%m-%d")

    def get_session_offset(self, anchor_date: str, offset: int) -> Optional[str]:
        """
        Returns trading session at +offset or -offset relative to anchor_date.
        offset=0 returns anchor_date if it's a trading date.
        offset=1 returns T+1 trading session, offset=-1 returns T-1 trading session.
        """
        if not self.trading_dates:
            # Fallback simple calendar
            curr = datetime.strptime(anchor_date, "%Y-%m-%d").date()
            step = 1 if offset >= 0 else -1
            remaining = abs(offset)
            while remaining > 0:
                curr += timedelta(days=step)
                if not self.is_weekend(curr):
                    remaining -= 1
            return curr.strftime("%Y-%m-%d")

        if anchor_date not in self._date_to_idx:
            return None
        
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
