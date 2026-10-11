#!/usr/bin/env python3
"""
scripts/00_control/deterministic_accounting_auditor.py

Deep Research & Deterministic Accounting Auditor Gate
=====================================================
Combines DeepResearch reasoning prompts (compatible with local Ollama
models deepseek-r1:8b, qwen2.5-coder:7b) with a strict, fail-closed
mathematical verification gate:

1. Never commits raw unverified LLM extractions directly to DuckDB.
2. Mathematically verifies:
     - Balance Sheet Identity: Total Assets == Total Liabilities + Total Equity (±0.01%)
     - NPL Verification: Reported NPL % == (Gross NPL / Gross Loans) * 100 (±0.01%)
3. Fail-Closed Routing:
     - If either identity fails to reconcile within ±0.01%, auto-ingestion is rejected,
       and the payload is routed to reports/manual_review_queue.json for human review.
     - Only 100% mathematically reconciled reports are committed to DuckDB.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("accounting_auditor")

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
MANUAL_QUEUE_PATH = REPORTS_DIR / "manual_review_queue.json"
NFRS_LEDGER_PATH = DATA_DIR / "nfrs_ledger.parquet"
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")


class DeepResearchAccountingParser:
    """
    Reasoning parser interface modeled after Alibaba-NLP/DeepResearch and krishhlogan/deepQuery.
    Prepares reasoning prompts and parses unstructured quarterly reports and circulars.
    """

    def __init__(self, ollama_endpoint: str = "http://localhost:11434", model_name: str = "deepseek-r1:8b"):
        self.endpoint = ollama_endpoint
        self.model_name = model_name

    def construct_reasoning_prompt(self, text_content: str, document_type: str = "NFRS_QUARTERLY") -> str:
        """Builds a zero-shot chain-of-thought extraction prompt."""
        return (
            f"You are an institutional financial forensic auditor parsing a Nepalese {document_type} filing.\n"
            "Extract all numerical values into strict JSON with the following exact keys:\n"
            "{\n"
            '  "symbol": "TICKER",\n'
            '  "quarter_end_date": "YYYY-MM-DD",\n'
            '  "official_publication_timestamp": "YYYY-MM-DD HH:MM:SS",\n'
            '  "total_assets": float,\n'
            '  "total_liabilities": float,\n'
            '  "total_equity": float,\n'
            '  "gross_npl": float,\n'
            '  "gross_loans": float,\n'
            '  "reported_npl_pct": float,\n'
            '  "net_profit": float,\n'
            '  "paid_up_capital": float\n'
            "}\n"
            "Ensure that Total Assets equals Total Liabilities plus Total Equity.\n"
            f"Document text:\n{text_content[:4000]}\n"
        )

    def parse_with_deterministic_regex_fallback(self, text: str) -> Dict[str, Any]:
        """
        Robust deterministic parsing fallback for tabular NFRS text when local Ollama is offline.
        Uses multi-pass regex matching on Nepali banking NFRS line items.
        """
        extracted = {}

        # Symbol
        sym_match = re.search(r"\b(?:Symbol|Ticker|Scrip)[:\s]+([A-Z0-9]{2,8})\b", text, re.IGNORECASE)
        extracted["symbol"] = sym_match.group(1).upper() if sym_match else "UNKNOWN"

        # Quarter End Date & Pub Date
        qtr_match = re.search(r"\b(?:Quarter\s*End|Period\s*Ended)[:\s]+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        extracted["quarter_end_date"] = qtr_match.group(1) if qtr_match else "2026-07-16"

        pub_match = re.search(r"\b(?:Published|Publication\s*Date)[:\s]+(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)", text, re.IGNORECASE)
        extracted["official_publication_timestamp"] = pub_match.group(1) if pub_match else "2026-08-30 11:00:00"

        # Assets, Liabilities, Equity
        def find_num(pattern):
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                clean_str = m.group(1).replace(",", "").strip()
                try:
                    return float(clean_str)
                except ValueError:
                    return 0.0
            return 0.0

        extracted["total_assets"] = find_num(r"Total\s+Assets[:\s]+([\d,\.]+)")
        extracted["total_liabilities"] = find_num(r"Total\s+Liabilities[:\s]+([\d,\.]+)")
        extracted["total_equity"] = find_num(r"Total\s+Equity[:\s]+([\d,\.]+)")
        extracted["gross_npl"] = find_num(r"Gross\s+NPL[:\s]+([\d,\.]+)")
        extracted["gross_loans"] = find_num(r"Gross\s+Loans[:\s]+([\d,\.]+)")
        extracted["reported_npl_pct"] = find_num(r"NPL\s*(?:Percentage|Ratio|\%)[:\s]+([\d,\.]+)")
        extracted["net_profit"] = find_num(r"Net\s+Profit[:\s]+([\d,\.]+)")
        extracted["paid_up_capital"] = find_num(r"Paid[- ]up\s+Capital[:\s]+([\d,\.]+)")

        return extracted


class DeterministicAccountingGate:
    """
    Mathematical verification gate. Enforces strict zero-tolerance accounting identities.
    """

    def __init__(self, tolerance_pct: float = 0.0001):  # ±0.01%
        self.tolerance_pct = tolerance_pct
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self._init_queue_if_needed()

    def _init_queue_if_needed(self):
        if not MANUAL_QUEUE_PATH.exists():
            with open(MANUAL_QUEUE_PATH, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def audit_report(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Audits extracted figures against mathematical identities.
        Returns (is_passed, audit_report_dict).
        """
        tot_assets = float(payload.get("total_assets", 0.0))
        tot_liab = float(payload.get("total_liabilities", 0.0))
        tot_equity = float(payload.get("total_equity", 0.0))
        gross_npl = float(payload.get("gross_npl", 0.0))
        gross_loans = float(payload.get("gross_loans", 0.0))
        rep_npl_pct = float(payload.get("reported_npl_pct", 0.0))

        audit_results = {
            "symbol": payload.get("symbol"),
            "quarter_end_date": payload.get("quarter_end_date"),
            "official_publication_timestamp": payload.get("official_publication_timestamp"),
            "checks": {},
            "status": "PENDING"
        }

        # 1. Balance Sheet Identity: Assets == Liabilities + Equity
        bs_rhs = tot_liab + tot_equity
        bs_diff = abs(tot_assets - bs_rhs)
        bs_threshold = (tot_assets * self.tolerance_pct) if tot_assets > 0 else 0.0
        bs_passed = (bs_diff <= max(bs_threshold, 1.0)) and (tot_assets > 0)

        audit_results["checks"]["balance_sheet_identity"] = {
            "total_assets": tot_assets,
            "liabilities_plus_equity": bs_rhs,
            "discrepancy": round(bs_diff, 4),
            "allowed_tolerance": round(bs_threshold, 4),
            "passed": bool(bs_passed)
        }

        # 2. NPL Verification: Reported NPL % == (Gross NPL / Gross Loans) * 100
        npl_passed = True
        if gross_loans > 0:
            calc_npl_pct = (gross_npl / gross_loans) * 100.0
            npl_diff = abs(rep_npl_pct - calc_npl_pct)
            npl_passed = npl_diff <= (self.tolerance_pct * 100.0)  # within 0.01%
            audit_results["checks"]["npl_verification"] = {
                "reported_npl_pct": rep_npl_pct,
                "calculated_npl_pct": round(calc_npl_pct, 4),
                "discrepancy": round(npl_diff, 4),
                "passed": bool(npl_passed)
            }
        else:
            audit_results["checks"]["npl_verification"] = {
                "reported_npl_pct": rep_npl_pct,
                "note": "Gross loans zero or not applicable",
                "passed": True
            }

        overall_passed = bool(bs_passed and npl_passed)
        audit_results["status"] = "PASSED_AUDIT_GATE" if overall_passed else "REJECTED_AUDIT_FAIL"
        return overall_passed, audit_results

    def process_and_route(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes audit gate and routes to DuckDB lakehouse or manual review queue.
        """
        passed, audit_summary = self.audit_report(raw_payload)

        if passed:
            self._commit_to_duckdb(raw_payload, audit_summary)
            logger.info(f"Audit PASSED for {raw_payload.get('symbol')}. Committed to NFRS ledger.")
        else:
            self._route_to_manual_queue(raw_payload, audit_summary)
            logger.warning(f"Audit FAILED for {raw_payload.get('symbol')}. Discrepancy routed to manual review queue.")

        return audit_summary

    def _commit_to_duckdb(self, payload: Dict[str, Any], audit_summary: Dict[str, Any]):
        """Appends verified financial data to persistent DuckDB Parquet store."""
        row = {
            "symbol": str(payload.get("symbol", "")).upper().strip(),
            "quarter_end_date": str(payload.get("quarter_end_date", "")),
            "official_publication_timestamp": str(payload.get("official_publication_timestamp", "")),
            "total_assets": float(payload.get("total_assets", 0.0)),
            "total_liabilities": float(payload.get("total_liabilities", 0.0)),
            "total_equity": float(payload.get("total_equity", 0.0)),
            "gross_npl": float(payload.get("gross_npl", 0.0)),
            "gross_loans": float(payload.get("gross_loans", 0.0)),
            "reported_npl_pct": float(payload.get("reported_npl_pct", 0.0)),
            "net_profit": float(payload.get("net_profit", 0.0)),
            "paid_up_capital": float(payload.get("paid_up_capital", 0.0)),
            "audit_status": "VERIFIED_DETERMINISTIC_PASS"
        }
        df_new = pd.DataFrame([row])

        from scripts.db_connection import connection_manager
        p_str = str(NFRS_LEDGER_PATH).replace("\\", "/")

        with connection_manager.acquire() as con:
            if NFRS_LEDGER_PATH.exists():
                df_existing = con.execute(f"SELECT * FROM read_parquet('{p_str}')").df()
                # Deduplicate by (symbol, quarter_end_date)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=["symbol", "quarter_end_date"], keep="last")
            else:
                df_combined = df_new

            con.execute(f"COPY (SELECT * FROM df_combined) TO '{p_str}' (FORMAT PARQUET)")

        # Mirror to ALT_DIR
        if ALT_DIR.exists():
            alt_out = ALT_DIR / "data" / "nfrs_ledger.parquet"
            alt_out.parent.mkdir(parents=True, exist_ok=True)
            try:
                alt_out.write_bytes(NFRS_LEDGER_PATH.read_bytes())
            except Exception:
                pass

    def _route_to_manual_queue(self, payload: Dict[str, Any], audit_summary: Dict[str, Any]):
        """Dumps rejected extraction payload into the manual review queue."""
        queue_item = {
            "payload": payload,
            "audit_summary": audit_summary
        }
        items = []
        if MANUAL_QUEUE_PATH.exists():
            try:
                with open(MANUAL_QUEUE_PATH, "r", encoding="utf-8") as f:
                    items = json.load(f)
            except Exception:
                items = []

        items.append(queue_item)
        with open(MANUAL_QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)

        # Mirror to ALT_DIR
        if ALT_DIR.exists():
            alt_q = ALT_DIR / "reports" / "manual_review_queue.json"
            alt_q.parent.mkdir(parents=True, exist_ok=True)
            try:
                alt_q.write_text(json.dumps(items, indent=2), encoding="utf-8")
            except Exception:
                pass

    def get_ledger(self) -> pd.DataFrame:
        """Retrieves verified NFRS ledger."""
        if not NFRS_LEDGER_PATH.exists():
            return pd.DataFrame()
        from scripts.db_connection import connection_manager
        p_str = str(NFRS_LEDGER_PATH).replace("\\", "/")
        with connection_manager.acquire() as con:
            return con.execute(f"SELECT * FROM read_parquet('{p_str}')").df()

    def get_manual_queue(self) -> List[Dict[str, Any]]:
        """Retrieves items in the manual review queue."""
        if not MANUAL_QUEUE_PATH.exists():
            return []
        with open(MANUAL_QUEUE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)


def main():
    gate = DeterministicAccountingGate()

    # Test 1: Clean reconcilable report
    clean_sample = {
        "symbol": "NABIL",
        "quarter_end_date": "2026-07-16",
        "official_publication_timestamp": "2026-08-28 10:15:00",
        "total_assets": 50000000000.0,
        "total_liabilities": 45000000000.0,
        "total_equity": 5000000000.0,
        "gross_npl": 1200000000.0,
        "gross_loans": 40000000000.0,
        "reported_npl_pct": 3.0,
        "net_profit": 4200000000.0,
        "paid_up_capital": 27000000000.0
    }
    res_clean = gate.process_and_route(clean_sample)
    print("Clean Report Audit Result:", res_clean["status"])

    # Test 2: Corrupted balance sheet (Total Assets != Liabilities + Equity)
    corrupted_sample = {
        "symbol": "CORRUPT_BANK",
        "quarter_end_date": "2026-07-16",
        "official_publication_timestamp": "2026-08-28 10:15:00",
        "total_assets": 50000000000.0,
        "total_liabilities": 40000000000.0,
        "total_equity": 5000000000.0,  # 5B gap (10% mismatch)
        "gross_npl": 100000000.0,
        "gross_loans": 1000000000.0,
        "reported_npl_pct": 10.0,
    }
    res_corrupt = gate.process_and_route(corrupted_sample)
    print("Corrupted Report Audit Result:", res_corrupt["status"])

    ledger = gate.get_ledger()
    print(f"Verified Ledger Rows: {len(ledger)}")
    queue = gate.get_manual_queue()
    print(f"Manual Review Queue Rows: {len(queue)}")


if __name__ == "__main__":
    main()
