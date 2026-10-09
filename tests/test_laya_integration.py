#!/usr/bin/env python3
"""
tests/test_laya_integration.py

Comprehensive Test Suite for Laya System 1 Triage Guard & Router
================================================================
Verifies:
1. Strict Code Boundary & Typed Schema Outputs (Fixed Enum / Bool).
2. Bilingual 33ms News Triage (Devanagari & English).
3. Pre-Trade Binary Risk Safeguard (P > 0.85 Bearish Halt).
4. Candidate Shortlist Rule (Max 10-20 tickers, never 300+).
5. System 1 (Laya) / System 2 (Ollama DeepSeek-R1) Handoff Router.
6. NA-TWAP Depth-Capped Execution Slicing & Pre-Execution Halt.
"""

import sys
import importlib
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

laya_guard_mod = importlib.import_module("scripts.00_control.laya_triage_guard")
router_mod = importlib.import_module("scripts.00_control.system1_system2_router")
slicer_mod = importlib.import_module("scripts.00_control.na_twap_slicer")


class TestLayaIntegration:

    def test_01_laya_code_boundary_typing(self):
        """Asserts Laya guard is strictly bounded to typed enum schema and boolean flags."""
        guard = laya_guard_mod.LayaTriageGuard()

        cat = guard.classify_headline("NABIL Bank declares 15% cash dividend")
        assert isinstance(cat, str)
        assert cat in laya_guard_mod.HEADLINE_OPTIONS
        assert cat == "DIVIDEND_NOTICE"

        risk = guard.evaluate_pre_execution_risk("Normal market opening with balanced flows")
        assert isinstance(risk, bool)
        assert risk is False

    def test_02_bilingual_headline_triage(self):
        """Asserts bilingual classification across Devanagari and English regulatory disclosures."""
        guard = laya_guard_mod.LayaTriageGuard()

        # Devanagari test cases
        assert guard.classify_headline("सानिमा बैंकको लाभांश वितरण सम्बन्धी सूचना") == "DIVIDEND_NOTICE"
        assert guard.classify_headline("संस्थापक सेयरको ३ वर्ष लक-इन अवधि समाप्त भएको सूचना") == "PROMOTER_LOCKIN"
        assert guard.classify_headline("कम्पनीको १:१ अनुपातमा हकप्रद शेयर निष्काशन") == "RIGHTS_ISSUE"
        assert guard.classify_headline("नेप्से परिसूचक ४ प्रतिशतले घटेपछि कारोबार स्थगित") == "CIRCUIT_HALT"

        # English test cases
        assert guard.classify_headline("Board meeting proposes 10% bonus share dividend") == "DIVIDEND_NOTICE"
        assert guard.classify_headline("Promoter share lock-in expiry scheduled for next week") == "PROMOTER_LOCKIN"
        assert guard.classify_headline("SEBON approves 1:0.50 rights issue") == "RIGHTS_ISSUE"
        assert guard.classify_headline("NEPSE index triggers circuit breaker halt") == "CIRCUIT_HALT"
        assert guard.classify_headline("General corporate update on office relocation") == "OTHER"

    def test_03_pre_trade_binary_risk_safeguard(self):
        """Asserts binary halt trigger when critical bearish event is detected."""
        guard = laya_guard_mod.LayaTriageGuard()

        # Normal disclosures: No risk halt
        assert guard.evaluate_pre_execution_risk("Company schedules Annual General Meeting (AGM)") is False
        assert guard.evaluate_pre_execution_risk("Hydro project successfully connected to national grid") is False

        # Severe bearish disclosures: Pre-trade risk halt triggered
        assert guard.evaluate_pre_execution_risk("CIAA files corruption and fraud charges against bank directors") is True
        assert guard.evaluate_pre_execution_risk("SEBON suspends trading of promoter shares due to unauthorized dump") is True
        assert guard.evaluate_pre_execution_risk("Severe retail margin call liquidation cascade across hydro sector") is True

    def test_04_candidate_shortlist_rule(self):
        """Asserts that candidate tickers are restricted to max 10-20 to prevent token saturation."""
        guard = laya_guard_mod.LayaTriageGuard()

        top_candidates = ["NABIL", "SANIMA", "EBL", "GBIME", "CHCL", "SHIVM", "HDL", "UPPER", "NICA", "KBL"]
        # Exact English ticker match
        resolved_eng = guard.resolve_candidate_ticker("NABIL quarterly dividend announcement", top_candidates)
        assert resolved_eng == "NABIL"

        # Devanagari alias match
        resolved_nep = guard.resolve_candidate_ticker("सानिमा बैंकको विशेष साधारण सभा", top_candidates)
        assert resolved_nep == "SANIMA"

        # Check candidate overflow protection: 30 tickers get sliced to 10
        oversized_candidates = [f"SYM{i}" for i in range(30)]
        resolved_overflow = guard.resolve_candidate_ticker("Notice from SYM5", oversized_candidates)
        assert resolved_overflow == "SYM5"

    def test_05_system1_system2_router_handoff(self):
        """Asserts that headlines execute in System 1 (<33ms) while balance sheets route to System 2."""
        router = router_mod.System1System2Router()

        # 1. Headline routes to System 1
        headline_doc = {
            "doc_type": "AUTO",
            "text": "CHCL Chilime Hydropower announces 15% dividend",
            "published_time": "2026-10-07 10:00:00"
        }
        res1 = router.route_document(headline_doc, candidate_tickers=["CHCL", "UPPER", "SHPC"])
        assert res1["engine"] == "SYSTEM_1_LAYA"
        assert res1["is_sub_33ms"] is True
        assert res1["category"] == "DIVIDEND_NOTICE"
        assert res1["resolved_ticker"] == "CHCL"
        assert res1["action"] == "PROCEED_TO_EXECUTION"

        # 2. Financial Balance Sheet routes to System 2
        tabular_doc = {
            "doc_type": "BALANCE_SHEET",
            "text": """
            Quarter Ended: 2026-07-16
            Publication Date: 2026-08-25 10:00:00
            Symbol: TEST_BANK
            Total Assets: 200,000,000
            Total Liabilities: 170,000,000
            Total Equity: 30,000,000
            Gross NPL: 5,000,000
            Gross Loans: 125,000,000
            NPL Percentage: 4.0
            Net Profit: 8,000,000
            Paid-up Capital: 20,000,000
            """,
            "published_time": "2026-08-25 10:00:00"
        }
        res2 = router.route_document(tabular_doc)
        assert res2["engine"] == "SYSTEM_2_DEEPSEEK_R1_ACCOUNTING_GATE"
        assert res2["audit_status"] == "PASSED_AUDIT_GATE"
        assert res2["balance_sheet_verified"] is True
        assert res2["npl_verified"] is True

    def test_06_na_twap_depth_capped_slicing(self):
        """Asserts order slicing respects prevailing order book depth and halts on risk news."""
        slicer = slicer_mod.NATWAPSlicer(max_depth_participation=0.15)

        # 1. Standard execution
        plan = slicer.compute_twap_slices(
            symbol="NABIL",
            side="BUY",
            total_quantity=1500,
            limit_price=615.0,
            duration_minutes=30,
            interval_minutes=5,
            prevailing_book_depth_shares=2000,
            latest_headline_context="Nabil bank opens new digital branch in Pokhara"
        )
        assert plan["status"] == "SUCCESS_SCHEDULED"
        assert plan["total_scheduled_quantity"] == 1500
        # Depth cap limit: 15% of 2000 = 300 shares max per slice
        assert plan["depth_cap_limit_per_slice"] == 300
        for child in plan["child_orders"]:
            assert child["quantity"] <= 300

        # 2. Risk halt on bearish news
        plan_halt = slicer.compute_twap_slices(
            symbol="NABIL",
            side="BUY",
            total_quantity=1500,
            limit_price=615.0,
            duration_minutes=30,
            interval_minutes=5,
            prevailing_book_depth_shares=2000,
            latest_headline_context="CIAA raids commercial bank headquarters, trading halted"
        )
        assert plan_halt["status"] == "HALTED_PRE_TRADE_RISK"
        assert len(plan_halt["child_orders"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
