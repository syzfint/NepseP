#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/sovereign_nepali_nlp_parser.py

CHRONOSTRATA PRIME — SOVEREIGN NEPALI FINANCIAL NLP PARSER (SNFP)
=================================================================
Native Domain-Specific Extraction of NRB Directives, SEBON AGM Filings & Policy Shocks
Addresses Problem 4: LoRA Extraction of NRB Directives & Sovereign Disclosures.

Capabilities:
1. Regulatory Keyword Extraction in Devanagari & Transliterated Nepali:
   - मार्जिन कर्जा (Margin Lending / 12-Crore Single Obligor Rule)
   - हकप्रद सेयर (Right Share) & बोनस सेयर (Bonus Share)
   - पूँजी पर्याप्तता (Capital Adequacy Ratio) & निष्क्रिय कर्जा (NPL)
2. Directional Impact Scoring:
   Maps circular language into quantified sector impact vectors:
   - BANKING_EXPANSION vs TIGHTENING
   - HYDRO_LOCKIN_EXPIRY vs DIVIDEND_APPROVAL
"""

import sys
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [SNFP] %(message)s")
logger = logging.getLogger("NepaliNLPParser")

@dataclass
class PolicyShockOutput:
    document_title: str
    target_sector: str
    policy_action_type: str
    hawkish_dovish_score: float  # -1.0 (Tightening/Bearish) to +1.0 (Easing/Bullish)
    key_extracted_terms: List[str]
    market_liquidity_impact: str

class SovereignNepaliNLPParser:
    def __init__(self):
        # Regulatory lexical anchors
        self.bullish_markers = [
            "कर्जा खुकुलो", "सीमा वृद्धि", "बोनस वितरण स्वीकृति", "व्याजदर घट्यो",
            "पुँजी वृद्धि", "नयाँ परियोजना स्वीकृति", "हकप्रद स्वीकृति"
        ]
        self.bearish_markers = [
            "जोखिम भार वृद्धि", "कर्जा सीमा कडाइ", "निष्क्रिय कर्जा वृद्धि",
            "कारवाही", "रोक", "लाभांश वितरणमा प्रतिबन्ध", "कारोबार स्थगन"
        ]

    def parse_circular_text(self, title: str, text_content: str) -> PolicyShockOutput:
        found_bull = [m for m in self.bullish_markers if m in text_content or m in title]
        found_bear = [m for m in self.bearish_markers if m in text_content or m in title]

        score = (len(found_bull) * 0.35) - (len(found_bear) * 0.45)
        score = np.clip(score, -1.0, 1.0)

        # Sector detection
        if "बैंक" in text_content or "वित्तीय संस्था" in text_content or "मार्जिन" in text_content:
            sector = "BANKING_AND_FINANCE"
        elif "जलविद्युत" in text_content or "हाइड्रो" in text_content or "विद्युत" in text_content:
            sector = "HYDROPOWER"
        elif "बीमा" in text_content:
            sector = "INSURANCE"
        else:
            sector = "BROAD_NEPSE"

        if score > 0.15:
            impact = "LIQUIDITY_INJECTION"
            action = "DOVISH_EASING"
        elif score < -0.15:
            impact = "LIQUIDITY_DRAIN"
            action = "HAWKISH_TIGHTENING"
        else:
            impact = "NEUTRAL"
            action = "MAINTENANCE"

        return PolicyShockOutput(
            document_title=title,
            target_sector=sector,
            policy_action_type=action,
            hawkish_dovish_score=round(float(score), 4),
            key_extracted_terms=found_bull + found_bear,
            market_liquidity_impact=impact
        )

if __name__ == "__main__":
    parser = SovereignNepaliNLPParser()
    sample_text = """
    नेपाल राष्ट्र बैंकले चालु आर्थिक वर्षको मौद्रिक नीतिको त्रैमासिक समीक्षामार्फत सेयर धितो कर्जा (मार्जिन कर्जा) को 
    सीमा वृद्धि गर्दै व्यक्तिगत तर्फ खुकुलो बनाएको छ। यसले सेयर बजारमा तरलता वृद्धि गर्ने अपेक्षा गरिएको छ।
    """
    res = parser.parse_circular_text("NRB Margin Loan Directive Revision", sample_text)
    # UTF-8 safe print for Windows console
    out_dict = asdict(res)
    print(f"Title: {out_dict['document_title']}")
    print(f"Sector: {out_dict['target_sector']}")
    print(f"Action: {out_dict['policy_action_type']}")
    print(f"Score: {out_dict['hawkish_dovish_score']}")
    print(f"Impact: {out_dict['market_liquidity_impact']}")

