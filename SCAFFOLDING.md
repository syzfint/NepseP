# 🏛️ APEXMARKETENGINE — CODEBASE SCAFFOLDING & TAXONOMY

ApexMarketEngine follows an institutional **Five-Tier Quantitative Architecture** combining an ultra-low latency C/Python ingress kernel, Medallion Lakehouse (Bronze / Silver / Gold), 24/7 autonomous lifecycle state machines, and a unified 10-screen surveillance cockpit.

---

## 📂 Master Directory Tree

```text
neps/
├── 🚀 EXECUTION & ORCHESTRATION (Tier 0)
│   ├── run.bat                              # Unified One-Command Master Launcher (Port 8000 + 10-in-1 Cockpit)
│   ├── apex.bat                             # Instant CLI runner alias
│   ├── run_surveillance_cockpit.bat         # 10-Screen Multi-Monitor Hypervisor (Hardware CPU affinity)
│   ├── run_terminal.bat                     # Apex Wealth PMS Enterprise Launchpad (Port 8888)
│   ├── launch_hedge_terminal.bat            # Hedge Fund Asset Management Terminal
│   └── launch_prism_station.py              # Chronostrata Prism Station Launcher
│
├── ⚡ ENGINE & SERVERS (Tier 1)
│   └── apex_engine/                         # Low-Latency Core 0-1 Ingress & ASGI Web Server
│       ├── main.py                          # FastAPI ASGI entrypoint, /ws/pulse, and Cockpit routes
│       ├── api_server.py                    # REST microservices (TPO, 3D Optimization, Lakehouse stats)
│       ├── config.py                        # Network bindings, CPU core masks, buffer parameters
│       ├── ingress_daemon.py                # Core 0-1 Tape Ingress, SEBON Anti-Wash, and VPIN tracker
│       └── templates/                       # Cockpit WebGL/Canvas visual templates
│           ├── screen_unified_master.html   # Master 10-in-1 Unified Cockpit (Zero Degradation)
│           ├── screen_s04_ofi_depth.html    # Screen S04: Cont-Stoikov OFI, 10-Level L2 Depth, TPO Profile
│           └── screen_s10_merkle_lakehouse.html # Screen S10: MT5 Strategy Tester 3D Surfaces & Merkle Ledger
│
├── 🌊 MEDALLION LAKEHOUSE DATA TIERS (Tier 2)
│   ├── 01_raw/                              # Bronze Tier: Raw news corpus, scraped parquet archives
│   ├── 01_raw_data/                         # Bronze Tier: Historical raw daily floorsheet parquet files
│   ├── 02_processed_parquet/                # Silver Tier: Cleaned & deduplicated market OHLCV union (740k bars)
│   ├── 03_feature_store/                    # Gold Tier: Technical factors, sentiment, Chronos quantiles
│   ├── data/                                # Live staging, nfrs ledger, portfolio, SEBON DLQ quarantine
│   │   ├── merkle_provenance.chain          # HMAC-SHA256 Cryptographic Audit Trail
│   │   ├── parquet_staging/                 # AtomicParquetWriter zero-copy staging
│   │   ├── sebon_dlq/                       # Quarantined wash-trade and self-matching records
│   │   └── portfolio/                       # Demat holdings and execution allocations
│   ├── nepse_lakehouse/                     # Hive-partitioned streaming parquet lakehouse
│   └── static_data/                         # Point-in-Time broker master, promoter lockin, live state
│
├── 🧠 QUANTITATIVE PIPELINES & SCRIPTS (Tier 3)
│   └── scripts/
│       ├── 00_control/                      # 24/7 Sovereign Autonomous Lifecycle Engine & RD Agent
│       │   └── sovereign_live_autonomous_daemon.py  # Sun-Thu 11AM-3PM Live Trading & Reconciliation
│       ├── 01_etl_and_ingestion/            # Live WebSocket streamer, Playwright scrapers, session daemon
│       ├── 02_modeling_and_calculations/    # OFI depth, TPO profiles, VPIN, Hawkes, HRP, MDP policies
│       ├── 03_agentic_cio/                  # Institutional IP shield, Chat CIO, Hedge fund terminal
│       ├── 04_backtesting/                  # Sovereign Alpha Miner, Deflated Sharpe, PBO, Surface Smoother
│       ├── 05_forensic_audit_gates/         # Gates G0 to G10, Zero-Trust verification suite
│       ├── 06_forecasting_and_charts/       # Chronos probabilistic projections, publication tear sheets
│       ├── 07_clef_sentiment/               # Multimodal Nepali NLP, LoRA fine-tuning, news impact
│       ├── 08_dashboard_ui/                 # Streamlit & API bridges
│       └── 99_ops_and_maintenance/          # Live Market CI/CD Sentinel & Architecture Ticker Watcher
│           └── live_market_cicd_daemon.py   # Continuous 180s regression & Merkle test runner
│
├── 🛡️ FORENSICS, REPORTS & CERTIFICATIONS (Tier 4)
│   ├── reports/
│   │   ├── audits/                          # IC reconciliation, cost audits, benchmark audits, AST logs
│   │   ├── backtests/                       # Sovereign backtest audits, model hashes, equity curves
│   │   ├── certification/                   # Gate certification reports & G9/G10 formal sign-offs
│   │   ├── charts/                          # High-resolution architectural and performance figures
│   │   ├── final_oos/                       # Out-of-Sample trade logs, equity curves, validation
│   │   ├── gates/                           # Individual results for Gates G0 through G10
│   │   ├── pbo_dsr/                         # Probability of Backtest Overfitting & Deflated Sharpe
│   │   ├── predictions/                     # Production prediction manifests & historical forecasts
│   │   └── LIVE_CICD_STATUS.md              # Real-time automated CI/CD pass/fail status
│   └── tests/                               # Full 264+ pytest institutional regression test suite
│
├── 🖥️ TRADING DESKS & FRONTENDS (Tier 5)
│   ├── apex_wealth/                         # Enterprise PMS, Broker Manager, Blotter, Corporater Grid
│   ├── pulse_terminal/                      # Microsecond Canvas/WebGL streaming tick terminal
│   ├── prism_station/                       # Institutional Prism cross-sectional analytics station
│   └── website codes/                       # 10 Institutional HTML Trading Desks
│
└── 📚 SPECIFICATIONS & GOVERNANCE
    ├── docs/                                # Architecture maps, specifications, engineering logs
    ├── configs/                             # YAML configuration profiles
    ├── README.md                            # Comprehensive system documentation
    ├── SECURITY.md                          # Strix DevSecOps, Bandit SAST & supply chain policy
    └── NEPSE_MASTER_INTEGRATED_OUTPUT.json  # Primary production JSON manifest
```

---

## 🔒 Architectural Rules & Immutability Guarantees

1. **Zero-Copy Ingress**: All incoming trades pass through Core 0-1 shared memory (`/dev/shm/tick_queue`) before hitting storage or WebSockets.
2. **Point-In-Time (PIT) Isolation**: No feature in `03_feature_store/` or model in `scripts/02_modeling_and_calculations/` is allowed to look forward in time.
3. **Cryptographic Merkle Audit**: Every daily batch run and model deployment must append an HMAC-SHA256 hash block into `data/merkle_provenance.chain`.
4. **Single Command Run**: Running `run.bat` automatically sets CPU affinities, boots all daemons, and launches the unified 10-screen master cockpit without window clutter.
