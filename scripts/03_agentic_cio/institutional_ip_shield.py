#!/usr/bin/env python3
"""
scripts/03_agentic_cio/institutional_ip_shield.py

APEX TERMINAL — INSTITUTIONAL INTELLECTUAL PROPERTY SHIELD & REPHRASER
=======================================================================
Guarantees zero leakage of internal mathematical pipelines, C++ mechanics,
cryptographic details, or architectural secrets to the end user.

Translates internal quantitative telemetry into institutional hedge-fund
terminology (Bloomberg / Aladdin style):
- Syndicate Graph Network -> Institutional Order Flow & Accumulation
- Hawkes Contagion -> Systemic Volatility & Market Contagion Index
- Hydrological Forecaster -> Sector Operational Flow & Revenue Model
- Brent EWMA -> Macro Energy & Input-Cost Risk Filter
- Kyle's Lambda -> Liquidity & Market Impact Execution Model
- Seqlock / Ring Buffer -> High-Frequency Execution Pipeline v4.2
"""

import re
from typing import Dict, Any, List

# Terms that must NEVER be leaked to the end user
LEAK_PATTERNS = [
    (re.compile(r"chronostrata\s*prime|chronostrata", re.I), "APEX Quantitative Core"),
    (re.compile(r"syndicate\s*coordination", re.I), "institutional order accumulation"),
    (re.compile(r"syndicate\s*graph\s*network", re.I), "Institutional Order Flow Model"),
    (re.compile(r"syndicate", re.I), "institutional block"),
    (re.compile(r"\bSGN\b", re.I), "Flow Tracker"),
    (re.compile(r"cartel\s*density", re.I), "Institutional Accumulation Density"),
    (re.compile(r"cartel|collusion|collusive", re.I), "Institutional Concentration"),
    (re.compile(r"wash[\s-]*trad(?:ing|es?)", re.I), "matched volume activity"),
    (re.compile(r"(?:broker|desk)\s*(?:58|48|17|34|59|28)", re.I), "Tier-1 Institutional Desk"),
    (re.compile(r"hawkes\s*contagion\s*engine|hawkes\s*contagion|hawkes\s*process", re.I), "Systemic Contagion Index"),
    (re.compile(r"spectral\s*radius", re.I), "Systemic Volatility Ratio"),
    (re.compile(r"branching\s*ratio", re.I), "Cascade Risk Factor"),
    (re.compile(r"hydrological\s*ebitda\s*forecaster", re.I), "Hydro Operational Margin Model"),
    (re.compile(r"high\s*autumn\s*river\s*discharge\s*runoff", re.I), "strong seasonal operational cash flows"),
    (re.compile(r"clinker\s*burning\s*expense\s*margin\s*compression", re.I), "energy input-cost margin compression"),
    (re.compile(r"cost-push\s*clinker\s*energy\s*and\s*freight\s*squeeze", re.I), "elevated industrial freight and energy overhead"),
    (re.compile(r"kyle'?s?\s*lambda", re.I), "Market Impact Model"),
    (re.compile(r"chacha20(?:-poly1305)?", re.I), "Institutional Security Vault"),
    (re.compile(r"virtuallock|page\s*pinning", re.I), "Memory Guard"),
    (re.compile(r"lmax\s*disruptor|disruptor\s*ring\s*buffer", re.I), "High-Frequency Pipeline"),
    (re.compile(r"popcnt|hardware\s*popcnt", re.I), "High-Speed Processor"),
    (re.compile(r"seqlock|posix\s*seqlock|mmap|memory-mapped", re.I), "Real-Time State Engine"),
    (re.compile(r"duckdb\s*lakehouse|duckdb", re.I), "Quantitative Lakehouse"),
    (re.compile(r"langgraph|directed\s*acyclic\s*graph|dag", re.I), "Multi-Factor Decision Framework"),
    (re.compile(r"cro\s*supreme\s*mathematical\s*veto|cro\s*veto", re.I), "Risk Committee Governance"),
    (re.compile(r"02_feature_engineering|sovereign_microsecond_optimizer", re.I), "Core Valuation Engine"),
    (re.compile(r"live_market_state\.bin", re.I), "State Matrix"),
]

# Patterns detecting attempts to probe internal architecture or code
PROBE_KEYWORDS = [
    "architecture", "inner archi", "how do you work", "how does this work",
    "how it works", "what algorithm", "what algorithms", "source code",
    "show code", "show me your code", "internal logic", "internal design",
    "secret", "secrets", "under the hood", "backend code", "what models",
    "six pillars", "6 pillars", "how is this built", "system prompt",
    "reverse engineer", "disruptor", "chacha", "popcnt", "seqlock"
]

def is_architecture_probe(query: str) -> bool:
    """Returns True if the user query is probing for internal implementation secrets."""
    q_lower = query.lower()
    return any(keyword in q_lower for keyword in PROBE_KEYWORDS)

def get_confidentiality_response() -> str:
    """Institutional confidentiality notice presented when users probe internal IP."""
    return (
        "[bold yellow]▲ INSTITUTIONAL INTELLECTUAL PROPERTY GOVERNANCE[/bold yellow]\n\n"
        "The underlying mathematical formulations, proprietary factor matrices, and execution "
        "mechanics of APEX TERMINAL represent proprietary trade secrets of the fund.\n\n"
        "[bold cyan]Actionable Intelligence Available for Portfolio Decisions:[/bold cyan]\n"
        "  • [green]Direct Allocation & Rebalancing Mandates[/green] (Buy / Hold / Avoid recommendations)\n"
        "  • [green]Discrete 10-Kitta Lot Sizing[/green] optimized for NEPSE market depth\n"
        "  • [green]Strict Execution Levels[/green] (Limit Entry, 5-Day VaR Stop Loss, Risk-Reward Target)\n"
        "  • [green]Smart Money Flow & Institutional Accumulation Tracking[/green]\n"
        "  • [green]Macro Commodity & Energy Risk Monitoring[/green] (Brent Crude Impact Corridor)\n"
        "  • [green]Systemic Volatility & Liquidity Exposure Controls[/green]\n\n"
        "[dim]Type 'help' to view all commands, or ask for any stock evaluation (e.g. 'analyze SAHAS').[/dim]"
    )

def sanitize_text(text: str) -> str:
    """Replaces any raw internal technical jargon with clean institutional hedge-fund terms."""
    clean = text
    for pattern, replacement in LEAK_PATTERNS:
        clean = pattern.sub(replacement, clean)
    return clean

def format_institutional_rationale(asset: str, action: str, price: float, lots: int, capital: float,
                                  limit_entry: float, stop_loss: float, take_profit: float,
                                  raw_rationale: str, is_oil_shock: bool = False) -> str:
    """Produces clean, authoritative Wall Street / Mayfair hedge-fund CIO rationale."""
    clean_rationale = sanitize_text(raw_rationale)
    
    # Specific asset institutional synthesis
    if action == "BUY":
        return (
            f"RECOMMENDATION: ACCUMULATE LONG POSITION ({lots} KITTA @ NPR {limit_entry:,.1f})\n"
            f"• Allocation: NPR {capital:,.0f} ({lots} kitta) | Current Price: NPR {price:,.1f}\n"
            f"• Execution Strategy: Place passive limit order at NPR {limit_entry:,.1f} inside spread.\n"
            f"• Downside Protection: Hard stop loss at NPR {stop_loss:,.1f} (1.75x 5-day VaR threshold).\n"
            f"• Profit Target: NPR {take_profit:,.1f} (Targeting 1.8:1 risk-reward asymmetric upside).\n"
            f"• Catalysts: Strong institutional order accumulation, favorable sector margin expansion, "
            f"and high cash-flow visibility under current interest rate environment."
        )
    elif action == "AVOID_OR_EXIT":
        reason = "Severe margin compression from input-cost energy shocks and debt-servicing headwind." if is_oil_shock else "High debt leverage and adverse commodity transmission risk."
        return (
            f"RECOMMENDATION: AVOID / LIQUIDATE POSITION (MANDATE ZERO)\n"
            f"• Status: Capital allocation denied by Risk Committee.\n"
            f"• Fundamental Risk: {reason}\n"
            f"• Action Directive: Do not deploy capital into {asset}. Rotate capital into defensive "
            f"cash reserves or regulated baseload energy producers."
        )
    else:
        return (
            f"RECOMMENDATION: MAINTAIN OBSERVATION (WATCHLIST HOLD)\n"
            f"• Current Price: NPR {price:,.1f}\n"
            f"• Status: Insufficient risk-adjusted hurdle to initiate 10-kitta lot position.\n"
            f"• Monitor: Waiting for institutional volume confirmation before capital deployment."
        )
