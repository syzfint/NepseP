"""
Unit and regression tests for Phase 2: NRB Sovereign Macro & Treasury Bill Pipeline.
Validates:
  1. BS to AD calendar conversion using nepali_datetime.
  2. DuckDB schema integrity across staging tables and macro_interest_rates.
  3. Continuous LOCF forward-fill daily series (0 null gaps in rf_yield_91d).
  4. TemporalContaminationError guard: ASOF joins must not leak same-day Monday auctions.
"""

import sys
import pytest
import datetime
import importlib.util
from pathlib import Path

# Dynamic import for module with numeric directory prefix
_spec = importlib.util.spec_from_file_location(
    "nrb_treasury_scraper",
    Path(__file__).parent.parent / "scripts" / "01_etl_and_ingestion" / "nrb_treasury_scraper.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

convert_bs_to_ad = _mod.convert_bs_to_ad
get_pit_aligned_macro = _mod.get_pit_aligned_macro
DB_PATH = _mod.DB_PATH
from scripts.db_connection import get_connection_manager


class TemporalContaminationError(AssertionError):
    """Raised when future macro auction data leaks into historical price bars."""
    pass


def test_nepali_calendar_conversion():
    """Verify Bikram Sambat to Gregorian ISO-8601 conversions across variable month lengths."""
    # 2080-11-14 BS -> 2024-02-26 AD
    assert convert_bs_to_ad("2080-11-14") == "2024-02-26"
    assert convert_bs_to_ad("2080/11/14") == "2024-02-26"
    assert convert_bs_to_ad("2080.11.14") == "2024-02-26"

    # Year transition test: 2081-01-01 BS -> 2024-04-13 AD
    assert convert_bs_to_ad("2081-01-01") == "2024-04-13"


def test_staging_tables_exist_and_populated():
    """Ensure staging tables exist in DuckDB lakehouse and contain records."""
    db_mgr = get_connection_manager(str(DB_PATH))
    with db_mgr.acquire() as con:
        tbill_count = con.execute("SELECT COUNT(*) FROM staging_nrb_tbill_auctions").fetchone()[0]
        macro_count = con.execute("SELECT COUNT(*) FROM staging_nrb_monthly_macro").fetchone()[0]
        assert tbill_count >= 1000, f"Expected >= 1000 tbill records, got {tbill_count}"
        assert macro_count >= 50, f"Expected >= 50 monthly macro records, got {macro_count}"


def test_locf_forward_fill_zero_nulls():
    """Ensure continuous daily macro_interest_rates table has zero nulls in rf_yield_91d."""
    db_mgr = get_connection_manager(str(DB_PATH))
    with db_mgr.acquire() as con:
        null_count = con.execute("""
            SELECT COUNT(*) 
            FROM macro_interest_rates 
            WHERE rf_yield_91d IS NULL OR rf_yield_91d <= 0
        """).fetchone()[0]
        assert null_count == 0, f"Found {null_count} null or invalid rf_yield_91d values!"

        total_days = con.execute("SELECT COUNT(*) FROM macro_interest_rates").fetchone()[0]
        assert total_days >= 2000, f"Expected >= 2000 calendar days, got {total_days}"


def test_pit_one_session_lag_guard():
    """
    Assert TemporalContaminationError prevention:
    Monday evening auction disclosures (e.g. on 2024-03-25) CANNOT be visible
    to equity price action on Monday 2024-03-25.
    Effective date must strictly satisfy: effective_date <= query_date - 1 day.
    """
    query_date = "2024-03-25"  # A Monday
    res = get_pit_aligned_macro(query_date)
    assert res is not None, f"No macro data returned for {query_date}"

    effective_dt = datetime.date.fromisoformat(res["effective_date"])
    query_dt = datetime.date.fromisoformat(query_date)

    if effective_dt >= query_dt:
        raise TemporalContaminationError(
            f"LOOK-AHEAD BIAS DETECTED! Macro effective date {effective_dt} >= query date {query_dt}."
        )

    assert (query_dt - effective_dt).days >= 1, "1-session lag guard violated!"


def test_predictive_feature_view():
    """Ensure view_predictive_feature_feed joins without error and calculates derived macro spreads."""
    db_mgr = get_connection_manager(str(DB_PATH))
    with db_mgr.acquire() as con:
        sample = con.execute("""
            SELECT 
                trade_date, rf_yield_91d, yield_28d, yield_364d,
                tbill_term_spread_364_28, interbank_liquidity_premium
            FROM view_predictive_feature_feed
            WHERE trade_date IS NOT NULL
            LIMIT 5
        """).fetchall()
        assert len(sample) > 0, "view_predictive_feature_feed returned no rows"
        for row in sample:
            assert row[1] is not None, "rf_yield_91d is None in view"
