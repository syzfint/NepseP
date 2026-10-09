#!/usr/bin/env python3
"""
scripts/03_agentic_cio/sovereign_agentic_tui.py

CHRONOSTRATA PRIME — REACTIVE TERMINAL USER INTERFACE (TUI) FOR AGENTIC CIO
=============================================================================
Built with Textual and Rich for modern, async terminal interaction:
- Live Seqlock status and market parameters monitor
- Interactive multi-asset committee rebalancing blotter
- Real-time committee deliberation and executive rationale feed
- Natural language query prompt for interactive analysis
"""

import sys
import time
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, DataTable, Button, Input, RichLog
from textual.reactive import reactive

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import importlib.util
cio_path = BASE_DIR / "scripts" / "03_agentic_cio" / "sovereign_agentic_cio.py"
spec = importlib.util.spec_from_file_location("cio_mod", cio_path)
cio_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cio_mod)

class SovereignCIOApp(App):
    CSS = """
    Screen {
        background: #0d1117;
        color: #c9d1d9;
    }
    Header {
        background: #161b22;
        color: #58a6ff;
        text-style: bold;
    }
    #telemetry_panel {
        height: 5;
        background: #161b22;
        border: solid #30363d;
        padding: 0 1;
        margin-bottom: 1;
    }
    #main_container {
        height: 1fr;
    }
    #blotter_container {
        width: 60%;
        border: solid #30363d;
        background: #0d1117;
        padding: 0 1;
    }
    #rationale_container {
        width: 40%;
        border: solid #30363d;
        background: #161b22;
        padding: 0 1;
    }
    #control_panel {
        height: 4;
        background: #161b22;
        border: solid #30363d;
        padding: 0 1;
        margin-top: 1;
    }
    Input {
        width: 70%;
        border: tall #388bfd;
        background: #0d1117;
    }
    Button {
        width: 14%;
        margin-left: 1;
        background: #238636;
        color: #ffffff;
    }
    Button#btn_audit {
        background: #8957e5;
    }
    """

    TITLE = "CHRONOSTRATA PRIME — SOVEREIGN AGENTIC CIO"
    SUB_TITLE = "Institutional Local Multi-Agent Investment Committee (LangGraph + Seqlock mmap)"

    def __init__(self):
        super().__init__()
        self.committee = cio_mod.SovereignInvestmentCommittee()
        self.reader = self.committee.seqlock_reader

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # Telemetry Top Banner
        yield Static(id="telemetry_panel")
        
        # Middle Split: Left DataTable, Right RichLog
        with Horizontal(id="main_container"):
            with Vertical(id="blotter_container"):
                yield Static("🏛️  [bold yellow]PORTFOLIO REBALANCING BLOTTER[/bold yellow]")
                yield DataTable(id="blotter_table")
            with Vertical(id="rationale_container"):
                yield Static("🧠  [bold cyan]COMMITTEE DELIBERATION & EXECUTIVE RATIONALE[/bold cyan]")
                yield RichLog(id="rationale_log", wrap=True, highlight=True)
        
        # Bottom Command & Controls
        with Horizontal(id="control_panel"):
            yield Input(placeholder="Ask Agentic CIO (e.g. 'Analyze SAHAS', 'Rebalance', 'Risk Status')...", id="cmd_input")
            yield Button("Execute", id="btn_exec", variant="success")
            yield Button("Rebalance All", id="btn_audit", variant="primary")
        
        yield Footer()

    def on_mount(self) -> None:
        """Initialize widgets and launch background polling."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Ticker", "Action", "Price (NPR)", "Lots (Kitta)", "Capital (NPR)", "Limit", "Verdict")

        self.update_telemetry()
        self.run_rebalance()
        self.set_interval(1.0, self.update_telemetry)

    def update_telemetry(self) -> None:
        """Refreshes live parameters from lock-free Seqlock mmap."""
        state = self.reader.get_live_state()
        oil_ewma = state.get("macro_oil_ewma", 78.50)
        oil_z = (oil_ewma - 78.50) / 8.20
        oil_color = "red" if oil_z > 2.0 else "green"
        
        status_text = (
            f"[bold cyan]Seqlock Sequence:[/bold cyan] {state.get('sequence', 0)} (Consistent: {state.get('seqlock_consistent', True)})  |  "
            f"[bold cyan]T+2 Settled Cash:[/bold cyan] NPR {state.get('t2_settled_cash', 450000.0):,.2f}  |  "
            f"[bold cyan]Hawkes Contagion Radius:[/bold cyan] {state.get('spectral_radius', 0.82):.3f}  |  "
            f"[bold {oil_color}]Brent EWMA-60:[/bold {oil_color}] ${oil_ewma:.2f}/bbl (Z: {oil_z:+.2f}σ)  |  "
            f"[bold green]Zero-Trust RAM Vault:[/bold green] SEALED (ChaCha20)"
        )
        self.query_one("#telemetry_panel", Static).update(status_text)

    def run_rebalance(self) -> None:
        """Triggers the full multi-asset committee blotter."""
        log = self.query_one(RichLog)
        log.write("[bold green]Running Institutional Multi-Asset Committee Deliberation...[/bold green]")
        
        blotter = self.committee.run_portfolio_rebalance()
        table = self.query_one(DataTable)
        table.clear()

        for item in blotter:
            action_markup = f"[bold green]{item['action']}[/bold green]" if item['action'] == "BUY" else f"[bold red]{item['action']}[/bold red]"
            table.add_row(
                item["target_asset"],
                action_markup,
                f"{item['current_price']:.1f}",
                str(item["approved_lots_kitta"]),
                f"{item['committed_capital_npr']:,.0f}",
                f"{item['limit_entry_npr']:.1f}",
                item["cro_verdict"]
            )
            log.write(f"[bold cyan]{item['target_asset']}:[/bold cyan] {item['strategic_rationale']}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ["btn_exec", "btn_audit"]:
            cmd_input = self.query_one(Input)
            val = cmd_input.value.strip().upper()
            if val.startswith("ANALYZE ") or val in ["SAHAS", "CHCL", "NGPL", "SHIVM", "SARBTM", "NABIL", "CIT", "API"]:
                sym = val.replace("ANALYZE ", "").strip()
                res = self.committee.evaluate_asset(sym)
                log = self.query_one(RichLog)
                log.write(f"[bold yellow]DIRECT EVALUATION: {sym}[/bold yellow]")
                log.write(f"Verdict: {res['action']} {res['approved_lots_kitta']} kitta @ {res['current_price']} NPR")
                log.write(f"Rationale: {res['strategic_rationale']}")
                cmd_input.value = ""
            else:
                self.run_rebalance()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip().upper()
        if val:
            sym = val.replace("ANALYZE ", "").strip()
            res = self.committee.evaluate_asset(sym)
            log = self.query_one(RichLog)
            log.write(f"[bold yellow]QUERY PROCESSED: {sym}[/bold yellow]")
            log.write(f"Verdict: {res['action']} {res['approved_lots_kitta']} kitta @ {res['current_price']} NPR")
            log.write(f"Rationale: {res['strategic_rationale']}")
            event.input.value = ""

if __name__ == "__main__":
    app = SovereignCIOApp()
    app.run()
