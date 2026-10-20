@echo off
setlocal enabledelayedexpansion
title APEX WEALTH PMS - ENTERPRISE PORTFOLIO MANAGEMENT SUITE
cd /d "%~dp0"

echo ===============================================================================
echo   APEX WEALTH: NEPSE ENTERPRISE MULTI-ACCOUNT PORTFOLIO MANAGEMENT SUITE
echo   Executive PMS Launchpad + Triskell RAG Grid + Corporater Scorecard + Quant Lab
echo ===============================================================================

:: -----------------------------------------------------------------------------
:: STEP 1: Process Lifecycle & Socket Reclamation (Port 8888)
:: -----------------------------------------------------------------------------
echo [*] Auditing process lifecycle and socket bindings on port 8888...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8888 ^| findstr LISTENING 2^>nul') do (
    echo [!] Reclaiming previous listener on port 8888 [PID: %%a]...
    taskkill /F /T /PID %%a >nul 2>&1
)

:: -----------------------------------------------------------------------------
:: STEP 2: Python Environment Orchestration (Probes for FastAPI + NumPy)
:: -----------------------------------------------------------------------------
set "PYTHONHOME="
set "PYTHONPATH=%~dp0apex_wealth\backend"
set "PY_BIN="

for %%P in (
    "C:\Users\achar\AppData\Local\Programs\Python\Python313\python.exe"
    "C:\Users\achar\AppData\Local\Programs\Python\Python311\python.exe"
    "%~dp0.venv\Scripts\python.exe"
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
:: STEP 3: Ensure 1-Click Desktop Shortcut Exists
:: -----------------------------------------------------------------------------
if not exist "%USERPROFILE%\OneDrive\Desktop\ApexTerminal.lnk" if not exist "%USERPROFILE%\Desktop\ApexTerminal.lnk" (
    echo [*] Registering 1-Click Desktop Icon...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $p = [Environment]::GetFolderPath('Desktop') + '\ApexTerminal.lnk'; $s = $ws.CreateShortcut($p); $s.TargetPath = '%~dp0run_terminal.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Apex Wealth Enterprise PMS Suite'; $s.IconLocation = 'shell32.dll,220'; $s.Save()" >nul 2>&1
)

:: -----------------------------------------------------------------------------
:: STEP 4: Launch Institutional FastAPI + WebSocket PMS Backend (Port 8888)
:: -----------------------------------------------------------------------------
echo [*] Starting Apex Wealth Enterprise PMS Engine on http://127.0.0.1:8888 ...
pushd "%~dp0apex_wealth"
start "ApexWealth_PMS_Backend" /B "!PY_BIN!" backend/main.py
popd

:: -----------------------------------------------------------------------------
:: STEP 5: Socket Readiness Polling Loop
:: -----------------------------------------------------------------------------
echo [*] Waiting for ASGI telemetry socket on port 8888...
set /a TRIES=0
:wait_socket
timeout /t 1 /nobreak >nul
netstat -ano | findstr :8888 | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto socket_ready
set /a TRIES+=1
if !TRIES! lss 15 goto wait_socket

:socket_ready
echo [OK] Enterprise PMS Suite established on http://127.0.0.1:8888.

:: -----------------------------------------------------------------------------
:: STEP 6: Native Desktop App Window Launch (Edge / Chrome App Mode)
:: -----------------------------------------------------------------------------
echo [*] Launching Native Desktop PMS Suite Window (Zero Browser Chrome)...
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8888 --window-size=1920,1080
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8888 --window-size=1920,1080
) else if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=http://127.0.0.1:8888 --window-size=1920,1080
) else (
    start "" http://127.0.0.1:8888
)

echo [OK] Terminal operational. Minimize or close this window when finished.
timeout /t 3 >nul
