#!/usr/bin/env python3
"""
scripts/03_agentic_cio/chat_cio.py

CHRONOSTRATA PRIME — INTERACTIVE HEDGE-FUND MANAGER CONVERSATIONAL REPL
========================================================================
Interactive terminal interface allowing direct natural-language communication
with your Sovereign Chief Investment Officer & Institutional Multi-Agent Committee.
"""

import os
import sys
import time
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import importlib.util
cio_path = BASE_DIR / "scripts" / "03_agentic_cio" / "sovereign_agentic_cio.py"
spec = importlib.util.spec_from_file_location("cio_mod", cio_path)
cio_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cio_mod)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

console = Console()

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

class ConversationalHedgeFundManager:
    def __init__(self):
        self.committee = cio_mod.SovereignInvestmentCommittee()
        self.reader = self.committee.seqlock_reader
        self.lakehouse = self.committee.lakehouse_reader
        self.known_tickers = [
            "SAHAS", "CHCL", "NGPL", "NABIL", "CIT", "SHIVM", "SARBTM", "API",
            "LBBL", "GBIME", "NICA", "HIDCL", "UPPER", "HATHY", "HRL", "NRIC"
        ]

    def get_live_risk_posture(self) -> str:
        """Returns concise summary of live macro, memory, and liquidity health."""
        state = self.reader.get_live_state()
        oil_ewma = state.get("macro_oil_ewma", 78.50)
        oil_z = (oil_ewma - 78.50) / 8.20
        oil_status = "CRITICAL SHOCK (+2.0 sigma TRIGGER ACTIVE)" if oil_z > 2.0 else "NORMAL EQUILIBRIUM"
        
        posture = (
            f"**Portfolio Risk & Execution Posture:**\n"
            f"- **T+2 Settled Deployable Cash:** NPR {state.get('t2_settled_cash', 450000.0):,.2f}\n"
            f"- **Hawkes Contagion Spectral Radius:** {state.get('spectral_radius', 0.82):.3f} "
            f"({'CRITICAL CONTAGION' if state.get('spectral_radius', 0.82) > 0.95 else 'STABLE CASCADE BOUND'})\n"
            f"- **Brent Crude 60-Day EWMA:** ${oil_ewma:.2f}/bbl (Z-Score: {oil_z:+.2f} sigma — {oil_status})\n"
            f"- **Sovereign Model Vault:** ChaCha20-Poly1305 Sealed RAM (Zero disk leak)\n"
            f"- **Microsecond IPC:** Lock-Free POSIX Seqlock mmap (Seq #{state.get('sequence', 0)})"
        )
        return posture

    def answer_query(self, query: str) -> str:
        """Processes plain-English user query and delivers CIO recommendations."""
        q_upper = query.upper()

        # 1. Quick Commands
        if q_upper in ["REBALANCE", "PORTFOLIO", "/REBALANCE", "REBALANCE PORTFOLIO"]:
            blotter = self.committee.run_portfolio_rebalance()
            table = Table(title="🏛️ Institutional Rebalancing Blotter", header_style="bold cyan")
            table.add_column("Ticker", style="bold")
            table.add_column("Action", style="bold")
            table.add_column("Price (NPR)")
            table.add_column("Lots (Kitta)")
            table.add_column("Capital (NPR)")
            table.add_column("Limit Entry")
            table.add_column("CRO Verdict")

            for item in blotter:
                act_color = "green" if item["action"] == "BUY" else "red"
                table.add_row(
                    item["target_asset"],
                    f"[{act_color}]{item['action']}[/{act_color}]",
                    f"{item['current_price']:.1f}",
                    str(item["approved_lots_kitta"]),
                    f"{item['committed_capital_npr']:,.0f}",
                    f"{item['limit_entry_npr']:.1f}",
                    item["cro_verdict"]
                )
            console.print(table)
            return "Rebalancing recommendations generated and persisted to `static_data/agent_cio_recommendations.json`."

        if any(w in q_upper for w in ["RISK", "POSTURE", "HEALTH", "CASH", "BALANCE", "STATUS"]):
            return self.get_live_risk_posture()

        if "OIL" in q_upper or "BRENT" in q_upper or "CRUDE" in q_upper:
            state = self.reader.get_live_state()
            oil_ewma = state.get("macro_oil_ewma", 78.50)
            oil_z = (oil_ewma - 78.50) / 8.20
            regime = "OIL_SHOCK_RESTRICTIVE" if oil_z > 2.0 else ("EXPANSIONARY" if oil_z < -0.5 else "EQUILIBRIUM")
            return (
                f"**Brent Crude Macro Risk Assessment:**\n"
                f"- **Current EWMA-60:** ${oil_ewma:.2f}/bbl\n"
                f"- **Z-Score Deviation:** {oil_z:+.2f} sigma\n"
                f"- **Macro Regime:** `{regime}`\n"
                f"- **Policy Mandate:** When Z > +2.0 sigma, manufacturing assets (SHIVM, SARBTM, GCIL) are automatically dumped to 0% "
                f"due to clinker energy and freight squeeze. Capital is rotated +50% into baseload Run-of-River hydro (SAHAS, CHCL) "
                f"and locked into 40% NRB 91-Day Treasury Bills."
            )

        # 2. Extract Specific Tickers
        found_tickers = [t for t in self.known_tickers if re.search(r'\b' + t + r'\b', q_upper)]
        
        if found_tickers:
            responses = []
            for ticker in found_tickers:
                mandate = self.committee.evaluate_asset(ticker)
                metrics = self.lakehouse.get_ticker_metrics(ticker)
                
                resp = (
                    f"### 📊 Institutional Committee Evaluation: **{ticker}**\n\n"
                    f"- **Executive Action:** `{mandate['action']}`\n"
                    f"- **Market Price:** NPR {mandate['current_price']:.2f}\n"
                    f"- **Recommended Limit Entry:** NPR {mandate['limit_entry_npr']:.2f}\n"
                    f"- **Stop Loss (5-Day VaR):** NPR {mandate['stop_loss_npr']:.2f}\n"
                    f"- **Target Take-Profit:** NPR {mandate['take_profit_npr']:.2f} (1.8:1 Reward/Risk)\n"
                    f"- **Approved Position Size:** **{mandate['approved_lots_kitta']} Kitta** ({mandate['approved_lots_kitta']*10:,} shares)\n"
                    f"- **Capital Allocated:** NPR {mandate['committed_capital_npr']:,.2f}\n"
                    f"- **Kyle's Lambda (Market Depth):** {metrics.get('kyles_lambda', 0.00015):.6f}\n"
                    f"- **Chief Risk Officer (CRO) Verdict:** `{mandate['cro_verdict']}`\n\n"
                    f"**Committee Deliberation & Rationale:**\n"
                    f"> {mandate['strategic_rationale']}"
                )
                responses.append(resp)
            return "\n\n---\n\n".join(responses)

        # 3. General Strategic Question Fallback
        return (
            f"I have inspected the live market state and historical lakehouse.\n\n"
            f"{self.get_live_risk_posture()}\n\n"
            f"**To analyze a specific stock, mention its ticker (e.g. 'Analyze SAHAS', 'What about SHIVM?').**\n"
            f"Or type `rebalance` to generate a full multi-asset portfolio allocation blotter."
        )

def run_chat_repl():
    console.print(Panel.fit(
        "[bold cyan]CHRONOSTRATA PRIME — SOVEREIGN AGENTIC CHIEF INVESTMENT OFFICER (CIO)[/bold cyan]\n"
        "[italic white]Personal Institutional Multi-Agent Hedge Fund Manager running locally on your PC[/italic white]\n"
        "[dim]LangGraph Committee • Zero-Copy Seqlock mmap • Kyle's Lambda Depth • Discrete 10-Kitta Sizing[/dim]",
        border_style="cyan"
    ))
    console.print("[yellow]Type your questions in plain English (e.g., 'Should I buy SAHAS?', 'Why avoid SHIVM?', 'Rebalance').[/yellow]")
    console.print("[dim]Type 'exit' or 'quit' to close.[/dim]\n")

    manager = ConversationalHedgeFundManager()

    while True:
        try:
            query = console.input("[bold green]You > [/bold green]").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                console.print("[bold red]Hedge Fund Manager standing down. Session preserved.[/bold red]")
                break

            console.print("\n[dim]🧠 Committee Deliberating (Quant Analyst ➔ Macro Oil ➔ CRO ➔ CIO)...[/dim]\n")
            response = manager.answer_query(query)
            console.print(Panel(Markdown(response), title="[bold cyan]🏛️ Chief Investment Officer[/bold cyan]", border_style="blue"))
            console.print()
        except KeyboardInterrupt:
            console.print("\n[bold red]Session interrupted. Exiting.[/bold red]")
            break
        except Exception as e:
            console.print(f"[bold red]Error processing deliberation:[/bold red] {e}")

if __name__ == "__main__":
    run_chat_repl()
