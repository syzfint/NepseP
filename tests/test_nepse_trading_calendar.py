import unittest
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime, date

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.nepse_trading_calendar import (
    NEPSE_BUS_DAY,
    add_nepse_trading_days,
    sub_nepse_trading_days,
    is_nepse_trading_day,
    get_actual_nepse_trading_dates,
    get_next_trading_session,
    get_prev_trading_session,
    format_session_label,
    NepseTradingCalendar,
    EventTimingConvention
)

class TestNepseTradingCalendar(unittest.TestCase):
    def test_custom_business_day_weekmask(self):
        """Test standard Mon-Fri trading day transitions with Sat-Sun off."""
        # Thursday -> Friday (+1 day)
        thu = pd.to_datetime("2026-10-01")
        self.assertEqual(thu.strftime("%A"), "Thursday")
        fri = thu + NEPSE_BUS_DAY
        self.assertEqual(fri.strftime("%Y-%m-%d"), "2026-10-02")
        self.assertEqual(fri.strftime("%A"), "Friday")

        # Friday -> Monday (+1 day) (Friday rolls to Monday across Sat-Sun weekend)
        fri_start = pd.to_datetime("2026-10-02")
        self.assertEqual(fri_start.strftime("%A"), "Friday")
        mon = fri_start + NEPSE_BUS_DAY
        self.assertEqual(mon.strftime("%Y-%m-%d"), "2026-10-05")
        self.assertEqual(mon.strftime("%A"), "Monday")

        # Saturday -> Monday (+1 day)
        sat = pd.to_datetime("2026-10-03")
        self.assertEqual(sat.strftime("%A"), "Saturday")
        mon2 = sat + NEPSE_BUS_DAY
        self.assertEqual(mon2.strftime("%Y-%m-%d"), "2026-10-05")
        self.assertEqual(mon2.strftime("%A"), "Monday")

        # Sunday -> Monday (+1 day)
        sun = pd.to_datetime("2026-10-04")
        self.assertEqual(sun.strftime("%A"), "Sunday")
        mon3 = sun + NEPSE_BUS_DAY
        self.assertEqual(mon3.strftime("%Y-%m-%d"), "2026-10-05")
        self.assertEqual(mon3.strftime("%A"), "Monday")

        # Monday -> Tuesday (+1 day)
        mon_start = pd.to_datetime("2026-10-05")
        tue = mon_start + NEPSE_BUS_DAY
        self.assertEqual(tue.strftime("%Y-%m-%d"), "2026-10-06")
        self.assertEqual(tue.strftime("%A"), "Tuesday")

        # Tuesday -> Wednesday (+1 day)
        tue_start = pd.to_datetime("2026-10-06")
        wed = tue_start + NEPSE_BUS_DAY
        self.assertEqual(wed.strftime("%Y-%m-%d"), "2026-10-07")
        self.assertEqual(wed.strftime("%A"), "Wednesday")

    def test_add_and_sub_nepse_trading_days_helpers(self):
        """Test add_nepse_trading_days and sub_nepse_trading_days helpers."""
        # Thursday + 1 day -> Friday
        res_add = add_nepse_trading_days("2026-10-01", 1)
        self.assertEqual(res_add.strftime("%Y-%m-%d"), "2026-10-02")
        self.assertEqual(res_add.strftime("%A"), "Friday")

        # Friday + 1 day -> Monday
        res_add_fri = add_nepse_trading_days("2026-10-02", 1)
        self.assertEqual(res_add_fri.strftime("%Y-%m-%d"), "2026-10-05")
        self.assertEqual(res_add_fri.strftime("%A"), "Monday")

        # Monday - 1 day -> Friday
        res_sub = sub_nepse_trading_days("2026-10-05", 1)
        self.assertEqual(res_sub.strftime("%Y-%m-%d"), "2026-10-02")
        self.assertEqual(res_sub.strftime("%A"), "Friday")

    def test_weekend_detection(self):
        """Test Saturday and Sunday are non-trading weekends; Friday is OPEN."""
        self.assertTrue(is_nepse_trading_day("2026-10-02"))  # Friday (OPEN)
        self.assertFalse(is_nepse_trading_day("2026-10-03")) # Saturday (OFF)
        self.assertFalse(is_nepse_trading_day("2026-10-04")) # Sunday (OFF)
        self.assertTrue(is_nepse_trading_day("2026-10-05"))  # Monday (OPEN)
        self.assertTrue(is_nepse_trading_day("2026-10-06"))  # Tuesday (OPEN)
        self.assertTrue(is_nepse_trading_day("2026-10-07"))  # Wednesday (OPEN)
        self.assertTrue(is_nepse_trading_day("2026-10-08"))  # Thursday (OPEN)
        self.assertTrue(is_nepse_trading_day("2026-10-09"))  # Friday (OPEN)

    def test_duckdb_lakehouse_queries(self):
        """Test dynamic trading dates queried from market_master_union.parquet."""
        dates = get_actual_nepse_trading_dates(min_date="2026-09-28")
        self.assertIsInstance(dates, list)
        self.assertIn("2026-09-28", dates)
        self.assertIn("2026-10-01", dates)
        self.assertIn("2026-10-06", dates)

    def test_session_resolution(self):
        """Test get_next_trading_session and get_prev_trading_session."""
        # Historical next session from DB
        nxt_sess = get_next_trading_session("2026-10-05")
        self.assertEqual(nxt_sess, "2026-10-06")

        # Format label
        label = format_session_label("2026-10-09")
        self.assertEqual(label, "2026-10-09 (Friday)")

    def test_backward_compatibility_nepse_trading_calendar(self):
        """Test NepseTradingCalendar class methods."""
        cal = NepseTradingCalendar()
        self.assertFalse(cal.is_weekend(date(2026, 10, 2))) # Friday is trading day
        self.assertTrue(cal.is_weekend(date(2026, 10, 3)))  # Saturday is weekend
        self.assertTrue(cal.is_weekend(date(2026, 10, 4)))  # Sunday is weekend
        self.assertFalse(cal.is_weekend(date(2026, 10, 5))) # Monday is trading day
        self.assertFalse(cal.is_weekend(date(2026, 10, 9))) # Friday is trading day

        # 1. Test lakehouse-grounded session resolution (Oct 5 was an actual trading session)
        pub_dt_mon = datetime(2026, 10, 5, 9, 30) # Monday 9:30 AM
        t0_mon, _, conv_mon = cal.resolve_event_t0_and_t_minus_1(pub_dt_mon)
        self.assertEqual(t0_mon, "2026-10-05")
        self.assertEqual(conv_mon, EventTimingConvention.PRE_MARKET)

        # 2. Test weekend detection: Oct 4 is Sunday (Weekend), so rolls to Monday Oct 5
        pub_dt_sun = datetime(2026, 10, 4, 9, 30) # Sunday 9:30 AM
        t0_sun, _, conv_sun = cal.resolve_event_t0_and_t_minus_1(pub_dt_sun)
        self.assertEqual(t0_sun, "2026-10-05")
        self.assertEqual(conv_sun, EventTimingConvention.WEEKEND_HOLIDAY)

if __name__ == "__main__":
    unittest.main()
