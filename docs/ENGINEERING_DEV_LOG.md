# NEPSE Quantitative Trading & Research Engine — Chronological Dev Log

Full engineering activity chronology verified and maintained by SYZ-FINT.

## 2026-09-09: Project Inception
- Initialized core repository documentation and quantitative research specifications.
- Formulated data lake schema and NEPSE algorithmic trading system requirements.

- Configured `.gitignore` rules for market data caches, DuckDB files, and Parquet outputs.
- Designed directory structure for raw ingestion, processed data, and feature store.

## 2026-09-18: Raw Floorsheet Ingestion Pipeline
- Authored `01_merge_floorsheet_csvs.py` to aggregate raw broker trade records.
- Established schema mapping for legacy transaction numbers, stock symbols, and broker IDs.

- Authored `02_stream_merge_floorsheet_csvs.py` using chunked streaming reads to prevent out-of-memory errors.
- Prepared groundwork for Hive-partitioned tick data lakehouse.

