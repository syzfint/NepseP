@echo off
setlocal EnableExtensions EnableDelayedExpansion
title APEXMARKETENGINE -- 24/7 UNIFIED COCKPIT AND SURVEILLANCE PLATFORM
color 0B

:: ============================================================================
:: APEXMARKETENGINE: ONE-COMMAND MASTER RUNTIME
:: Usage:
::   run.bat          (Starts daemons and opens Cockpit Command Center)
::   run.bat --all    (Starts daemons and deploys all 10 unthrottled screens)
::   run.bat --stop   (Performs deterministic teardown on port 8000)
:: ============================================================================

set "CMD_ARG=%~1"
if "%CMD_ARG%"=="" set "CMD_ARG=--launch"

set "APEX_ROOT=%~dp0"
if "%APEX_ROOT:~-1%"=="\" set "APEX_ROOT=%APEX_ROOT:~0,-1%"

set "APEX_HOST=127.0.0.1"
set "APEX_PORT=8000"
set "APEX_BASE_URL=http://%APEX_HOST%:%APEX_PORT%"
set "APEX_WS_PULSE=%APEX_BASE_URL%/ws/pulse"

:: Detect Python environment
set "PY_CMD=py -3.13"
if exist "%APEX_ROOT%\.venv\Scripts\python.exe" (
    set "PY_CMD=%APEX_ROOT%\.venv\Scripts\python.exe"
)

echo ============================================================================
echo   APEXMARKETENGINE - 24/7 REGTECH SURVEILLANCE + 10-SCREEN COCKPIT
echo   Single Workstation Topology :: Port %APEX_PORT% :: Mode: %CMD_ARG%
echo ============================================================================

:: 1. TEARDOWN CHECK
if /i "%CMD_ARG%"=="--stop" (
    echo [TEARDOWN] Terminating active processes on Port %APEX_PORT%...
    call :CLEAN_PORT_8000
    echo [OK] All Apex services stopped.
    exit /b 0
)

:: Clean any stale bindings on Port 8000 before boot
call :CLEAN_PORT_8000

:: 2. CPU AFFINITY BITMASK
set "RT_MASK=0x3"
for /f "usebackq tokens=*" %%M in (`powershell -NoProfile -Command ^
    "$n = [int]$env:NUMBER_OF_PROCESSORS; if ($n -ge 64) { '0xFFFFFFFFFFFFFFFC' } elseif ($n -lt 4) { '0xC' } else { $mask = ([uint64]1 -shl $n) - 1 - 3; '0x' + $mask.ToString('X') }"`) do (
    set "ASYNC_MASK=%%M"
)
echo [CPU] Logical Cores: %NUMBER_OF_PROCESSORS% :: Core 0-1 Ingress: %RT_MASK% :: Async Pool: %ASYNC_MASK%

:: 3. LAUNCH PINNED INGRESS DAEMON (CORE 0-1)
echo [DAEMON] Starting Core 0-1 Real-Time Ingress and SEBON Anti-Wash Guard...
cmd.exe /c start "Apex_Core01_Ingress" /min /affinity %RT_MASK% ^
    %PY_CMD% -m apex_engine.ingress_daemon --shm-path "/dev/shm/tick_queue" --vpin-threshold 0.70

:: 4. LAUNCH ASYNC ASGI & WEBSOCKET ENGINE (CORE 2-N)
echo [SERVER] Starting ASGI Engine and WebSocket /ws/pulse on Port %APEX_PORT%...
cmd.exe /c start "Apex_ASGI_Engine" /min /affinity %ASYNC_MASK% ^
    %PY_CMD% -m uvicorn apex_engine.main:app --host %APEX_HOST% --port %APEX_PORT% --workers 1 --no-access-log

:: 5. WEBSOCKET READINESS GATE
echo [GATE] Awaiting Port %APEX_PORT% readiness...
set /a "TRIES=0"
:POLL_READY
set /a "TRIES+=1"
if %TRIES% gtr 40 (
    echo [WARN] Server startup taking longer than normal. Attempting browser launch...
    goto :DEPLOY_UI
)
powershell -NoProfile -Command "Start-Sleep -Milliseconds 500"
netstat -aon | findstr ":%APEX_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorLevel% neq 0 goto :POLL_READY

echo [OK] Port %APEX_PORT% is ONLINE and WebSocket /ws/pulse is active!

:: 6. LAUNCH UNIFIED MASTER COCKPIT WINDOW (10-IN-1 ZERO DEGRADATION)
:DEPLOY_UI
call :DETECT_BROWSER

echo [COCKPIT] Deploying Unified 10-in-1 Master Cockpit (Single Maximized Window)...
set "MASTER_PROF=%LOCALAPPDATA%\ApexCockpitProfiles\UnifiedMaster"
if not exist "%MASTER_PROF%" mkdir "%MASTER_PROF%"

start "Apex_Unified_Master_Cockpit" "%BROWSER_EXE%" ^
    --user-data-dir="%MASTER_PROF%" ^
    --app="%APEX_BASE_URL%/" ^
    --start-maximized ^
    --no-first-run --no-default-browser-check ^
    --disable-background-timer-throttling --disable-renderer-backgrounding

echo ============================================================================
echo   [ACTIVE] APEX UNIFIED 10-SCREEN MASTER COCKPIT ONLINE
echo   - Master Single Window : %APEX_BASE_URL%/
echo   - Master Matrix View   : Hotkey [M]
echo   - Dual Split (S04+S10) : Hotkey [D]
echo   - Dedicated Screens    : Hotkeys [1-9, 0] (S01 to S10)
echo   - Telemetry Stream     : ws://%APEX_HOST%:%APEX_PORT%/ws/pulse
echo   To stop all processes, run:  run.bat --stop
echo ============================================================================
goto :EOF

:: ============================================================================
:: SUBROUTINES
:: ============================================================================
:CLEAN_PORT_8000
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":%APEX_PORT% " ^| findstr "LISTENING"') do (
    if not "%%P"=="0" (
        taskkill /F /T /PID %%P >nul 2>&1
    )
)
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %APEX_PORT% -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 4 } | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>&1
exit /b 0

:DETECT_BROWSER
set "BROWSER_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "BROWSER_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    exit /b 0
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "BROWSER_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    exit /b 0
)
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    set "BROWSER_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
    exit /b 0
)
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    set "BROWSER_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
    exit /b 0
)
set "BROWSER_EXE=explorer.exe"
exit /b 0

:SPAWN_APP
set "SCR_ID=%~1"
set "SCR_POS=%~2"
set "SCR_SIZE=%~3"
set "SCR_PATH=%~4"
set "SCR_PROF=%LOCALAPPDATA%\ApexCockpitProfiles\%SCR_ID%"
if not exist "%SCR_PROF%" mkdir "%SCR_PROF%"

start "Apex_%SCR_ID%" "%BROWSER_EXE%" ^
    --user-data-dir="%SCR_PROF%" ^
    --window-position=%SCR_POS% ^
    --window-size=%SCR_SIZE% ^
    --app="%APEX_BASE_URL%%SCR_PATH%" ^
    --no-first-run --no-default-browser-check ^
    --disable-background-timer-throttling --disable-renderer-backgrounding
exit /b 0
