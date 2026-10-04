"""
Classification & Entity Linking Engine for NEPSE Disclosures.

Separates:
1. Ex-Ante Event Importance (Policy Scope, Authority Level, Sector Breadth)
2. Ex-Post Observed Impact (Measured Returns, Turnover, Volatility)

Contains domain mapping rules for NEPSE sector taxonomy and stock tickers.
"""

import re
from typing import Tuple, List, Dict, Any, Optional
from .models import EventCategory, EventScope, DisclosureSource


# Historical M&A and Ticker Mapping Ledger (Point-in-Time Resolution)
HISTORICAL_MERGER_MAP = {
    # Pre-merger symbol: (Canonical active symbol, Merger effective date, Original Sector)
    "NBBL": ("NABIL", "2022-07-11", "COMMERCIAL_BANKS"),   # Nepal Bangladesh Bank -> NABIL
    "MEGA": ("NIMB", "2023-01-11", "COMMERCIAL_BANKS"),    # Mega Bank -> Nepal Investment Mega Bank
    "BOKL": ("NBL", "2023-01-08", "COMMERCIAL_BANKS"),     # Bank of Kathmandu -> Global IME / NBL
    "CBL": ("CZBIL", "2023-05-14", "COMMERCIAL_BANKS"),     # Civil Bank -> Citizens Bank International
    "NCCB": ("KBL", "2023-01-01", "COMMERCIAL_BANKS"),     # NCC Bank -> Kumari Bank
    "CCBL": ("PRVU", "2022-12-25", "COMMERCIAL_BANKS"),    # Century Commercial Bank -> Prabhu Bank
    "JBNL": ("SANIMA", "2022-09-01", "COMMERCIAL_BANKS"),  # Janata Bank -> Global / Sanima
}

# Sector Taxonomy and Symbol mapping for NEPSE (including historical mappings)
SECTOR_SYMBOLS = {
    "COMMERCIAL_BANKS": [
        "NABIL", "GBIME", "NICA", "EBL", "SCB", "SBL", "KBL", "PRVU",
        "SBI", "NBL", "ADBL", "CZBIL", "SANIMA", "LSL", "MBL", "PCBL",
        "NIMB", "NBBL", "MEGA", "BOKL", "CBL", "NCCB", "CCBL"
    ],
    "DEVELOPMENT_BANKS": [
        "GBBL", "MLBL", "MNBBL", "SHINE", "JBBL", "CORBL", "EDBL", "KSBBL"
    ],
    "HYDROPOWER": [
        "CHCL", "UPPER", "SHPC", "AKPL", "API", "RHPL", "BPCL", "HDHPC",
        "KPCL", "MHNL", "NGPL", "RADHI", "RIDI", "SJCL", "SSHPC", "UNHPL"
    ],
    "MICROFINANCE": [
        "CBBL", "DDBL", "FMDBL", "GMFBS", "ILBS", "JOSHI", "MSMBS", "NICLBSL",
        "NUBL", "SKBBL", "SMB", "SWBBL", "USLB", "VLBS", "ALBSL", "ACLBSL"
    ],
    "LIFE_INSURANCE": [
        "LICN", "NLIC", "CLI", "RNLI", "SNLI", "ILI", "PLI", "SJLIC"
    ],
    "NON_LIFE_INSURANCE": [
        "NIL", "SICL", "IGI", "NICL", "PRIN", "RBCL", "SALICO", "SGIC", "SPIL"
    ],
    "MANUFACTURING_PROCESSING": [
        "HDL", "SHIVM", "BNT", "BSL", "UNL", "SARBTM", "GCIL"
    ],
    "HOTELS_TOURISM": [
        "OHL", "SHL", "TRH", "CGH"
    ],
    "INVESTMENT": [
        "CIT", "HIDCL", "NIFRA", "NRN", "CHDC"
    ]
}


def resolve_canonical_ticker(symbol: str, trade_date: Optional[str] = None) -> str:
    """
    Resolves pre-merger or subsidiary surface forms to canonical NEPSE tickers point-in-time.
    If trade_date is provided and precedes the merger, the original pre-merger ticker is preserved.
    """
    sym = symbol.upper().strip()
    if sym in HISTORICAL_MERGER_MAP:
        canonical, effective_date, _ = HISTORICAL_MERGER_MAP[sym]
        if trade_date is None or trade_date >= effective_date:
            return canonical
        return sym
    return sym


def get_sector_for_symbol_at_date(symbol: str, trade_date: Optional[str] = None) -> str:
    """Returns point-in-time sector membership for a given symbol."""
    sym = symbol.upper().strip()
    if sym in HISTORICAL_MERGER_MAP:
        _, effective_date, original_sector = HISTORICAL_MERGER_MAP[sym]
        if trade_date is not None and trade_date < effective_date:
            return original_sector

    for sector, sym_list in SECTOR_SYMBOLS.items():
        if sym in sym_list:
            return sector
    return "GENERAL_MACRO"


class DisclosureClassifier:
    """
    Classifies news text into category, scope, and affected entities with documented rationale.
    """
    VERSION = "v2.1_rule_engine"

    def classify_disclosure(
        self,
        source: DisclosureSource,
        headline: str,
        body_text: str
    ) -> Tuple[EventCategory, EventScope, float, str, str, bool, List[str], List[str], str]:
        """
        Returns:
            (category, scope, confidence, importance_tier, classifier_version,
             affected_broad_market, affected_sectors, affected_symbols, mapping_rationale)
        """
        text = f"{headline} {body_text}".lower()
        
        # 1. Classification & Scope
        category = EventCategory.ISSUER_DISCLOSURE
        scope = EventScope.ISSUER
        importance_tier = "LOW"
        confidence = 0.80
        affected_broad_market = False
        affected_sectors = []
        affected_symbols = []
        rationale_parts = []

        # Monetary Policy Patterns (NRB)
        if any(w in text for w in [
            "monetary policy", "policy rate", "reverse repo", "cash reserve ratio",
            "crr", "margin loan cap", "single borrower limit", "interest rate corridor",
            "statutory liquidity ratio", "slr", "working capital loan guidelines"
        ]) or source == DisclosureSource.NRB and any(w in text for w in ["circular", "directive", "rate"]):
            category = EventCategory.MONETARY_POLICY
            scope = EventScope.BROAD_MARKET
            affected_broad_market = True
            importance_tier = "HIGH"
            confidence = 0.95
            rationale_parts.append("Central bank macroprudential or interest rate directive impacting total banking liquidity and margin leverage.")
            
            # Sub-sectors heavily exposed
            affected_sectors = ["COMMERCIAL_BANKS", "DEVELOPMENT_BANKS", "MICROFINANCE", "INVESTMENT"]

        # Regulatory Rules (SEBON / NEPSE)
        elif any(w in text for w in [
            "sebon directive", "circuit breaker", "broker commission", "margin trading",
            "lock-in period", "promoter share conversion", "ipo quota", "trading halt rule"
        ]) or (source == DisclosureSource.SEBON and any(w in text for w in ["regulation", "directive", "amendment"])):
            category = EventCategory.REGULATORY_RULE
            scope = EventScope.BROAD_MARKET
            affected_broad_market = True
            importance_tier = "HIGH"
            confidence = 0.92
            rationale_parts.append("Securities regulator capital market structure change affecting market-wide market microstructure and trading friction.")

        # Sector Policy (PPA, Capital requirements, Energy ministry, Insurance authority)
        elif any(w in text for w in [
            "power purchase agreement", "ppa", "nea", "insurance authority", "nia capital",
            "commercial bank capital", "microfinance merger mandate", "hydropower tariff"
        ]):
            category = EventCategory.SECTOR_POLICY
            scope = EventScope.SECTOR
            importance_tier = "MEDIUM"
            confidence = 0.88
            
            if any(w in text for w in ["ppa", "hydropower", "nea", "electricity"]):
                affected_sectors.append("HYDROPOWER")
                rationale_parts.append("Energy sector tariff/PPA policy directly impacting cashflows of listed hydropower operators.")
            if any(w in text for w in ["insurance", "life", "non-life"]):
                affected_sectors.extend(["LIFE_INSURANCE", "NON_LIFE_INSURANCE"])
                rationale_parts.append("Insurance regulatory capital mandate impacting underwriting leverage and dividend retention.")
            if any(w in text for w in ["bank", "microfinance", "merger"]):
                affected_sectors.extend(["COMMERCIAL_BANKS", "MICROFINANCE"])
                rationale_parts.append("Consolidation/capital adequacy policy impacting BFIs.")

        # Macroeconomic
        elif any(w in text for w in [
            "inflation", "cpi", "remittance", "foreign exchange reserves", "bop",
            "current account", "fiscal budget", "gdp growth"
        ]):
            category = EventCategory.MACRO_ECONOMIC
            scope = EventScope.BROAD_MARKET
            affected_broad_market = True
            importance_tier = "MEDIUM"
            confidence = 0.85
            rationale_parts.append("Macroeconomic balance of payments or inflation release altering system liquidity expectations.")

        # Issuer Specific
        else:
            category = EventCategory.ISSUER_DISCLOSURE
            scope = EventScope.ISSUER
            confidence = 0.90
            
            if any(w in text for w in ["bonus share", "dividend", "cash dividend"]):
                importance_tier = "MEDIUM"
                rationale_parts.append("Corporate payout disclosure altering yield and ex-date adjustment.")
            elif any(w in text for w in ["right share", "rights issue"]):
                importance_tier = "MEDIUM"
                rationale_parts.append("Capital dilution and equity call notice.")
            elif any(w in text for w in ["quarterly report", "financial report", "q1", "q2", "q3", "q4"]):
                importance_tier = "LOW"
                rationale_parts.append("Periodic corporate earnings release.")
            else:
                importance_tier = "LOW"
                rationale_parts.append("Routine issuer announcement.")

        # 2. Extract specific symbols mentioned
        detected_symbols = set()
        words = re.findall(r'[A-Z]{2,10}', f"{headline} {body_text}")
        for word in words:
            for sector, syms in SECTOR_SYMBOLS.items():
                if word in syms:
                    detected_symbols.add(word)
                    if sector not in affected_sectors and scope != EventScope.BROAD_MARKET:
                        affected_sectors.append(sector)

        affected_symbols = sorted(list(detected_symbols))
        if affected_symbols and not affected_broad_market and len(affected_sectors) <= 1:
            scope = EventScope.ISSUER
            rationale_parts.append(f"Direct ticker match to {', '.join(affected_symbols)}.")

        mapping_rationale = " ".join(rationale_parts) if rationale_parts else "Categorized via rule engine keywords."

        return (
            category,
            scope,
            confidence,
            importance_tier,
            self.VERSION,
            affected_broad_market,
            affected_sectors,
            affected_symbols,
            mapping_rationale
        )
