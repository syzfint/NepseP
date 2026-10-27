# Architectural Specification and Batch Orchestration Design for the ApexMarketEngine Single-PC Surveillance Daemon and 10-Screen Cockpit

---

## Executive Summary and Operational Paradigm

Frontier equity venues such as the Nepal Stock Exchange (NEPSE) are undergoing a structural transition from pre-funded cash-and-carry settlement toward leveraged margin trading, intraday short-selling, and open API order routing. While this evolution deepens market liquidity, it simultaneously exposes trading infrastructure to acute microstructure pathologies, including:
- **Sub-millisecond circular wash trading** ($\Delta t < 50\text{ms}$)
- **Pre-open indicative price painting** (false equilibrium distortion)
- **Toxic informed order flow** (informed queue front-running and adverse selection)
- **Abrupt secondary-market supply shocks** triggered by the expiration of promoter share lock-in periods and mutual fund institutional quotas.

Legacy architectures that rely on disconnected polling scripts and static end-of-day batch reporting lack the temporal resolution required to intercept manipulative order flow before execution occurs. Consolidating six real-time regulatory technology (RegTech) and quantitative intelligence vectors into a single 24/7 daemon running natively on one local workstation eliminates network hop jitter across external edge nodes, enforces deterministic memory locality, and guarantees that unverified signals are purged at ingestion prior to analytical storage.

Executing a high-frequency WebSocket ingestion pipeline, an analytical lakehouse powered by Apache Arrow and DuckDB, a multimodal large language model and vision-language model (LLM/VLM) news harness, and a 10-screen institutional user interface on a single physical host PC introduces severe operating system contention:
1. **Port Locking:** Orphaned ASGI web server workers lock TCP port 8000 across ungraceful restarts.
2. **Browser Renderer Throttling:** Background browser windows suffer aggressive Chromium timer throttling ($1\text{ Hz} \to 0.0167\text{ Hz}$) that stalls real-time WebSocket rendering and builds up Mojo IPC queues.
3. **Core & Cache Contention:** CPU-intensive OLAP scans or neural network inferences starve real-time Level-1/Level-2 order book parsers of processor cache lines.

The `run_terminal.bat` launcher functions as the deterministic supervisor and hypervisor script for the entire ApexMarketEngine runtime. Rather than acting as a simplistic command wrapper, the batch orchestrator bridges Win32 process management with POSIX kernel memory primitives, enforces hardware CPU core pinning via hexadecimal affinity bitmasks, executes recursive process-tree teardowns on TCP port 8000, validates RFC 6455 WebSocket upgrade handshakes, and deploys an unthrottled 10-window Chromium or Microsoft Edge cockpit mapped deterministically across multi-monitor coordinate spaces.

---

## Hybrid Single-PC Kernel and Process Isolation Topology

A defining architectural requirement of the ApexMarketEngine specification is the simultaneous enforcement of POSIX real-time kernel directives—specifically `SCHED_FIFO` first-in-first-out real-time scheduling, `/dev/shm/tick_queue` shared memory, and `/etc/sysctl.d/99-zram.conf` virtual memory tuning—alongside native Windows batch execution (`run_terminal.bat`) and Win32 process tree termination (`taskkill /F /T /PID`). On a single physical host workstation, reconciling these requirements necessitates a dual-domain execution architecture that bridges the Windows NT kernel and the Windows Subsystem for Linux 2 (WSL2) real-time Linux kernel, or an equivalent native Win32/POSIX shared-memory abstraction.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                      HYBRID SINGLE-PC DUAL-DOMAIN EXECUTION TOPOLOGY                            │
├─────────────────────────────────────────────────┬───────────────────────────────────────────────┤
│          WINDOWS NT SUBSYSTEM DOMAIN            │               WSL2 POSIX DOMAIN               │
├─────────────────────────────────────────────────┼───────────────────────────────────────────────┤
│ • run_terminal.bat (Hypervisor / Supervisor)    │ • /dev/shm/tick_queue (POSIX Zero-Copy Shm)   │
│ • Win32 taskkill /F /T /PID (Tree Reclamation)  │ • SCHED_FIFO Priority 99 (chrt -f 99)         │
│ • NetTCPConnection / Netstat Socket Auditing    │ • ZRAM In-RAM Block Compression (lz4/zstd)   │
│ • 10-Screen Chromium/Edge Cockpit (App Mode)    │ • vm.swappiness=100, vm.page-cluster=0        │
│ • CPU Affinity Masking (Cores 0-1 vs Cores 2-N) │ • vm.vfs_cache_pressure=500                   │
└─────────────────────────────────────────────────┴───────────────────────────────────────────────┘
```

---

## CPU Core Pinning and Hexadecimal Affinity Bitmask Algebra

To guarantee that DuckDB OLAP scans across 150 million historical floorsheet records, fractional differentiation ($d = 0.35$), or Qwen2.5-VL-3B vision-language inference never preempt live NEPSE WebSocket frame ingestion, the host CPU must be partitioned at the OS scheduler level.

In both Windows and Linux scheduling architectures, each logical processor $k \in \{0, 1, \dots, N-1\}$ corresponds to bit position $k$ in a binary affinity mask, carrying a decimal weight of $2^k$. The Windows `start /affinity <HexMask>` command and the underlying Win32 `SetProcessAffinityMask` system call require this processor mask to be passed as a hexadecimal value:

$$\text{AffinityMask}_{\text{hex}}(C) = \text{Hex}\left(\sum_{k \in C} 2^k\right)$$

where $C$ denotes the subset of zero-indexed logical processors permitted to execute threads for the target process.

### Real-Time Ingress Pool (Cores 0 & 1)
Enabling logical processors 0 and 1 sets bit 0 ($2^0 = 1$) and bit 1 ($2^1 = 2$), producing the binary bitmask `00000011` and an exact hexadecimal affinity value of `0x3` (or `0x0003`). On the Windows host layer, `run_terminal.bat` spawns the primary WebSocket ingestion and anti-wash filter daemon using:
```cmd
cmd.exe /c start "Apex_RT_Ingress" /realtime /affinity 0x3
```
This simultaneously binds the process to Cores 0–1 and elevates its Windows scheduling priority class to `REALTIME_PRIORITY_CLASS`. Within the WSL2 Linux environment, the corresponding real-time worker is pinned to the identical hardware threads and elevated to deterministic POSIX first-in-first-out scheduling via `chrt -f 99 taskset -c 0,1` (coupled with `isolcpus` and `nohz_full` kernel boot parameters where supported to suppress timer ticks).

### Asynchronous Analytical Pool (Cores 2 to $N-1$)
Conversely, the asynchronous analytical, microstructure, and OLAP pool is restricted to Cores 2 through $N-1$. This pool executes Cont-Stoikov Order Flow Imbalance (OFI) calculations, Hawkes point-process matrix solvers, Volume-Synchronized Probability of Informed Trading (VPIN) bucketing, Multilingual FinBERT sentiment scoring, and DuckDB analytical queries.

Subtracting the Core 0–1 bitmask ($3$) from the all-processor bitmask ($2^N - 1$) yields the exact hexadecimal affinity mask for the asynchronous worker pool across any core count $N$:

$$\text{AffinityMask}_{\text{Async}}(N) = \text{Hex}\left((2^N - 1) - 3\right)$$

### Dynamic Affinity Mask Table

| Host Logical Processors ($N$) | All-Cores Decimal ($2^N-1$) | Cores 0–1 Binary / Hex Mask (Real-Time Ingress) | Cores 2–$N$ Binary / Hex Mask (Async Analytical Pool) | Windows CLI Launch Directive | Linux / WSL2 Equivalent Directive |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **6 Cores** | $63$ | `000011` / `0x3` | `111100` / `0x3C` | `start /realtime /affinity 0x3` vs `start /high /affinity 0x3C` | `chrt -f 99 taskset -c 0,1` vs `taskset -c 2-5` |
| **8 Cores** | $255$ | `00000011` / `0x03` | `11111100` / `0xFC` | `start /realtime /affinity 0x03` vs `start /high /affinity 0xFC` | `chrt -f 99 taskset -c 0,1` vs `taskset -c 2-7` |
| **12 Cores** | $4,095$ | `000000000011` / `0x003` | `111111111100` / `0xFFC` | `start /realtime /affinity 0x003` vs `start /high /affinity 0xFFC` | `chrt -f 99 taskset -c 0,1` vs `taskset -c 2-11` |
| **16 Cores** | $65,535$ | `0x0003` | `0xFFFC` | `start /realtime /affinity 0x0003` vs `start /high /affinity 0xFFFC` | `chrt -f 99 taskset -c 0,1` vs `taskset -c 2-15` |
| **24 Cores** | $16,777,215$ | `0x000003` | `0xFFFFFC` | `start /realtime /affinity 0x000003` vs `start /high /affinity 0xFFFFFC` | `chrt -f 99 taskset -c 0,1` vs `taskset -c 2-23` |
| **32 Cores** | $4,294,967,295$ | `0x00000003` | `0xFFFFFFFC` | `start /realtime /affinity 0x00000003` vs `start /high /affinity 0xFFFFFFFC` | `chrt -f 99 taskset -c 0,1` vs `taskset -c 2-31` |
| **64 Cores** | $18,446,744,073,709,551,615$ | `0x0000000000000003` | `0xFFFFFFFFFFFFFFFC` | `start /realtime /affinity 0x3` vs `start /high /affinity 0xFFFFFFFFFFFFFFFC` | `chrt -f 99 taskset -c 0,1` vs `taskset -c 2-63` |

Because institutional workstations vary in core count and Hyper-Threading or Simultaneous Multithreading (SMT) exposes two logical processors per physical core, hardcoding a static hexadecimal mask in `run_terminal.bat` either leaves upper cores idle or triggers a `SetValueInvocationException` ("The parameter is incorrect") when a mask bit exceeds the installed logical processor count. `run_terminal.bat` dynamically reads `%NUMBER_OF_PROCESSORS%` at startup and calculates the exact bitmask via bitwise shift arithmetic.

---

## Zero-Copy Shared Memory and ZRAM Virtual Memory Tuning

Sustaining sub-millisecond verification between the Core 0–1 ingestion engine and the Core 2–$N$ analytical consumers requires eliminating serialization and socket-copy overhead. Raw NEPSE WebSocket ticks that pass the anti-wash filter are written directly into POSIX shared memory (`/dev/shm/tick_queue`) formatted as zero-copy Apache Arrow Columnar RecordBatches.

When `run_terminal.bat` initializes the runtime environment, it invokes an administrative WSL2 kernel configuration routine that enforces the virtual memory parameters specified in `/etc/sysctl.d/99-zram.conf`:

1. **`vm.swappiness = 100` (or 200 on newer kernels):** Directs the kernel memory manager to proactively swap idle anonymous memory pages—such as dormant LLM weights or off-hours scraping buffers—into compressed in-RAM ZRAM block devices (`lz4` or `zstd`). This guarantees that physical, unswappable DRAM frames remain continuously available for `/dev/shm/tick_queue` and live Level-1/Level-2 order book ring buffers.
2. **`vm.page-cluster = 0`:** Disables multi-page swap read-ahead clustering. Whereas default kernel behavior reads $2^3 = 8$ contiguous pages during a page fault, `vm.page-cluster = 0` restricts ZRAM decompression to individual $4\text{ KB}$ pages, preventing decompression tail-latency spikes from stalling analytical workers during market hours.
3. **`vm.vfs_cache_pressure = 500`:** Accelerates kernel reclamation of Virtual File System (VFS) directory and inode caches accumulated during high-frequency Parquet micro-batching and 30-second regulatory PDF scraping cycles.

---

## Deterministic Process Teardown and Concurrency Recovery on Port 8000

A critical operational vulnerability in single-PC Python/Uvicorn surveillance appliances occurs during ungraceful restarts, unhandled exceptions, or manual console closures. When an ASGI server such as Uvicorn spawns worker processes, multiprocessing resource trackers, Tesseract OCR sub-processes, and asynchronous storage threads (`AtomicParquetWriter` and `DuckDBConnectionManager`), terminating the parent wrapper via a standard console close or shallow `taskkill /PID` leaves orphaned descendant processes running in the background. These zombie processes retain ownership of TCP port 8000 (`127.0.0.1:8000`, `0.0.0.0:8000`, or IPv6 `[::1]:8000`), triggering `Port 8000 is already in use (EADDRINUSE)` fatal bind errors on subsequent launches and locking DuckDB write-ahead log (`.wal`) files.

### Process Tree Termination Mechanics
To guarantee deterministic port reclamation before initializing the surveillance daemon, `run_terminal.bat` implements a multi-layered process tree teardown pipeline:
1. **Socket Resolution to PID:** The script resolves active socket descriptors to their owning Process IDs (PIDs) by executing:
   ```cmd
   netstat -aon | findstr ":8000 " | findstr "LISTENING"
   ```
   Parsing the stream with `for /f "tokens=5"` extracts the exact PID across both IPv4 and IPv6 listening interfaces.
2. **Recursive Tree Kill (`/T /F`):** `taskkill /F /T /PID <PID>` instructs the Win32 kernel to perform a genuine recursive tree kill, traversing the parent-child process hierarchy to terminate root and descendant worker processes, OCR child binaries, and tunnels, while `/F` forces immediate termination without waiting for hung event loops.
3. **PowerShell Network Stack Secondary Sweep:** Sockets in transitional `BOUND` or `CLOSE_WAIT` states not matched by `LISTENING` are caught using PowerShell:
   ```powershell
   Get-NetTCPConnection -LocalPort 8000 | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 4 } | ForEach-Object { taskkill /F /T /PID $_ }
   ```
4. **Storage Artifact Sanitization:** Purging stale `.wal.lck` and `.tmp` Parquet staging fragments ensures that `DuckDBConnectionManager` singleton pool acquires its primary read-write file lock cleanly, while preserving the cryptographic continuity of the append-only HMAC-SHA256 Merkle provenance chain:

$$H_t = \text{HMAC-SHA256}\left(K_{\text{secret}}, H_{t-1} \parallel \text{seq} \parallel \text{payload\_hash} \parallel t\right)$$

---

## WebSocket Handshake Readiness Gate (`/ws/pulse`)

Launching ten Chromium or Edge cockpit windows immediately after invoking `start uvicorn` results in blank `ERR_CONNECTION_REFUSED` screens because the Python backend requires several seconds to initialize memory-mapped DuckDB tables, load Multilingual FinBERT weights, and attach to `/dev/shm/tick_queue`.

To synchronize graphical cockpit deployment with backend readiness, `run_terminal.bat` interposes an active readiness gate using native `curl.exe` to execute an RFC 6455 WebSocket upgrade handshake against `http://127.0.0.1:8000/ws/pulse`:
```cmd
curl.exe --silent --include --no-buffer --max-time 1 ^
    --header "Connection: Upgrade" ^
    --header "Upgrade: websocket" ^
    --header "Host: 127.0.0.1:8000" ^
    --header "Origin: http://127.0.0.1:8000" ^
    --header "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" ^
    --header "Sec-WebSocket-Version: 13" ^
    "http://127.0.0.1:8000/ws/pulse"
```
In accordance with libcurl WebSocket protocol semantics, a plain HTTP 200 response is treated as an upgrade failure, and a **101 Switching Protocols** response confirms live framing readiness.

---

## Multi-Monitor 10-Screen Institutional Cockpit Architecture

The ApexMarketEngine exposes its six real-time surveillance and intelligence engines through a 10-Screen Institutional UI Cockpit launched in native browser application mode (`--app=<URL>`).

### Overcoming Chromium Broker Coalescing
When a Chromium-based browser (`chrome.exe` or `msedge.exe`) is launched, the executable checks for an active browser process lock within the default user data directory. If an existing browser session is detected, the newly spawned executable passes its command-line arguments to the running parent broker process and terminates immediately. In this coalesced state, Chromium and Edge systematically ignore `--window-position` and `--window-size` parameters, cascading all windows onto the primary monitor.

To force independent process trees that strictly respect multi-monitor coordinate placement, `run_terminal.bat` provisions a dedicated, exclusive `--user-data-dir` directory for every window (`%LOCALAPPDATA%\ApexMarketEngine\CockpitProfiles\S01` through `S10`). This also assigns a unique `AppUserModelId` (`Chrome.{user-data-dir}`) to each screen, isolating taskbar icons and preventing memory leaks or WebGL crashes in one window from impacting the remaining nine.

### Eliminating Background Timer and Occlusion Throttling
Chromium's power-efficiency scheduler subjects background, minimized, or occluded windows to severe throttling:
- **Stage 1 (Regular Background Throttling):** Clamps high-frequency timers from 60–100 Hz down to $1\text{ Hz}$.
- **Stage 2 (IntensiveWakeUpThrottling):** After 60 seconds of occlusion, collapses timers to 1 wake-up per minute ($0.0167\text{ Hz}$).

In high-throughput surveillance, a 60-second rendering freeze causes WebSocket frames to back up in Mojo IPC queues until frames are dropped or the connection is severed. Crucial alerts ($\text{VPIN} \ge 0.70$ or pre-open spoofing) are unacceptably delayed.

`run_terminal.bat` injects specific anti-throttling flags into every window invocation:

| Chromium / Edge CLI Switch | Subsystem Target | Operational Mechanism & Surveillance Justification |
| :--- | :--- | :--- |
| `--app=<URL>` | Window Shell | Launches the endpoint in native frameless application mode without an address bar or tab strip. |
| `--user-data-dir=<Path>` | Process Broker | Forces an independent browser instance per screen so `--window-position` and `--window-size` are honored. |
| `--disable-background-timer-throttling` | Blink Scheduler | Prevents Chromium from clamping `setTimeout`/`setInterval` timers to 1 Hz in non-foreground windows. |
| `--disable-renderer-backgrounding` | OS Process Priority | Prevents the broker from lowering the Windows process priority class of non-foreground renderer processes. |
| `--disable-backgrounding-occluded-windows` | Win32 Occlusion | Stops Chromium from treating cockpit windows covered by overlapping windows as background tabs. |
| `--disable-ipc-flooding-protection` | Mojo IPC Bus | Removes the default 10-IPC-calls-per-second-per-frame throttle so high-frequency bursts do not stall IPC. |
| `--disable-features=IntensiveWakeUpThrottling,CalculateNativeWinOcclusion,BackForwardCache` | Feature Flags | Disables 1-wake-up-per-minute clamping, native occlusion tracking, and page freeze caching. |

*(Note: `--disable-background-networking` is intentionally omitted, as Chromium bug reports show it blocks enterprise extension policies and internal component updates).*

### 10-Screen Cockpit Mapping & Quantitative Risk Trigger Specification

Workspace topology: Three $1920\times 1080$ monitors arranged horizontally ($5760\times 1080$ total desktop canvas).

| Screen ID | Cockpit Module Name | Subsystem Vector | Profile Dir | Position ($X,Y$) & Size ($W,H$) | Target Route | Governing Mathematical Model & Risk Trigger | Automated Downstream Action |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Screen 01** | SEBON Anti-Wash & DLQ Guard | 3.1 SEBON RegTech | `...\CockpitProfiles\S01` | `0,0` / `960,540` | `/cockpit/sebon-wash-dlq` | `buyerMemberId == sellerMemberId` or circular ring within $\Delta t < 50\text{ms}$ | Purges tick at ingress; isolates violation into Dead-Letter Queue (DLQ). |
| **Screen 02** | Pre-Open Anti-Spoofing Auditor | 3.1 SEBON RegTech | `...\CockpitProfiles\S02` | `960,0` / `960,540` | `/cockpit/preopen-spoof` | $\text{CancellationRatio}_{\text{preopen}} = \frac{\text{CanceledBidVol}}{\text{SubmittedBidVol}} > 0.35$ & Gap $> +3.0\%$ | Aborts Market-on-Open (MOO) execution tickets during 10:30–10:45 NPT. |
| **Screen 03** | Live VPIN Order-Book Toxicity | 3.1 SEBON RegTech | `...\CockpitProfiles\S03` | `0,540` / `960,540` | `/cockpit/vpin-toxicity` | $V_{\text{bucket}} = 10,000$ shares; live $\text{VPIN} \ge 0.70$ or $\text{CDF}(\text{VPIN}) \ge 0.90$ | Immediately revokes passive limit orders and pauses child slices. |
| **Screen 04** | Cont-Stoikov OFI & L1/L2 Depth | 3.3 Microstructure | `...\CockpitProfiles\S04` | `960,540` / `960,540` | `/cockpit/ofi-depth` | $\text{OFI}(t) = e_b(t) - e_a(t)$ normalized to $\text{NOFI}(t) \in [-1.0, 1.0]$ | Feeds real-time queue depletion signals into Gate G4 Meta-Labeler. |
| **Screen 05** | Hawkes Syndicate Sweep Radar | 3.3 Broker Intel | `...\CockpitProfiles\S05` | `1920,0` / `960,540` | `/cockpit/hawkes-sweeps` | $\lambda_i(t) = \mu_i + \sum_{t_j < t} \alpha_i e^{-\beta_i(t - t_j)}$; Branching $\eta_i = \alpha_i / \beta_i \to 1.0$ | Flags anchor broker sweeps (#58, #45); scales TWAP/VWAP pace. |
| **Screen 06** | Floorsheet Accumulation Heatmap | 3.3 Floorsheet Engine | `...\CockpitProfiles\S06` | `2880,0` / `960,540` | `/cockpit/floorsheet-hhi` | Herfindahl-Hirschman Index $\text{HHI} = \sum s_k^2 > 2,500$ across 150M+ rows | Identifies institutional sector rotation and desk concentration. |
| **Screen 07** | Promoter Lock-In Expiry Tracker | 3.4 Supply Tracker | `...\CockpitProfiles\S07` | `1920,540` / `960,540` | `/cockpit/promoter-lockin` | $\text{SupplyOverhangScore}(i,t) = \frac{\text{PromoterShares}_i}{\text{ADV}_{i,30\text{d}}} e^{-\frac{\lvert \tau_{\text{lockin},i} - t \rvert}{30}} > 15.0$, $\Delta \tau \le 14\text{d}$ | Triggers `PROMOTER_LOCKIN_EXPIRY_RISK`; caps weight $w_i \le 0.02$. |
| **Screen 08** | Mutual Fund & Quota Maturity | 3.4 Maturity Monitor | `...\CockpitProfiles\S08` | `2880,540` / `960,540` | `/cockpit/fund-maturity` | 6-month pre-IPO institutional quota & closed-end fund maturity horizon | Forecasts secondary supply overhangs; degrades asset Health Score. |
| **Screen 09** | NRB/SEBON News & VLM Harness | 3.2 News & Policy | `...\CockpitProfiles\S09` | `3840,0` / `1920,540` | `/cockpit/news-vlm-gate4` | FinBERT $S_{\text{news}} \in [-1,1]$, Qwen2.5-VL-3B, Gate G4 $\text{logit}(P_{\text{success}})$ | Recalibrates log-odds success probability; shifts to defensive cash. |
| **Screen 10** | Lakehouse & Merkle Audit Chain | 4.0 Persistence | `...\CockpitProfiles\S10` | `3840,540` / `1920,540` | `/cockpit/merkle-lakehouse` | $H_t = \text{HMAC-SHA256}(K_{\text{secret}}, H_{t-1} \parallel \text{seq} \parallel \text{payload\_hash} \parallel t)$ | Verifies non-repudiable order/fill audit chain & DuckDB/Parquet health. |

---

## 24/7 Nepal Standard Time (NPT) Operational State Machine

The supervisor watchdog loop monitors port 8000 and transitions through four NPT operational regimes:

$$\text{NPT} = \text{UTC} + 05:45$$

```
   ┌────────────────────────────────────────────────────────────────────────┐
   │             24/7 NEPAL STANDARD TIME (UTC+05:45) STATE MACHINE          │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │
     ┌─────────────────────────────────┼─────────────────────────────────┐
     │                                 │                                 │
     ▼                                 ▼                                 ▼
 10:30 - 10:45 NPT                 11:00 - 15:00 NPT                 15:15 - 15:30 NPT
 [PRE-OPEN AUDIT]               [CONTINUOUS SURVEILLANCE]          [POST-MARKET RECON]
 • L1/L2 Indicative Gap          • Δt < 50ms Wash Intercept        • Flush shm to Parquet
 • CancelRatio > 0.35            • VPIN Vol Buckets (10k)          • 150M+ Row HHI Table Update
 • MOO Execution Abort           • Hawkes Syndicate Radar          • Seal HMAC Merkle Root
                                 • Realtime Port 8000 Recovery
                                       │
                                       ▼
                               15:30 - 10:30 NPT
                            [OFF-HOURS MACRO & AI]
                            • 30s NRB/SEBON Media Scrape
                            • Tesseract OCR (<180ms/pg)
                            • Qwen2.5-VL-3B Cloudflare Bridge
                            • FinBERT News Score S_news
                            • Promoter Lock-In Decay Kernel
```

### Operational Schedule Breakdown

1. **10:30 AM – 10:45 AM NPT (Pre-Open Anti-Spoofing Audit):**
   Cores 0–1 inspect indicative equilibrium price formation. If:
   $$\text{CancellationRatio}_{\text{preopen}} = \frac{\text{CanceledBidVolume}}{\text{TotalSubmittedBidVolume}} > 0.35 \quad \text{and} \quad \text{Gap} > +3.0\%$$
   the engine flags tape painting and aborts pending Market-on-Open (MOO) orders.

2. **11:00 AM – 03:00 PM NPT (Live Continuous Surveillance):**
   All microstructure guards run at full capacity. Trades where `buyerMemberId == sellerMemberId` or circular rings transact with $\Delta t < 50\text{ms}$ are purged on Cores 0–1 into the Dead-Letter Queue. On Cores 2–$N$, VPIN ($V_{\text{bucket}} = 10,000$, threshold $\ge 0.70$) and Hawkes branching ratios ($\eta_i \to 1.0$ with $\text{HHI} > 2,500$) drive TWAP/VWAP pace adjustments.

3. **03:15 PM – 03:30 PM NPT (Post-Market Reconciliation):**
   Flushes residual `/dev/shm` ticks to NVMe via `AtomicParquetWriter`, refreshes the 150M+ row DuckDB floorsheet accumulation tables, and seals the HMAC-SHA256 Merkle root.

4. **03:30 PM – 10:30 AM NPT (Off-Hours Macro & AI Harness):**
   Polls ShareSansar, Merolagani, Bizmandu, Nepali Paisa, NRB, and SEBON every 30 seconds. Devanagari circulars are OCR'd, circular charts are processed via Qwen2.5-VL-3B, and Multilingual FinBERT updates Gate G4 log-odds:
   $$\text{logit}(P_{\text{success}}) = \text{logit}(P_{\text{base}}) + \Delta_{\text{ChronosDrift}} + \Delta_{\text{Kronos}} + \Delta_{\text{OFI}} + \Delta_{\text{MacroNews}} - \text{Penalty}_{\text{T+2 Vol}}$$
   Promoter lock-in exponential decay is computed:
   $$\text{SupplyOverhangScore}(i, t) = \frac{\text{PromoterSharesToRelease}_i}{\text{AverageDailyVolume}_{i, 30\text{d}}} \times \exp\left(-\frac{\vert{}\tau_{\text{lockin}, i} - t\vert{}}{30}\right)$$
   Securities with $\text{SupplyOverhangScore} > 15.0$ within 14 days are tagged `PROMOTER_LOCKIN_EXPIRY_RISK` ($w_i \le 0.02$).

---

## Architectural Conclusions and Second-Order Failure Mitigations

1. **Browser V8 & GPU Compositor Contention:**
   By explicitly passing `/affinity %ASYNC_AFFINITY_HEX%` to `start "%BROWSER_EXE%"`, all Chromium/Edge browser, renderer, utility, and GPU compositor threads are confined to Cores 2–$N$. Cores 0 and 1 remain completely isolated for live NEPSE WebSocket ingestion and $\Delta t < 50\text{ms}$ anti-wash ring filtering.
2. **Mitigating netstat PID 0 False Positives & TIME_WAIT Collisions:**
   When the port 8000 listener terminates, sockets in `TIME_WAIT` report PID 0 or 4. Naive termination crashes or kills system processes. The teardown routine pairs a strict `LISTENING` filter and trailing-space port delimiter (`":8000 "`) with explicit guards (`if not "%%P"=="0"` and `Where-Object { $_ -gt 4 }`).
3. **Resilient Timezone Resolution for Continuous 24/7 NPT:**
   Rather than relying on locale-dependent Windows Batch `%TIME%` parsing, timestamp evaluation inside `:WATCHDOG_TICK` uses .NET `[System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, 'Nepal Standard Time')`, ensuring exact state transitions across any workstation locale.

---

## Advances in Financial Machine Learning (AFML) Statistical Overfitting Gates

To prevent data snooping and multi-trial selection bias across NEPSE quantitative factors, the runtime integrates Marcos López de Prado's *Advances in Financial Machine Learning* (AFML) validation battery into Gate AFML:

### 1. Deflated Sharpe Ratio (DSR) & Minimum Track Record Length (MinTRL)
Standard Sharpe ratio evaluation overstates statistical significance when $N$ strategy variations are tested. The expected maximum Sharpe ratio under the null hypothesis of zero skill is:
$$\mathbb{E}[\max_{n=1,\dots,N} \text{SR}_n] \approx \sqrt{\mathbb{V}[\text{SR}]} \left( (1 - \gamma)\Phi^{-1}\left(1 - \frac{1}{N}\right) + \gamma \Phi^{-1}\left(1 - \frac{1}{N e}\right) \right)$$
where $\gamma \approx 0.5772$ is the Euler-Mascheroni constant and $\Phi$ is the standard normal CDF. The Deflated Sharpe Ratio adjusts for non-normality (skewness $S$, kurtosis $K$) and sample length $T$:
$$\text{DSR} = \Phi\left(\frac{(\widehat{\text{SR}} - \text{SR}^*) \sqrt{T - 1}}{\sqrt{1 - S\widehat{\text{SR}} + \frac{K - 1}{4}\widehat{\text{SR}}^2}}\right)$$
Candidate factor allocations require $\text{DSR} \ge 0.95$ and track record $T \ge \text{MinTRL}$ to receive capital.

### 2. Combinatorially Symmetric Cross-Validation (CSCV) & PBO
Evaluating factor robustness via Combinatorially Symmetric Cross-Validation divides $T$ historical periods into $S = 16$ contiguous partitions, generating $\binom{S}{S/2} = 12,870$ train/test combinations. The Probability of Backtest Overfitting is calculated as:
$$\text{PBO} = \int_{-\infty}^0 f(\text{SR}_{\text{OOS}}) \, d\text{SR}_{\text{OOS}} \le 0.15$$

### 3. White's Reality Check & Hansen's Superior Predictive Ability (SPA)
Stationary bootstrap resampling ($B = 500$ iterations, geometric mean block length $q = 10$) tests whether any proposed NEPSE factor outperforms the index benchmark after accounting for data-snooping dependencies.

---

## Institutional Cockpit Visual Components (Screen S04 & Screen S10)

### Screen S04: Cont-Stoikov OFI & L1/L2 Depth Cockpit (`/cockpit/ofi-depth`)
- **Theme:** JetBrains Mono typography, `#030712` institutional dark palette.
- **Normalized OFI Gauge:** Real-time dynamic gauge $[-1.0, +1.0]$ depicting instantaneous buyer replenishment vs seller queue depletion.
- **Micro-Price Divergence:** Real-time computation of Stoikov Micro-Price vs Mid-Price:
  $$P_{\text{micro}} = \frac{P_{\text{ask}} V_{\text{bid}} + P_{\text{bid}} V_{\text{ask}}}{V_{\text{bid}} + V_{\text{ask}}}$$
- **10-Level Visual Depth Ladder:** Consolidated Bid/Ask order book with volumetric bar overlays and queue depletion alert tags.

### Screen S10: Merkle Provenance Lakehouse & 3D Overfitting Surface (`/cockpit/merkle-lakehouse`)
- **Three.js WebGL Interactive Surface:** Real-time parametric 3D rendering of the PBO surface (Trials $N \times$ In-Sample Sharpe vs Out-of-Sample Degradation). OrbitControls support interactive pan, rotate, and zoom.
- **Continuous HMAC-SHA256 Ledger:** Live block feed verifying chain integrity from Genesis (`#0`) to Tip:
  $$H_t = \text{HMAC-SHA256}(K_{\text{secret}}, H_{t-1} \parallel \text{seq} \parallel \text{hash}(\text{payload}) \parallel t)$$
- **Lakehouse Health Telemetry:** Tracks row counts in `market_master_union.parquet` (740,998+ rows), SHA-256 partition hashes, and SEBON DLQ quarantine metrics.
