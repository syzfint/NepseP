#!/usr/bin/env python3
"""
launch_prism_station.py

CHRONOSTRATA PRIME — LAUNCHER FOR PRISM PRO REACT STATION
===========================================================
Single-click launcher that boots the FastAPI & WebSocket backend,
serves the compiled React/Tailwind frontend, and opens your browser.
"""

import sys
import time
import webbrowser
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import uvicorn
import importlib.util

api_path = BASE_DIR / "scripts" / "08_dashboard_ui" / "api_server.py"
spec = importlib.util.spec_from_file_location("api_mod", api_path)
api_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_mod)

def open_browser():
    time.sleep(1.2)
    url = "http://127.0.0.1:8000"
    print(f"\n==========================================================================")
    print(f"  ⚡ CHRONOSTRATA PRIME │ PRISM PRO STATION READY AT: {url}")
    print(f"==========================================================================\n")
    webbrowser.open(url)

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(api_mod.app, host="127.0.0.1", port=8000, log_level="info")
