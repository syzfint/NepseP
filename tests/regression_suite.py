#!/usr/bin/env python3
"""
tests/regression_suite.py

SWE-bench Style Automated Institutional Assertion Regression Suite
==================================================================
Strict test harness enforcing the zero-leakage, fail-closed,
deterministic mathematical integrity of APEXMARKETENGINE:

1. Ordinary Equity Filtration: Asserts zero contamination from promoter (PO),
   debentures (D8*), or mutual funds (*MF).
2. Point-in-Time NFRS Zero-Leakage: Enforces T_pub < T_trade for 100% of joins.
3. Deterministic Accounting Gate: Mathematically verifies Balance Sheet Identity
   (Assets == Liabilities + Equity) and NPL % verification (±0.01%), routing
   corrupted reports to reports/manual_review_queue.json.
4. Promoter Share Lock-in Dilution & HHI: Asserts supply shock detection in [-15d, +30d]
   and broker accumulation HHI calculation.
5. Fractional Differentiation (d=0.35): Verifies ADF stationarity (p < 0.05) and
   Pearson correlation retention (r > 0.80).
6. Statutory Market Rules: Verifies schema, commission slabs, and CGT rates.
7. Zero Numerical Drift: Verifies exact regression equivalence against BASELINE.
"""

import sys
import json
import hashlib
import tempfile
import importlib
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Dynamic imports for modules with numeric path components
connectors = importlib.import_module("scripts.01_etl_and_ingestion.nepse_ingestion_connectors")
nfrs_pit = importlib.import_module("scripts.01_etl_and_ingestion.nfrs_point_in_time_extractor")
accounting_gate = importlib.import_module("scripts.00_control.deterministic_accounting_auditor")
rules_sync = importlib.import_module("scripts.00_control.market_rules_synchronizer")
frac_diff = importlib.import_module("scripts.02_modeling_and_calculations.fractional_differentiation")
audit_mod = importlib.import_module("scripts.00_control.audit")


class TestInstitutionalRegressionSuite:

    def test_01_ordinary_equity_filtration_invariants(self):
        """Asserts zero non-ordinary instruments leak into ordinary trading universe."""
        is_ord = connectors.is_ordinary_equity

        # Valid ordinary equities
        assert is_ord("NABIL") is True
        assert is_ord("SHIVM") is True
        assert is_ord("CHCL") is True
        assert is_ord("HDL") is True
        assert is_ord("NICA") is True

        # Promoter shares
        assert is_ord("NABILPO") is False
        assert is_ord("NICAPO") is False
        assert is_ord("CHCL_PO") is False
        assert is_ord("HATHP") is False

        # Debentures
        assert is_ord("EBLD86") is False
        assert is_ord("SBLD83") is False
        assert is_ord("GBD85") is False
        assert is_ord("NABIL D82") is False

        # Mutual funds
        assert is_ord("NICBF") is False
        assert is_ord("NIBLPF") is False
        assert is_ord("SEF") is False
        assert is_ord("SIGS2") is False
        assert is_ord("LEMF") is False
        assert is_ord("KMCITMF") is False

    def test_02_point_in_time_nfrs_zero_leakage(self):
        """Asserts that quarterly reports cannot leak before official publication timestamp T_pub."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_parquet = Path(tmpdir) / "test_pit.parquet"
            pit_ext = nfrs_pit.PointInTimeNFRSExtractor(pit_parquet=test_parquet)

            # Record a report with Q-end July 15 and publication Aug 25
            pit_ext.record_nfrs_quarterly(
                symbol="NABIL",
                quarter_label="2080-81_Q4",
                quarter_end_date="2024-07-15",
                official_publication_timestamp="2024-08-25 10:30:00",
                net_profit=7.0e9,
                paid_up_capital=2.7e10,
                total_equity=5.5e10,
                gross_npl_pct=3.15,
                eps=26.0,
                bvps=203.0
            )

            # Trade bars before and after publication
            trades = pd.DataFrame([
                {"date": "2024-08-20", "open": 600, "high": 610, "low": 595, "close": 605, "volume": 1000},
                {"date": "2024-08-24", "open": 605, "high": 612, "low": 601, "close": 610, "volume": 1200},
                {"date": "2024-08-26", "open": 612, "high": 625, "low": 610, "close": 620, "volume": 1500},
                {"date": "2024-08-27", "open": 620, "high": 630, "low": 618, "close": 628, "volume": 2000},
            ])

            merged = pit_ext.join_point_in_time(trades, "NABIL")

            # Prior to Aug 25 publication: fundamentals MUST be NaN
            assert pd.isna(merged.loc[0, "eps"])
            assert pd.isna(merged.loc[1, "eps"])

            # After Aug 25 publication: fundamentals are available
            assert merged.loc[2, "eps"] == 26.0
            assert merged.loc[3, "eps"] == 26.0
            assert merged.loc[2, "quarter_label"] == "2080-81_Q4"

            # Attempting to record report with publication <= quarter_end must fail
            with pytest.raises(ValueError):
                pit_ext.record_nfrs_quarterly(
                    symbol="NABIL",
                    quarter_label="2080-81_Q3",
                    quarter_end_date="2024-04-15",
                    official_publication_timestamp="2024-04-10 00:00:00",  # Illegal early timestamp
                    net_profit=5e9, paid_up_capital=2.7e10, total_equity=5e10, gross_npl_pct=3.0, eps=20.0, bvps=190.0
                )

    def test_03_deterministic_accounting_gate_reconciliation(self):
        """Asserts deterministic mathematical validation of balance sheet identities."""
        gate = accounting_gate.DeterministicAccountingGate()

        # 1. Perfectly reconciled report
        clean = {
            "symbol": "EBL",
            "quarter_end_date": "2026-07-16",
            "official_publication_timestamp": "2026-08-28 10:00:00",
            "total_assets": 100000000.0,
            "total_liabilities": 85000000.0,
            "total_equity": 15000000.0,  # 85M + 15M = 100M exactly
            "gross_npl": 3000000.0,
            "gross_loans": 75000000.0,
            "reported_npl_pct": 4.0,  # (3M / 75M) * 100 = 4.0%
            "net_profit": 5000000.0,
            "paid_up_capital": 10000000.0
        }
        res_clean = gate.process_and_route(clean)
        assert res_clean["status"] == "PASSED_AUDIT_GATE"
        assert res_clean["checks"]["balance_sheet_identity"]["passed"] is True
        assert res_clean["checks"]["npl_verification"]["passed"] is True

        # 2. Corrupted Balance Sheet (Assets != Liab + Equity)
        corrupted_bs = dict(clean)
        corrupted_bs["total_assets"] = 120000000.0  # 20M mismatch
        res_corrupt_bs = gate.process_and_route(corrupted_bs)
        assert res_corrupt_bs["status"] == "REJECTED_AUDIT_FAIL"
        assert res_corrupt_bs["checks"]["balance_sheet_identity"]["passed"] is False

        # 3. Corrupted NPL percentage (Reported 10% vs Actual 4%)
        corrupted_npl = dict(clean)
        corrupted_npl["reported_npl_pct"] = 10.0
        res_corrupt_npl = gate.process_and_route(corrupted_npl)
        assert res_corrupt_npl["status"] == "REJECTED_AUDIT_FAIL"
        assert res_corrupt_npl["checks"]["npl_verification"]["passed"] is False

    def test_04_promoter_lockin_free_float_and_hhi(self):
        """Asserts supply shock window detection and broker accumulation HHI calculation."""
        engine = nfrs_pit.FreeFloatDilutionEngine()

        trades = [
            {"buyer_broker": 58, "seller_broker": 45, "quantity": 20000},
            {"buyer_broker": 58, "seller_broker": 49, "quantity": 10000},
            {"buyer_broker": 45, "seller_broker": 34, "quantity": 5000},
        ]
        # Net buyer 58 = +30,000, 45 = +5,000 - 20,000 = -15,000 (seller)
        # Total net buying = 30,000 (100% broker 58)
        # HHI should be (100)^2 = 10,000
        hhi = engine.calculate_broker_hhi(trades)
        assert hhi == 10000.0

        # Shock evaluation with dilution factor
        shock = engine.evaluate_dilution_shock(
            symbol="TEST_HYDRO",
            as_of_date="2026-10-10",
            current_close=300.0,
            ordinary_shares=5000000.0,
            promoter_shares=15000000.0,
            quarterly_net_profit=50000000.0,
            broker_trades=trades
        )
        assert shock["post_free_float_shares"] == 20000000.0
        assert shock["dilution_expansion_factor"] == 4.0
        assert shock["broker_accumulation_hhi"] == 10000.0
        assert shock["broker_cartel_alert"] is True

    def test_05_fractional_differentiation_stationarity_and_memory(self):
        """Asserts that fractional differencing d=0.35 achieves ADF stationarity while retaining memory."""
        np.random.seed(42)
        n = 500
        dt = 1 / 252
        mu, sigma = 0.08, 0.25
        steps = np.random.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), n)
        prices = pd.Series(500.0 * np.exp(np.cumsum(steps)), name="close")

        # 1. Raw prices should be non-stationary (ADF p > 0.05)
        raw_adf = frac_diff.test_stationarity_adf(prices)
        assert raw_adf["stationary"] is False

        # 2. Fractional differenced d=0.35
        fd_035 = frac_diff.fractional_diff_ffd(prices, d=0.35, threshold=1e-3, max_lags=120)
        fd_adf = frac_diff.test_stationarity_adf(fd_035)
        fd_corr = frac_diff.evaluate_memory_retention(prices, fd_035)

        # Must be stationary (p < 0.05) and retain memory (r > 0.80)
        assert fd_adf["stationary"] is True
        assert fd_adf["p_value"] < 0.05
        assert fd_corr > 0.80

        # 3. Standard integer differencing d=1.0 loses long-term memory
        d1 = prices.diff()
        d1_corr = frac_diff.evaluate_memory_retention(prices, d1)
        assert d1_corr < 0.20


    def test_06_market_rules_synchronizer(self):
        """Asserts statutory fee slabs, CGT, margin lending, and circuit breaker conformity."""
        sync = rules_sync.MarketRulesSynchronizer()
        assert sync.validate_rules_schema() is True

        # Commission tier 1: <= 50,000 is 0.40%
        c1 = sync.calculate_commission(40000.0)
        assert c1 == 160.0

        # Commission tier 5: > 10,000,000 is 0.27%
        c5 = sync.calculate_commission(12000000.0)
        assert c5 == 32400.0

        # Capital Gains Tax: Individual Short-Term (7.5%)
        cost_st = sync.calculate_effective_costs(100000.0, is_sell=True, gain=20000.0, is_short_term=True)
        assert cost_st["capital_gains_tax"] == 1500.0  # 7.5% of 20,000

        # Capital Gains Tax: Individual Long-Term (5.0%)
        cost_lt = sync.calculate_effective_costs(100000.0, is_sell=True, gain=20000.0, is_short_term=False)
        assert cost_lt["capital_gains_tax"] == 1000.0  # 5.0% of 20,000

        # DP charge on sell
        assert cost_st["dp_charge"] == 25.0

    def test_07_zero_numerical_drift_equivalence(self):
        """Asserts 0.0000% regression drift against frozen baseline."""
        report = audit_mod.audit_against_baseline()
        assert report["overall_passed"] is True
        assert report["prediction_drift_pct"] == 0.0
        assert report["allocation_drift_pct"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
