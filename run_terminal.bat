@echo off
setlocal enabledelayedexpansion
title APEXMARKETENGINE - INSTITUTIONAL DESKTOP TERMINAL
cd /d "%~dp0"

echo ===============================================================================
echo   APEXMARKETENGINE: NEPSE INSTITUTIONAL QUANTITATIVE TERMINAL
echo   Zero-Config Windows Orchestration & Desktop Productization Suite
echo ===============================================================================

:: -----------------------------------------------------------------------------
:: STEP 1: Process Tree Lifecycle Management & Socket Binding Reclamation
:: -----------------------------------------------------------------------------
echo [*] Auditing process lifecycle and socket bindings...
if exist ".apex_server.pid" (
    set /p OLD_PID=<.apex_server.pid
    if defined OLD_PID (
        echo [*] Terminating previous server process tree [PID: !OLD_PID!] via Win32 Job reclamation...
        taskkill /F /T /PID !OLD_PID! >nul 2>&1
    )
    del /f /q ".apex_server.pid" >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    echo [!] Found lingering listener on port 8000 [PID: %%a]. Reclaiming socket...
    taskkill /F /T /PID %%a >nul 2>&1
)

:: -----------------------------------------------------------------------------
:: STEP 2: Python Environment & Virtualenv Orchestration
:: -----------------------------------------------------------------------------
set "PY_BIN="
if exist ".venv\Scripts\python.exe" (
    set "PY_BIN=.venv\Scripts\python.exe"
    echo [*] Utilizing local virtual environment (.venv)
) else if exist "C:\Users\achar\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PY_BIN=C:\Users\achar\AppData\Local\Programs\Python\Python313\python.exe"
    echo [*] Utilizing verified institutional Python 3.13 binary
) else (
    set "PY_BIN=py -3.13"
)

:: -----------------------------------------------------------------------------
:: STEP 3: Ensure Desktop Shortcut Exists (1-Click Desktop Icon)
:: -----------------------------------------------------------------------------
if not exist "%USERPROFILE%\OneDrive\Desktop\ApexTerminal.lnk" if not exist "%USERPROFILE%\Desktop\ApexTerminal.lnk" (
    echo [*] Registering 1-Click Desktop Icon...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $p = [Environment]::GetFolderPath('Desktop') + '\ApexTerminal.lnk'; $s = $ws.CreateShortcut($p); $s.TargetPath = '%~dp0run_terminal.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'NEPSE Apex Institutional Terminal'; $s.IconLocation = 'shell32.dll,220'; $s.Save()" >nul 2>&1
)

:: -----------------------------------------------------------------------------
:: STEP 4: Asynchronous Uvicorn Server Launch
:: -----------------------------------------------------------------------------
echo [*] Initializing multi-workspace ASGI terminal server on http://127.0.0.1:8000 ...
start "ApexTerminal_Backend" /B %PY_BIN% scripts/08_dashboard_ui/multi_workspace_terminal.py

:: -----------------------------------------------------------------------------
:: STEP 5: Socket Polling Wait Loop
:: -----------------------------------------------------------------------------
echo [*] Waiting for ASGI socket to establish...
:wait_socket
timeout /t 1 /nobreak >nul
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if errorlevel 1 goto wait_socket

echo [OK] Backend established on http://127.0.0.1:8000.

:: -----------------------------------------------------------------------------
:: STEP 6: Native Desktop App Window Launch (Edge / Chrome App Mode)
:: -----------------------------------------------------------------------------
echo [*] Launching Native Desktop Terminal Window (Zero Browser Chrome)...
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8000 --window-size=1920,1080
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8000 --window-size=1920,1080
) else if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=http://127.0.0.1:8000 --window-size=1920,1080
) else (
    start "" http://127.0.0.1:8000
)

echo [OK] Terminal operational. Minimize or close this window when finished.
timeout /t 4 >nul
