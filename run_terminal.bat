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

set PY_PATH="C:\Users\achar\AppData\Local\Programs\Python\Python313\python.exe"
if exist %PY_PATH% (
    start "" http://127.0.0.1:8000
    %PY_PATH% scripts/08_dashboard_ui/multi_workspace_terminal.py
) else (
    start "" http://127.0.0.1:8000
    py -3.13 scripts/08_dashboard_ui/multi_workspace_terminal.py
)
pause
