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

## 2026-09-27: News Harness & Trading Calendar
- Authored `02_nepal_stock_exchange_trading_calendar.py` modeling Bikram Sambat (BS) holidays and NPT trading hours (11:00-15:00).
- Implemented session offset calculator and T+0 trading day resolution.

- Authored `03_duckdb_news_database_connector.py` for structured persistence in `news_and_events.duckdb`.
- Integrated SHA-256 deduplication and verification states for NRB, SEBON, and NEPSE notices.

- Authored `03_classify_news_sentiment_and_topics.py` to extract polarity and subjectivity from announcements.
- Mapped event types into 5 canonical categories (Dividends, Rights, Mergers, Earnings, AGM).

- Authored `01_calculate_event_study_abnormal_returns.py` to compute post-announcement abnormal returns.
- Modeled estimation windows [-90, -1] and event windows [0, +5] to track market reaction.

- Authored `04_run_end_to_end_ml_pipeline.py` uniting disclosures, prices, and event study outcomes.

## 2026-10-02: Live Scrapers & Market Ingestion
- Authored `02_scrape_nepali_financial_news.py` targeting ShareSansar, Merolagani, and Bizpati feeds.
- Added content hashing and duplicate elimination.

- Authored `03_scrape_global_macro_news.py` tracking crude oil, gold, remittance, and interest rate macro signals.

- Authored `05_demo_feature_extraction_examples.py` demonstrating rolling momentum, RSI, and VWAP features.

- Authored `05_load_partitioned_market_data.py` loading multi-year daily CSVs into DuckDB.

## 2026-10-03: Master Orchestration & Stress Testing
- Developed `run_all_pipelines.py` orchestrating raw ingestion, feature creation, and backtesting.

- Authored `08_extreme_bottleneck_stress_test.py` subjecting database to 40+ concurrent workers.
- Exposed concurrency bottlenecks and connection exhaustion patterns.

- Authored `docs/MASTER_SYSTEM_MAP.md` and `docs/RESEARCH_TRACEABILITY.md`.
- Documented all 10 verification gates and artifact lineage.

## 2026-10-04: Live Streaming & CLEF Multimodal Engine
- Authored `06_live_websocket_lakehouse_streamer.py` with auto-reconnecting socket daemon.
- Implemented Hive-partitioned storage: `nepse_lakehouse/year=*/month=*/day=*/*.parquet`.

- Authored `33_clef_inference_bridge.py` combining candlestick vision tokens with textual disclosures.
- Implemented Colab T4 LoRA fine-tuning scripts in `notebooks/35_colab_train_clef_lora.py`.

- Authored `34_build_clef_training_dataset.py` preparing paired chart-image and disclosure training tensors.

## 2026-10-06: Microstructure & Broker Signals
- Authored `08_compute_floorsheet_broker_features.py` computing Buyer/Seller Herfindahl-Hirschman Index (HHI).
- Built top-3 smart money buyer/seller concentration ratios.

- Implemented Hawkes process kernels tracking endogenous trade clustering and retail panic absorption.

