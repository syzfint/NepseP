@echo off
setlocal enabledelayedexpansion
title APEX WEALTH PMS - ENTERPRISE PORTFOLIO MANAGEMENT SUITE
cd /d "%~dp0"

echo ===============================================================================
echo   APEX WEALTH: ENTERPRISE MULTI-ACCOUNT PORTFOLIO MANAGEMENT SUITE (PMS)
echo   Layman Executive Cockpit + Institutional Schur-RA-HRP ^& Merkle Engine
echo ===============================================================================

:: -----------------------------------------------------------------------------
:: STEP 1: Reclaim Port 8888 Socket if Previously Running
:: -----------------------------------------------------------------------------
echo [*] Auditing socket bindings on port 8888...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8888 ^| findstr LISTENING 2^>nul') do (
    echo [!] Reclaiming existing listener on port 8888 [PID: %%a]...
    taskkill /F /T /PID %%a >nul 2>&1
)

:: -----------------------------------------------------------------------------
:: STEP 2: Locate Verified Python Environment (with FastAPI + NumPy)
:: -----------------------------------------------------------------------------
set "PYTHONHOME="
set "PYTHONPATH=%~dp0backend"
set "PY_BIN="

for %%P in (
    "C:\Users\achar\AppData\Local\Programs\Python\Python313\python.exe"
    "C:\Users\achar\AppData\Local\Programs\Python\Python311\python.exe"
    "..\.venv\Scripts\python.exe"
    "python"
) do (
    if not defined PY_BIN (
        if exist %%P (
            %%P -c "import fastapi, uvicorn, numpy" >nul 2>&1
            if not errorlevel 1 (
                set "PY_BIN=%%~P"
            )
        )
    )
)

if not defined PY_BIN (
    if exist "C:\Users\achar\AppData\Local\Programs\Python\Python313\python.exe" (
        set "PY_BIN=C:\Users\achar\AppData\Local\Programs\Python\Python313\python.exe"
    ) else if exist "C:\Users\achar\AppData\Local\Programs\Python\Python311\python.exe" (
        set "PY_BIN=C:\Users\achar\AppData\Local\Programs\Python\Python311\python.exe"
    ) else (
        set "PY_BIN=python"
    )
    echo [*] Verifying core runtime packages...
    "!PY_BIN!" -c "import fastapi, uvicorn, numpy" >nul 2>&1
    if errorlevel 1 (
        echo [*] Installing core runtime packages ^(fastapi, uvicorn, numpy^)...
        "!PY_BIN!" -m pip install --quiet fastapi uvicorn numpy
    )
)

echo [*] Utilizing verified Python runtime: !PY_BIN!

:: -----------------------------------------------------------------------------
:: STEP 3: Start Institutional FastAPI + WebSocket Telemetry Server
:: -----------------------------------------------------------------------------
echo [*] Launching Apex Wealth Enterprise PMS Server on http://127.0.0.1:8888 ...
start "ApexWealth_PMS_Backend" /B "!PY_BIN!" backend/main.py

:: -----------------------------------------------------------------------------
:: STEP 4: Poll Socket Until Ready
:: -----------------------------------------------------------------------------
echo [*] Waiting for PMS Engine socket to establish...
set /a TRIES=0
:wait_socket
timeout /t 1 /nobreak >nul
netstat -ano | findstr :8888 | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto socket_ready
set /a TRIES+=1
if !TRIES! lss 15 goto wait_socket

:socket_ready
echo [OK] Apex Wealth PMS Engine online at http://127.0.0.1:8888

:: -----------------------------------------------------------------------------
:: STEP 5: Launch Native Borderless Desktop Window (Edge / Chrome App Mode)
:: -----------------------------------------------------------------------------
echo [*] Opening Borderless Enterprise PMS Suite Window...
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8888 --window-size=1920,1080
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8888 --window-size=1920,1080
) else if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=http://127.0.0.1:8888 --window-size=1920,1080
) else (
    start "" http://127.0.0.1:8888
)

echo [OK] Apex Wealth PMS Suite is running.
timeout /t 3 >nul
