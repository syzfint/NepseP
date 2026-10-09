#!/usr/bin/env python3
"""
scripts/00_control/system1_system2_router.py

System 1 / System 2 Handoff Router for NEPSE Disclosures
=========================================================
Implements the institutional System 1 / System 2 document routing architecture:

               INCOMING REGULATORY / FINANCIAL DOCUMENT
                                  │
                                  ▼
               ┌─────────────────────────────────────┐
               │  Document Complexity Inspection     │
               └──────────────────┬──────────────────┘
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
[Is Short Text / Headline?]                       [Is PDF / Balance Sheet?]
        │                                                   │
        ▼                                                   ▼
System 1: Laya Triage (< 33 ms)                  System 2: Ollama DeepSeek-R1
- Fast bilingual headline triage                 - Full NFRS PDF table extractor
- Pre-trade execution risk gate (P > 0.85)       - Deterministic accounting gate
- Top 10-20 candidate ticker resolution          - Assets == Liab + Equity (±0.01%)
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("system_router")

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from .laya_triage_guard import LayaTriageGuard
from .deterministic_accounting_auditor import DeepResearchAccountingParser, DeterministicAccountingGate

ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")


class System1System2Router:
    """
    Decoupled router directing incoming documents to either:
      - System 1 (Laya): Sub-33ms headline classification & pre-trade risk guardrail.
      - System 2 (Ollama DeepSeek-R1 + Accounting Gate): Deep tabular balance sheet extraction.
    """

    def __init__(self, laya_guard: Optional[LayaTriageGuard] = None):
        self.system1_laya = laya_guard or LayaTriageGuard()
        self.system2_parser = DeepResearchAccountingParser()
        self.system2_gate = DeterministicAccountingGate()

    def route_document(self, document_payload: Dict[str, Any], candidate_tickers: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Inspects document payload and routes to System 1 or System 2.
        
        document_payload schema:
          - "doc_type": "HEADLINE" | "BREAKING_ALERT" | "NFRS_PDF" | "BALANCE_SHEET" | "AUTO"
          - "text": str
          - "source": str
          - "published_time": str
          - "file_path": Optional[str]
        """
        start_t = time.perf_counter()
        doc_type = document_payload.get("doc_type", "AUTO").upper()
        text_content = document_payload.get("text", "")
        file_path = document_payload.get("file_path", "")

        is_system2 = (
            doc_type in ["NFRS_PDF", "BALANCE_SHEET", "QUARTERLY_REPORT"] or
            str(file_path).lower().endswith(".pdf") or
            (doc_type == "AUTO" and len(text_content) > 600 and ("balance sheet" in text_content.lower() or "assets" in text_content.lower()))
        )

        if not is_system2:
            # =========================================================================
            # SYSTEM 1: LAYA TRIAGE (Target < 33 ms)
            # =========================================================================
            category = self.system1_laya.classify_headline(text_content)
            is_risk_halt = self.system1_laya.evaluate_pre_execution_risk(text_content)

            # Candidate shortlist resolution (never pass 300+ tickers)
            shortlist = candidate_tickers[:10] if candidate_tickers else []
            resolved_ticker = self.system1_laya.resolve_candidate_ticker(text_content, shortlist) if shortlist else None

            elapsed_ms = (time.perf_counter() - start_t) * 1000
            return {
                "engine": "SYSTEM_1_LAYA",
                "execution_time_ms": round(elapsed_ms, 2),
                "is_sub_33ms": elapsed_ms <= 33.0,
                "headline": text_content[:150],
                "category": category,
                "pre_execution_risk_halt": is_risk_halt,
                "resolved_ticker": resolved_ticker,
                "candidate_count_evaluated": len(shortlist),
                "action": "HALT_TRADING_DUE_TO_RISK" if is_risk_halt else "PROCEED_TO_EXECUTION"
            }
        else:
            # =========================================================================
            # SYSTEM 2: OLLAMA DEEPSEEK-R1 + DETERMINISTIC ACCOUNTING GATE
            # =========================================================================
            parsed_figures = self.system2_parser.parse_with_deterministic_regex_fallback(text_content)
            audit_result = self.system2_gate.process_and_route(parsed_figures)

            elapsed_ms = (time.perf_counter() - start_t) * 1000
            return {
                "engine": "SYSTEM_2_DEEPSEEK_R1_ACCOUNTING_GATE",
                "execution_time_ms": round(elapsed_ms, 2),
                "symbol": parsed_figures.get("symbol"),
                "audit_status": audit_result.get("status"),
                "balance_sheet_verified": audit_result.get("checks", {}).get("balance_sheet_identity", {}).get("passed", False),
                "npl_verified": audit_result.get("checks", {}).get("npl_verification", {}).get("passed", False),
                "action": "COMMITTED_TO_DUCKDB_LAKEHOUSE" if audit_result.get("status") == "PASSED_AUDIT_GATE" else "ROUTED_TO_MANUAL_REVIEW_QUEUE"
            }


def main():
    router = System1System2Router()

    print("=" * 70)
    print("TESTING SYSTEM 1 / SYSTEM 2 HANDOFF ROUTER")
    print("=" * 70)

    # Test 1: Short text breaking headline -> Routes to System 1 (Laya)
    headline_doc = {
        "doc_type": "AUTO",
        "text": "NABIL Bank announces 22% bonus share dividend for FY 2080/81",
        "published_time": "2026-10-07 11:30:00"
    }
    candidates = ["NABIL", "GBIME", "EBL", "NICA", "SANIMA"]
    res1 = router.route_document(headline_doc, candidate_tickers=candidates)
    print("\nResult 1 (Short Headline):")
    print(res1)

    # Test 2: Extreme bearish headline -> Triggers pre-trade risk halt in System 1
    bearish_doc = {
        "doc_type": "AUTO",
        "text": "Breaking: CIAA launches corruption fraud investigation against hydro board, trading halted",
        "published_time": "2026-10-07 11:45:00"
    }
    res2 = router.route_document(bearish_doc)
    print("\nResult 2 (Bearish Alert):")
    print(res2)

    # Test 3: Complex NFRS Balance Sheet -> Hands off to System 2 (Ollama / Accounting Gate)
    nfrs_doc = {
        "doc_type": "NFRS_PDF",
        "text": """
        Quarter Ended: 2026-07-16
        Publication Date: 2026-08-25 10:00:00
        Symbol: SCB
        Total Assets: 100,000,000
        Total Liabilities: 85,000,000
        Total Equity: 15,000,000
        Gross NPL: 2,000,000
        Gross Loans: 80,000,000
        NPL Percentage: 2.5
        Net Profit: 4,000,000
        Paid-up Capital: 10,000,000
        """,
        "published_time": "2026-08-25 10:00:00"
    }
    res3 = router.route_document(nfrs_doc)
    print("\nResult 3 (NFRS PDF Document):")
    print(res3)


if __name__ == "__main__":
    main()
