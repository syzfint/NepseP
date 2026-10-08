# NEPSE Quantitative Engine — Engineering Development Log

Chronological engineering activity ledger across active development sprints.

### 2026-10-03 (Session 1)
- Initialized core quantitative backtesting workspace and directory structure.
- Added master pipeline execution runner `run_all_pipelines.py`.
- Defined base data hydration paths and Parquet lakehouse targets.

### 2026-10-03 (Session 2)
- Added `08_extreme_bottleneck_stress_test.py` for DuckDB connection load analysis.
- Added dataset comparison audit script for verifying raw price volumes against verified CSV dumps.

### 2026-10-04 (Session 1)
- Implemented live market tick capture daemon with fault-tolerant reconnect.
- Configured Hive partitioning format `nepse_lakehouse/year=*/month=*/day=*`.
- Added tick buffer queue with batch flush to disk.

### 2026-10-04 (Session 2)
- Replaced legacy row-wise parsers with vectorized Polars and DuckDB expressions.
- Built streaming order book parser to handle fragmented NEPSE payloads.

### 2026-10-06 (Session 1)
- Built `08_compute_floorsheet_broker_features.py` computing broker HHI and dispersion.
- Integrated Hawkes process intensity kernels to model self-exciting order flow clusters.
- Implemented top-3 smart money buyer/seller concentration ratios.

### 2026-10-06 (Session 2)
- Implemented 34 vectorized technical indicators across 720k+ daily bars in `market_master_union.parquet`.
- Computed rolling order flow imbalance (OFI) and volume-weighted average price (VWAP) bounds.

### 2026-10-07 (Session 1)
- Added `34_full_market_chronos_engine.py` for probabilistic zero-shot time series forecasts.
- Generated 5-day quantile predictions (p10, p50, p90) stored in `chronos_quantiles_5d`.
- Integrated asymmetric pinball loss functions for downside volatility penalization.

### 2026-10-07 (Session 2)
- Configured Combinatorial Purged Cross-Validation (CPCV) preventing information leakage.
- Enforced realistic 0.65% institutional round-trip transaction fee drag model.
- Verified equity curve metrics and Deflated Sharpe Ratio (DSR).

### 2026-10-08 (Session 1)
- Developed `pulse_terminal_server.py` and rich terminal UI with live tick ingestion.
- Added sub-second telemetry websockets streaming live LTP, volume, and broker signals.
- Built ANSI color tearsheets and strategy matrix visualizers.

