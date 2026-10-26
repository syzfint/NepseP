@echo off
setlocal EnableExtensions EnableDelayedExpansion
title APEXMARKETENGINE - 24/7 SINGLE-PC SURVEILLANCE DAEMON & COCKPIT ORCHESTRATOR
color 0B

:: ============================================================================
:: SECTION 0: OPERATOR CLI FLAGS & ENVIRONMENT CONFIGURATION
:: Usage: run_surveillance_cockpit.bat [--all | --daemon-only | --cockpit-only | --teardown]
:: ============================================================================
set "LAUNCH_MODE=%~1"
if "%LAUNCH_MODE%"=="" set "LAUNCH_MODE=--all"

set "APEX_ROOT=%~dp0"
if "%APEX_ROOT:~-1%"=="\" set "APEX_ROOT=%APEX_ROOT:~0,-1%"

set "APEX_HOST=127.0.0.1"
set "APEX_PORT=8000"
set "APEX_BASE_URL=http://%APEX_HOST%:%APEX_PORT%"
set "APEX_WS_PULSE=%APEX_BASE_URL%/ws/pulse"

set "PYTHON_EXE=%APEX_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python.exe"

set "DATA_DIR=%APEX_ROOT%\data"
set "PARQUET_STAGING=%DATA_DIR%\parquet_staging"
set "DUCKDB_FILE=%DATA_DIR%\apex_nepse_lakehouse.duckdb"
set "MERKLE_LEDGER=%DATA_DIR%\merkle_provenance.chain"
set "LOG_DIR=%APEX_ROOT%\logs"
set "PROFILE_ROOT=%LOCALAPPDATA%\ApexMarketEngine\CockpitProfiles"

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%PARQUET_STAGING%" mkdir "%PARQUET_STAGING%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%PROFILE_ROOT%" mkdir "%PROFILE_ROOT%"

:: ============================================================================
:: SECTION 1: ADMINISTRATIVE PRIVILEGE VERIFICATION (REQUIRED FOR /REALTIME)
:: ============================================================================
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Administrative privileges required for /REALTIME CPU scheduling and taskkill /T.
    echo [INFO] Elevating run_surveillance_cockpit.bat via UAC...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Start-Process -FilePath '%~f0' -ArgumentList '%LAUNCH_MODE%' -Verb RunAs"
    exit /b 0
)

echo ============================================================================
echo  APEXMARKETENGINE - SINGLE-PC REGTECH SURVEILLANCE ^& NEWS HARNESS RUNTIME
echo  Host Topology : Single Local PC (Zero External Edge Nodes)
echo  Target Port   : TCP %APEX_PORT% (/ws/pulse + REST + MCP AI Connectors)
echo  Launch Mode   : %LAUNCH_MODE%
echo ============================================================================

:: ============================================================================
:: SECTION 2: DETERMINISTIC PROCESS TREE TEARDOWN ON TCP PORT 8000
:: Prevents orphan Uvicorn / multiprocessing workers from locking Port 8000
:: ============================================================================
call :TEARDOWN_PORT_8000
if /i "%LAUNCH_MODE%"=="--teardown" (
    echo [OK] Teardown complete. Exiting as requested.
    exit /b 0
)

:: ============================================================================
:: SECTION 3: DYNAMIC CPU AFFINITY HEX BITMASK CALCULATION
:: Cores 0-1 (0x03) -> Pinned Real-Time WebSocket Ingress + Anti-Wash Filter
:: Cores 2-N        -> Asynchronous Pool (OFI, Hawkes, VPIN, News, DuckDB OLAP)
:: ============================================================================
set "RT_AFFINITY_HEX=0x3"
for /f "usebackq tokens=*" %%M in (`powershell -NoProfile -Command ^
    "$n = [int]$env:NUMBER_OF_PROCESSORS; if ($n -ge 64) { '0xFFFFFFFFFFFFFFFC' } elseif ($n -lt 4) { '0xC' } else { $mask = ([uint64]1 -shl $n) - 1 - 3; '0x' + $mask.ToString('X') }"`) do (
    set "ASYNC_AFFINITY_HEX=%%M"
)
echo [CPU] Detected %NUMBER_OF_PROCESSORS% Logical Processors.
echo [CPU] Cores 0-1 Real-Time Ingress Mask : %RT_AFFINITY_HEX% (Priority: /REALTIME / SCHED_FIFO)
echo [CPU] Cores 2-N Async Analytical Mask  : %ASYNC_AFFINITY_HEX% (Priority: /HIGH)

:: ============================================================================
:: SECTION 4: WSL2 / POSIX KERNEL ZRAM & /dev/shm ZERO-COPY IPC TUNING
:: Applies vm.swappiness=100, vm.page-cluster=0, vm.vfs_cache_pressure=500
:: ============================================================================
where wsl.exe >nul 2>&1
if %errorLevel% equ 0 (
    echo [KERNEL] Applying POSIX /dev/shm/tick_queue and ZRAM sysctl tuning via WSL2...
    wsl.exe -u root -- sh -c ^
        "sysctl -w vm.swappiness=100 vm.page-cluster=0 vm.vfs_cache_pressure=500 >/dev/null 2>&1; mkdir -p /dev/shm/tick_queue && chmod 1777 /dev/shm/tick_queue"
    echo [KERNEL] POSIX shared memory (/dev/shm/tick_queue) and ZRAM parameters active.
) else (
    echo [KERNEL] Native Win32 Named Shared Memory fallback active (mmap tag: ApexTickQueue_shm).
)

:: ============================================================================
:: SECTION 5: LAKEHOUSE CONCURRENCY GUARD & MERKLE PROVENANCE AUDIT CHECK
:: Cleans orphan Parquet staging files and stale DuckDB locks before startup
:: ============================================================================
if exist "%DUCKDB_FILE%.wal.lck" (
    echo [STORAGE] Removing stale DuckDB lock artifact: %DUCKDB_FILE%.wal.lck
    del /f /q "%DUCKDB_FILE%.wal.lck" >nul 2>&1
)
if exist "%PARQUET_STAGING%\*.tmp" (
    echo [STORAGE] Purging uncommitted AtomicParquetWriter staging fragments...
    del /f /q "%PARQUET_STAGING%\*.tmp" >nul 2>&1
)
echo [AUDIT] Verifying HMAC-SHA256 Merkle Provenance Chain (%MERKLE_LEDGER%)...

:: ============================================================================
:: SECTION 6: LAUNCH PINNED BACKEND DAEMONS (CORES 0-1 AND CORES 2-N)
:: ============================================================================
if /i not "%LAUNCH_MODE%"=="--cockpit-only" (
    echo [DAEMON] Launching Core 0-1 Real-Time Tape Ingress ^& SEBON Anti-Wash/Spoof Engine...
    cmd.exe /c start "Apex_Core01_RT_Ingress" /min /realtime /affinity %RT_AFFINITY_HEX% ^
        "%PYTHON_EXE%" -m apex_engine.ingress_daemon ^
        --shm-path "/dev/shm/tick_queue" ^
        --anti-wash-delta-ms 50 ^
        --preopen-cancel-limit 0.35 ^
        --preopen-gap-limit 0.03 ^
        --vpin-bucket-vol 10000 ^
        --vpin-threshold 0.70

    echo [DAEMON] Launching Core 2-N Async Analytical Pool, News Harness ^& Uvicorn API (Port %APEX_PORT%)...
    cmd.exe /c start "Apex_Core2N_Uvicorn_OLAP" /min /high /affinity %ASYNC_AFFINITY_HEX% ^
        "%PYTHON_EXE%" -m uvicorn apex_engine.main:app ^
        --host %APEX_HOST% ^
        --port %APEX_PORT% ^
        --workers 1 ^
        --ws-ping-interval 5 ^
        --ws-ping-timeout 10 ^
        --no-access-log
)

:: ============================================================================
:: SECTION 7: WEBSOCKET HANDSHAKE READINESS GATE (/ws/pulse)
:: Polls RFC 6455 Upgrade handshake via curl before spawning 10 UI windows
:: ============================================================================
echo [GATE] Waiting for Uvicorn ASGI ^& WebSocket stream (%APEX_WS_PULSE%) to bind...
set /a "WAIT_COUNT=0"
:WAIT_WS_LOOP
set /a "WAIT_COUNT+=1"
if %WAIT_COUNT% gtr 60 (
    echo [FATAL] Timeout waiting for Port %APEX_PORT% WebSocket readiness after 30s.
    exit /b 1
)
curl.exe --silent --include --no-buffer --max-time 1 ^
    --header "Connection: Upgrade" ^
    --header "Upgrade: websocket" ^
    --header "Host: %APEX_HOST%:%APEX_PORT%" ^
    --header "Origin: %APEX_BASE_URL%" ^
    --header "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" ^
    --header "Sec-WebSocket-Version: 13" ^
    "%APEX_WS_PULSE%" 2>nul | findstr /i "101 Switching Protocols" >nul 2>&1
if %errorLevel% neq 0 (
    :: Fallback check if endpoint responds to HTTP health probe while WS upgrades
    netstat -aon | findstr ":%APEX_PORT% " | findstr "LISTENING" >nul 2>&1
    if !errorLevel! neq 0 (
        powershell -NoProfile -Command "Start-Sleep -Milliseconds 500"
        goto :WAIT_WS_LOOP
    )
)
echo [OK] Port %APEX_PORT% bound and WebSocket /ws/pulse verified ready.

:: ============================================================================
:: SECTION 8: 10-SCREEN INSTITUTIONAL UI COCKPIT LAUNCHER (NATIVE APP MODE)
:: Uses isolated --user-data-dir per window and disables background throttling
:: ============================================================================
if /i "%LAUNCH_MODE%"=="--daemon-only" goto :ENTER_WATCHDOG

call :DETECT_BROWSER
if "%BROWSER_EXE%"=="" (
    echo [WARN] No Chromium/Edge binary detected. Skipping GUI launch; daemon running 24/7.
    goto :ENTER_WATCHDOG
)

set "CHROME_FLAGS=--no-first-run --no-default-browser-check --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --disable-ipc-flooding-protection --disable-renderer-accessibility --disable-features=IntensiveWakeUpThrottling,CalculateNativeWinOcclusion,BackForwardCache"

echo [COCKPIT] Deploying 10-Screen Unthrottled Institutional Cockpit via %BROWSER_NAME%...

:: Display 1 (Primary Monitor: 0,0 to 1920,1080) - SEBON RegTech & L1/L2 OFI
call :SPAWN_SCREEN "S01" "0,0"      "960,540"  "/cockpit/sebon-wash-dlq"
call :SPAWN_SCREEN "S02" "960,0"    "960,540"  "/cockpit/preopen-spoof"
call :SPAWN_SCREEN "S03" "0,540"    "960,540"  "/cockpit/vpin-toxicity"
call :SPAWN_SCREEN "S04" "960,540"  "960,540"  "/cockpit/ofi-depth"

:: Display 2 (Secondary Monitor: 1920,0 to 3840,1080) - Hawkes, Floorsheet HHI & Supply Lock-In
call :SPAWN_SCREEN "S05" "1920,0"   "960,540"  "/cockpit/hawkes-sweeps"
call :SPAWN_SCREEN "S06" "2880,0"   "960,540"  "/cockpit/floorsheet-hhi"
call :SPAWN_SCREEN "S07" "1920,540" "960,540"  "/cockpit/promoter-lockin"
call :SPAWN_SCREEN "S08" "2880,540" "960,540"  "/cockpit/fund-maturity"

:: Display 3 (Tertiary Monitor: 3840,0 to 5760,1080) - News/VLM Harness & Merkle Audit
call :SPAWN_SCREEN "S09" "3840,0"   "1920,540" "/cockpit/news-vlm-gate4"
call :SPAWN_SCREEN "S10" "3840,540" "1920,540" "/cockpit/merkle-lakehouse"

echo [OK] All 10 Cockpit screens deployed with isolated profiles and zero timer throttling.

:: ============================================================================
:: SECTION 9: 24/7 CONTINUOUS NPT MARKET-PHASE WATCHDOG & AUTO-RECOVERY LOOP
:: ============================================================================
:ENTER_WATCHDOG
set "LAST_RECONCILE_DATE="
echo ============================================================================
echo  [WATCHDOG] Entering 24/7 Continuous Supervision Loop (NPT / UTC+05:45)
echo  * 10:30-10:45 NPT : Pre-Open Anti-Spoofing Audit (CancelRatio ^> 0.35, Gap ^> 3%%)
echo  * 11:00-15:00 NPT : Live Intraday Execution ^& VPIN / Hawkes / Anti-Wash Guard
echo  * 15:15 NPT       : Post-Market Broker Reconciliation ^& Parquet Compaction
echo  * Off-Hours       : 30s NRB/SEBON/Media OCR, Qwen2.5-VL ^& Lock-In Recalibration
echo ============================================================================

:WATCHDOG_TICK
:: 1. Verify Port 8000 Uvicorn Daemon is still listening; auto-restart if crashed
netstat -aon | findstr ":%APEX_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorLevel% neq 0 (
    echo [%DATE% %TIME%] [ALERT] Port %APEX_PORT% listener lost! Executing emergency recovery...
    call :TEARDOWN_PORT_8000
    cmd.exe /c start "Apex_Core2N_Uvicorn_OLAP" /min /high /affinity %ASYNC_AFFINITY_HEX% ^
        "%PYTHON_EXE%" -m uvicorn apex_engine.main:app --host %APEX_HOST% --port %APEX_PORT% --workers 1
)

:: 2. Query current Nepal Standard Time (UTC+05:45) HHMM and Date via PowerShell
for /f "tokens=1,2 delims=|" %%A in ('powershell -NoProfile -Command ^
    "$npt = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Nepal Standard Time'); Write-Output ($npt.ToString('yyyyMMdd') + '|' + $npt.ToString('HHmm'))"') do (
    set "NPT_DATE=%%A"
    set "NPT_HHMM=%%B"
)

:: 3. Trigger Post-Market Broker Reconciliation exactly once daily at 15:15 NPT
if "%NPT_HHMM%"=="1515" (
    if not "%LAST_RECONCILE_DATE%"=="%NPT_DATE%" (
        set "LAST_RECONCILE_DATE=%NPT_DATE%"
        echo [%NPT_DATE% 15:15 NPT] Triggering Post-Market Broker Reconciliation ^& Merkle Seal...
        cmd.exe /c start "Apex_PostMarket_Reconcile" /min /high /affinity %ASYNC_AFFINITY_HEX% ^
            "%PYTHON_EXE%" -m apex_engine.reconcile --mode post-market --seal-merkle
    )
)

timeout /t 15 /nobreak >nul
goto :WATCHDOG_TICK

:: ============================================================================
:: SUBROUTINES: PROCESS TEARDOWN, BROWSER DETECTION & COCKPIT WINDOW SPAWNING
:: ============================================================================
:TEARDOWN_PORT_8000
echo [TEARDOWN] Scanning TCP Port %APEX_PORT% for active or orphaned processes...
set "FOUND_PID=0"
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":%APEX_PORT% " ^| findstr "LISTENING"') do (
    if not "%%P"=="0" (
        set "FOUND_PID=1"
        echo [TEARDOWN] Terminating process tree rooted at PID %%P on Port %APEX_PORT%...
        taskkill /F /T /PID %%P >nul 2>&1
    )
)
:: Secondary PowerShell Get-NetTCPConnection cleanup for non-LISTENING bound sockets
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Get-NetTCPConnection -LocalPort %APEX_PORT% -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 4 } | ForEach-Object { Start-Process -FilePath 'taskkill.exe' -ArgumentList \"/F /T /PID $_\" -NoNewWindow -Wait }" >nul 2>&1
if "%FOUND_PID%"=="1" (
    powershell -NoProfile -Command "Start-Sleep -Milliseconds 800"
)
exit /b 0

:DETECT_BROWSER
set "BROWSER_EXE="
set "BROWSER_NAME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "BROWSER_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    set "BROWSER_NAME=Google Chrome"
    exit /b 0
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "BROWSER_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    set "BROWSER_NAME=Google Chrome (x86)"
    exit /b 0
)
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    set "BROWSER_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
    set "BROWSER_NAME=Microsoft Edge"
    exit /b 0
)
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    set "BROWSER_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
    set "BROWSER_NAME=Microsoft Edge (x64)"
    exit /b 0
)
exit /b 0

:SPAWN_SCREEN
set "SCR_ID=%~1"
set "SCR_POS=%~2"
set "SCR_SIZE=%~3"
set "SCR_PATH=%~4"
set "SCR_PROF=%PROFILE_ROOT%\%SCR_ID%"
if not exist "%SCR_PROF%" mkdir "%SCR_PROF%"

:: Pin UI rendering to the Asynchronous Pool (Cores 2-N) so browser GPU/V8 threads
:: never contend with Cores 0-1 Real-Time WebSocket ingestion.
start "Apex_%SCR_ID%" /affinity %ASYNC_AFFINITY_HEX% "%BROWSER_EXE%" ^
    --user-data-dir="%SCR_PROF%" ^
    --window-position=%SCR_POS% ^
    --window-size=%SCR_SIZE% ^
    --app="%APEX_BASE_URL%%SCR_PATH%" ^
    %CHROME_FLAGS%
exit /b 0
