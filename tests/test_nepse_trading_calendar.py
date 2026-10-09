import unittest
import pandas as pd
from pathlib import Path
from datetime import datetime, date

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
        """Test standard Sun-Thu trading day transitions."""
        # Thursday -> Sunday (+1 day)
        thu = pd.to_datetime("2026-10-01")
        self.assertEqual(thu.strftime("%A"), "Thursday")
        sun = thu + NEPSE_BUS_DAY
        self.assertEqual(sun.strftime("%Y-%m-%d"), "2026-10-04")
        self.assertEqual(sun.strftime("%A"), "Sunday")

        # Friday -> Sunday (+1 day)
        fri = pd.to_datetime("2026-10-02")
        self.assertEqual(fri.strftime("%A"), "Friday")
        sun2 = fri + NEPSE_BUS_DAY
        self.assertEqual(sun2.strftime("%Y-%m-%d"), "2026-10-04")
        self.assertEqual(sun2.strftime("%A"), "Sunday")

        # Saturday -> Sunday (+1 day)
        sat = pd.to_datetime("2026-10-03")
        self.assertEqual(sat.strftime("%A"), "Saturday")
        sun3 = sat + NEPSE_BUS_DAY
        self.assertEqual(sun3.strftime("%Y-%m-%d"), "2026-10-04")
        self.assertEqual(sun3.strftime("%A"), "Sunday")

        # Sunday -> Monday (+1 day)
        sun_start = pd.to_datetime("2026-10-04")
        mon = sun_start + NEPSE_BUS_DAY
        self.assertEqual(mon.strftime("%Y-%m-%d"), "2026-10-05")
        self.assertEqual(mon.strftime("%A"), "Monday")

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
        res_add = add_nepse_trading_days("2026-10-01", 1)
        self.assertEqual(res_add.strftime("%Y-%m-%d"), "2026-10-04")
        self.assertEqual(res_add.strftime("%A"), "Sunday")

        res_sub = sub_nepse_trading_days("2026-10-04", 1)
        self.assertEqual(res_sub.strftime("%Y-%m-%d"), "2026-10-01")
        self.assertEqual(res_sub.strftime("%A"), "Thursday")

    def test_weekend_detection(self):
        """Test Friday and Saturday are non-trading weekends."""
        self.assertFalse(is_nepse_trading_day("2026-10-02")) # Friday
        self.assertFalse(is_nepse_trading_day("2026-10-03")) # Saturday
        self.assertTrue(is_nepse_trading_day("2026-10-04"))  # Sunday
        self.assertTrue(is_nepse_trading_day("2026-10-05"))  # Monday
        self.assertTrue(is_nepse_trading_day("2026-10-06"))  # Tuesday
        self.assertTrue(is_nepse_trading_day("2026-10-07"))  # Wednesday
        self.assertTrue(is_nepse_trading_day("2026-10-08"))  # Thursday

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

        # Future projected session beyond DB (Tuesday Oct 6 -> Wednesday Oct 7)
        nxt_future = get_next_trading_session("2026-10-06")
        self.assertEqual(nxt_future, "2026-10-07")
        self.assertEqual(pd.to_datetime(nxt_future).strftime("%A"), "Wednesday")

        # Format label
        label = format_session_label("2026-10-04")
        self.assertEqual(label, "2026-10-04 (Sunday)")

    def test_backward_compatibility_nepse_trading_calendar(self):
        """Test NepseTradingCalendar class methods."""
        cal = NepseTradingCalendar()
        self.assertTrue(cal.is_weekend(date(2026, 10, 2))) # Friday is weekend
        self.assertTrue(cal.is_weekend(date(2026, 10, 3))) # Saturday is weekend
        self.assertFalse(cal.is_weekend(date(2026, 10, 4))) # Sunday is regular weekday

        # 1. Test lakehouse-grounded session resolution (Oct 5 was an actual trading session)
        pub_dt_mon = datetime(2026, 10, 5, 9, 30) # Monday 9:30 AM
        t0_mon, _, conv_mon = cal.resolve_event_t0_and_t_minus_1(pub_dt_mon)
        self.assertEqual(t0_mon, "2026-10-05")
        self.assertEqual(conv_mon, EventTimingConvention.PRE_MARKET)

        # 2. Test holiday detection: Oct 4 was not traded in lakehouse (Dashain), so rolls to Oct 5
        pub_dt_sun = datetime(2026, 10, 4, 9, 30) # Sunday 9:30 AM
        t0_sun, _, conv_sun = cal.resolve_event_t0_and_t_minus_1(pub_dt_sun)
        self.assertEqual(t0_sun, "2026-10-05")
        self.assertEqual(conv_sun, EventTimingConvention.WEEKEND_HOLIDAY)

        # 3. Test pure math calendar fallback (where Oct 4 is treated as standard Sun-Thu session)
        cal_math = NepseTradingCalendar(active_trading_dates=[])
        t0_math, _, conv_math = cal_math.resolve_event_t0_and_t_minus_1(pub_dt_sun)
        self.assertEqual(t0_math, "2026-10-04")
        self.assertEqual(conv_math, EventTimingConvention.PRE_MARKET)

if __name__ == "__main__":
    unittest.main()
