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

