#!/usr/bin/env python3
"""
scripts/00_control/laya_triage_guard.py

Laya System 1 Triage Guard (Sub-33ms Execution Boundary)
=========================================================
Strictly scoped interface wrapping Laya as a fast System 1 triage gatekeeper.

Operational Constraints:
1. Physical Code Boundary: Does NOT handle open-ended generation, long text,
   or numerical price forecasting.
2. Strict Schema Outputs: Returns only fixed str categories or bool flags.
3. Sub-33ms Latency: Fast choice / noul heads for real-time market depth guardrails.
4. Candidate Shortlist Rule: Never passes 300+ NEPSE tickers at once. Enforces
   a maximum of 10-20 candidate tickers via pre-filtered sector/volume shortlists.

Use Cases:
  - classify_headline(text): Devnagari / English news triage
      ["PROMOTER_LOCKIN", "DIVIDEND_NOTICE", "RIGHTS_ISSUE", "CIRCUIT_HALT", "OTHER"]
  - evaluate_pre_execution_risk(headline): Binary pre-trade halt safeguard (P(bearish) > 0.85)
  - resolve_candidate_ticker(text, candidates): Top-10 candidate choice head
"""

import os
import sys
import re
import time
import logging
from typing import List, Optional, Dict, Any


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("laya_guard")

# Permitted categorical options (Fixed Enum Schema)
HEADLINE_OPTIONS = [
    "PROMOTER_LOCKIN",
    "DIVIDEND_NOTICE",
    "RIGHTS_ISSUE",
    "CIRCUIT_HALT",
    "OTHER"
]

# Devanagari & English keyword patterns for fast-path deterministic validation
DEVANAGARI_PATTERNS = {
    "PROMOTER_LOCKIN": [r"संस्थापक", r"लक[- ]?इन", r"अवधि समाप्त", r"सेयर फुक्का"],
    "DIVIDEND_NOTICE": [r"लाभांश", r"बोनस", r"नगद लाभांश", r"प्रतिफल"],
    "RIGHTS_ISSUE": [r"हकप्रद", r"राइट शेयर", r"हकप्रद शेयर"],
    "CIRCUIT_HALT": [r"सर्किट", r"कारोबार स्थगित", r"कारोबार बन्द", r"नेप्से परिसूचक"],
}

ENGLISH_PATTERNS = {
    "PROMOTER_LOCKIN": [r"promoter", r"lock[- ]?in", r"expiry", r"unfreeze"],
    "DIVIDEND_NOTICE": [r"dividend", r"bonus share", r"cash dividend", r"book closure"],
    "RIGHTS_ISSUE": [r"right share", r"rights issue", r"ratio 1:"],
    "CIRCUIT_HALT": [r"circuit breaker", r"halted", r"market suspended", r"trading halt"],
}

BEARISH_KEYWORDS = [
    r"scam", r"fraud", r"investigation", r"cbi", r"ciaa", r"halted", r"suspended",
    r"npl surges", r"loss widens", r"liquidation", r"margin call", r"dump", r"selloff",
    r"market crash", r"penalty", r"blacklisted",
    r"कारोबार रोक्का", r"घोटाला", r"कारबाही", r"नोक्सानी", r"सस्पेन्ड", r"गिरावट"
]



class LayaTriageGuard:
    """
    Tightly-scoped System 1 Triage Guard.
    Physically prevented from open-ended generation or numerical math.
    """

    def __init__(self, model_name: Optional[str] = None, use_accelerate: bool = True):
        self.model_name = model_name or os.environ.get("LAYA_MODEL_NAME")
        self.use_accelerate = use_accelerate
        self.agent = None
        self._load_agent_safe()

    def _load_agent_safe(self):
        """Attempts to preload resident checkpoint in VRAM; falls back to deterministic fast engine if offline."""
        if not self.model_name or os.environ.get("LAYA_FAST_PATH_ONLY") == "1":
            logger.info("Laya initialized in sub-millisecond fast-path execution mode.")
            return

        try:
            import laya
            if hasattr(laya, "load"):
                logger.info(f"Initializing Laya agent with {self.model_name}...")
                self.agent = laya.load(self.model_name, fast=self.use_accelerate)
                logger.info("Laya resident checkpoint preloaded in memory.")
        except Exception as e:
            logger.info(f"Laya agent running in fast-path deterministic mode: {e}")
            self.agent = None


    def classify_headline(self, headline_text: str) -> str:
        """
        STRICT USE CASE 1: 33ms Devnagari/English News Triage.
        Returns one of HEADLINE_OPTIONS.
        """
        start_t = time.perf_counter()
        clean_text = headline_text.strip()

        # Try native Laya agent if resident and available
        if self.agent and hasattr(self.agent, "decide"):
            try:
                # Use Laya choice head
                res = self.agent.decide(text=clean_text, options=HEADLINE_OPTIONS)
                elapsed_ms = (time.perf_counter() - start_t) * 1000
                logger.debug(f"Laya choice executed in {elapsed_ms:.2f}ms: {res}")
                if hasattr(res, "selected_option") and res.selected_option in HEADLINE_OPTIONS:
                    return res.selected_option
                if isinstance(res, str) and res in HEADLINE_OPTIONS:
                    return res
            except Exception as e:
                logger.debug(f"Laya decide fallback: {e}")

        # Deterministic sub-millisecond bilingual regex engine
        selected = self._regex_triage(clean_text)
        elapsed_ms = (time.perf_counter() - start_t) * 1000
        logger.debug(f"Fast-path triage executed in {elapsed_ms:.2f}ms: {selected}")
        return selected

    def evaluate_pre_execution_risk(self, headline: str) -> bool:
        """
        STRICT USE CASE 2: 33ms Pre-Trade Binary Safeguard (noul).
        Enforce hard confidence gate: if P(bearish) > 0.85, trigger risk halt (True).
        """
        clean_text = headline.strip()

        # Try native Laya agent noul / binary verification
        if self.agent and hasattr(self.agent, "predict"):
            try:
                stmt = f"Is this news headline extremely bearish for market execution: {clean_text}"
                res = self.agent.predict(statement=stmt)
                prob_bearish = getattr(res, "prob_true", 0.0)
                return bool(prob_bearish > 0.85)
            except Exception as e:
                logger.debug(f"Laya predict fallback: {e}")

        # Deterministic fast-path check
        for pattern in BEARISH_KEYWORDS:
            if re.search(pattern, clean_text, re.IGNORECASE):
                return True
        return False

    def resolve_candidate_ticker(self, headline_text: str, candidate_tickers: List[str]) -> Optional[str]:
        """
        CANDIDATE SHORTLIST RULE:
        Never pass all 300+ NEPSE tickers at once.
        Candidate list MUST be pre-filtered to max 10-20 tickers.
        """
        if len(candidate_tickers) > 20:
            logger.warning(f"Candidate count ({len(candidate_tickers)}) exceeds institutional limit (20). Slicing top 10.")
            candidate_tickers = candidate_tickers[:10]

        if not candidate_tickers:
            return None

        # Try native Laya choice head over the 10 candidates
        if self.agent and hasattr(self.agent, "decide"):
            try:
                res = self.agent.decide(text=headline_text, options=candidate_tickers)
                sel = getattr(res, "selected_option", None)
                if sel in candidate_tickers:
                    return sel
            except Exception as e:
                logger.debug(f"Laya ticker choice fallback: {e}")

        # Sub-millisecond token matching over candidate shortlist
        upper_text = headline_text.upper()
        for sym in candidate_tickers:
            sym_clean = sym.upper().strip()
            # Exact boundary match
            if re.search(rf"\b{re.escape(sym_clean)}\b", upper_text):
                return sym_clean

        # Devanagari name matching against candidate shortlist
        nepali_map = {
            "सानिमा": "SANIMA", "नबिल": "NABIL", "एभरेष्ट": "EBL",
            "शिवम": "SHIVM", "चिलिमे": "CHCL", "ग्लोबल": "GBIME",
            "माछापुच्छ्रे": "MBL", "सिद्धार्थ": "SBL", "सिटिजन्स": "CZBIL",
            "एनआइसी": "NICA"
        }
        for nep_name, sym in nepali_map.items():
            if nep_name in headline_text and sym in candidate_tickers:
                return sym

        return candidate_tickers[0] if candidate_tickers else None


    def _regex_triage(self, text: str) -> str:
        """Bilingual pattern classifier matching English & Devanagari financial phrases."""
        # Check Devanagari patterns
        for cat, patterns in DEVANAGARI_PATTERNS.items():
            for p in patterns:
                if re.search(p, text):
                    return cat

        # Check English patterns
        for cat, patterns in ENGLISH_PATTERNS.items():
            for p in patterns:
                if re.search(p, text, re.IGNORECASE):
                    return cat

        return "OTHER"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    guard = LayaTriageGuard()

    # Test 1: Devanagari dividend headline
    dev_text = "सानिमा बैंक लिमिटेडको १०.५ प्रतिशत नगद लाभांश वितरण सम्बन्धी सूचना"
    c1 = guard.classify_headline(dev_text)
    print(f"Devanagari Test: '{dev_text}' -> Category: {c1}")


    # Test 2: English promoter lockin headline
    eng_text = "SARBTM announces 3-year promoter share lock-in expiry date"
    c2 = guard.classify_headline(eng_text)
    print(f"English Test: '{eng_text}' -> Category: {c2}")

    # Test 3: Pre-trade risk trigger
    bearish_news = "SEBON suspends trading of hydro company following fraud investigation"
    is_risk = guard.evaluate_pre_execution_risk(bearish_news)
    print(f"Risk Check Test: '{bearish_news}' -> Halt Execution: {is_risk}")

    # Test 4: Candidate Shortlist Rule
    candidates = ["NABIL", "SANIMA", "EBL", "GBIME", "CHCL"]
    sym = guard.resolve_candidate_ticker(dev_text, candidates)
    print(f"Shortlist Ticker Match: '{dev_text}' -> Selected: {sym}")


if __name__ == "__main__":
    main()
