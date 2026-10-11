@echo off
title NEPSE PULSE TERMINAL - WORKSPACE LAUNCHER
cd /d "%~dp0"
echo ======================================================================
echo   NEPSE PULSE TERMINAL - MULTI-WORKSPACE QUANTITATIVE ENGINE
echo ======================================================================
echo   Starting server at http://127.0.0.1:8000 ...
echo   [0] MENU / LAUNCH PAD
echo   [1] TRADING DESK
echo   [2] ALPHA DASHBOARD
echo   [3] RISK MONITOR
echo   [4] 20D FORECAST
echo ======================================================================

start "" http://127.0.0.1:8000
python scripts/08_dashboard_ui/multi_workspace_terminal.py
pause
