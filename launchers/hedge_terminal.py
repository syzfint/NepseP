#!/usr/bin/env python3
"""
hedge_terminal.py

APEX TERMINAL — LOCAL CMD HEDGE-FUND WORKSTATION ENTRYPOINT
============================================================
Run directly in Windows Command Prompt, PowerShell, or Terminal:
    python hedge_terminal.py

Features:
- Complete Hedge Fund Manager running locally on your workstation
- What stocks to buy or avoid
- When to enter, exit, stop loss, and take profit
- Discrete 10-kitta lot sizing optimized for your capital
- Real-time alerts, risk monitoring, and macro energy surveillance
- Zero leakage of proprietary internal architecture or secrets
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import importlib.util

term_path = BASE_DIR / "scripts" / "03_agentic_cio" / "hedge_fund_terminal.py"
spec = importlib.util.spec_from_file_location("term_mod", term_path)
term_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(term_mod)

if __name__ == "__main__":
    app = term_mod.InstitutionalHedgeTerminal()
    app.start()
