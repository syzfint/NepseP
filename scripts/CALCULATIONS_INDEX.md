# 🧭 ApexMarketEngine — Calculations & Scripts Index

All scripts are executed from the **repository root** (e.g. `python scripts/00_master_integrated_pipeline.py`).

```
scripts/
├── 📄 00_master_integrated_pipeline.py            # [PRODUCTION] 10-Gate Master Integrated Orchestrator (DuckDB + Chronos + G4 Meta-Labeler + T+2 + H_master)
├── 📄 00_organize_workspace.py                    # Workspace Restructuring & Bidirectional Sync Engine
├── 📄 run_all_pipelines.py                        # Legacy Baseline Multi-Stage Runner (Init → Union → Features → Train)
│
├── 📁 01_etl_and_ingestion/                       # DATA INGESTION & FEATURE CONVERGENCE
│   ├── 📄 init_duckdb.py                          # Initializes DuckDB analytics & news databases with zero-copy views
│   ├── 📄 01_build_master_union.py                # Aggregates 719k+ EOD rows into 02_processed_parquet/market_master_union.parquet
│   ├── 📄 01_merge_floorsheet_csvs.py             # Merges individual floorsheet transaction CSVs
│   ├── 📄 02_stream_merge_floorsheet_csvs.py      # Low-memory streaming merger for multi-gigabyte floorsheets
│   ├── 📄 03_export_news_parquet_to_csv.py        # Exports Hive news Parquet datasets to CSV
│   ├── 📄 04_ingest_raw_floorsheet_data.py        # Standardizes raw floorsheet transaction logs
│   ├── 📄 05_load_partitioned_market_data.py      # Fast Parquet loader helper for ML training
│   ├── 📄 06_live_websocket_lakehouse_streamer.py # Real-time WebSocket tick streamer to DuckDB lakehouse
│   └── 📄 08_compute_floorsheet_broker_features.py# Top-20 broker accumulation/distribution & order flow imbalance
│
├── 📁 02_modeling_and_calculations/               # QUANTITATIVE ALPHAS, BACKTESTS & SIMULATORS
│   ├── 📄 02_feature_engineering.py               # Memory-preserving Fractional Differentiation (d=0.35) & technical indicators
│   ├── 📄 03_train_and_backtest.py                # LightGBM cross-sectional ranking & purged CPCV backtester
│   ├── 📄 05_shap_diagnostic_protocol.py          # SHAP feature importance & model attribution diagnostics
│   ├── 📄 06_verify_purged_embargo_split.py       # Validates zero lookahead leakage in purged CPCV splits
│   ├── 📄 20_test_mean_reversion_engine.py        # Baseline mean-reversion factor evaluation
│   ├── 📄 21_calibrated_mean_reversion_engine.py  # Friction-adjusted hysteresis retention alpha (+3,438.94% net)
│   ├── 📄 22_institutional_nepse_backtester.py    # Realistic institutional liquidity, turnover & slippage backtester
│   ├── 📄 26_realistic_nepse_simulator.py         # Order-level fill simulator with 5% ADV bounding & circuit breakers
│   ├── 📄 27_comparative_chronos_g4_backtester.py # Comparative 2024–2026 backtest: Chronos-Bolt G4 vs Naive LightGBM (MDD -9.15% vs -21.64%)
│   ├── 📄 34_full_market_chronos_engine.py        # Full-market Chronos-Bolt zero-shot batch inference (P10, P50, P90 across 5 sessions)
│   └── 📄 01_… 05_ helpers                       # Abnormal returns, NLP sentiment classifier, topic models
│
├── 📁 03_data_access_and_storage/                 # SCHEMAS, API & CALENDAR UTILITIES
│   ├── 📄 01_nepse_market_api_client.py           # NEPSE quote & REST API connector
│   ├── 📄 02_nepal_stock_exchange_trading_calendar.py # Localized Sunday–Thursday NEPSE trading calendar & BS/AD date converter
│   ├── 📄 03_duckdb_news_database_connector.py    # News & macroeconomic DuckDB query helper
│   └── 📄 04_data_schemas_and_pydantic_entities.py# Pydantic v2 strict data schemas for API payloads & manifests
│
├── 📁 04_scrapers_and_harness/                    # CRAWLERS & SCRAPING PIPELINE
│   ├── 📄 01_format_news_feed_for_analysis.py    # Cleans and tokenizes news streams for sentiment modeling
│   ├── 📄 02_scrape_nepali_financial_news.py      # Multi-source scraper (Ekantipur, Kathmandu Post, Nagarik, News24)
│   ├── 📄 03_scrape_global_macro_news.py          # Global macro, commodity & crude oil feed scraper
│   └── 📄 04_harvest_corporate_actions.py         # Bonus, dividend, and right share backward-adjustment crawler
│
├── 📁 05_forensic_audit_gates/ (11_ … 28_)        # FORENSIC AUDIT SUITE & CERTIFICATION (G0–G10)
│   ├── 📄 11_incremental_remediation_suite.py     # Remediation test harness
│   ├── 📄 12_remediation_2010_start.py            # Historical dataset truncation alignment
│   ├── 📄 15_execute_steps_1_to_6.py              # Automated 6-step data repair pipeline
│   ├── 📄 16_remediation_deliverables.py          # Remediation artifact generator
│   ├── 📄 17_institutional_ic_audit.py            # Daily rank information coefficient (IC) verification
│   ├── 📄 18_run_user_modules_audit.py            # Codebase sanity & module compliance test
│   ├── 📄 19_execute_nepse_audit_suite.py         # 10-Gate master audit evaluator
│   ├── 📄 22_generate_baseline_0000.py            # Cold-start baseline generator
│   ├── 📄 23_execute_full_forensic_gates.py       # Gate G0 to G8 verification suite
│   ├── 📄 24_execute_gate_certification_audit.py  # Certification gate runner
│   ├── 📄 25_execute_g9_g10_evaluation.py         # Gate G9 (PBO/DSR) & Gate G10 (Out-of-Sample) evaluation
│   ├── 📄 26_update_master_certification.py       # Updates master certification verdict
│   ├── 📄 27_reconstruct_experiment_registry.py   # Reconstructs trial count registry for PBO calculation
│   └── 📄 28_update_g9_certification.py           # PBO/DSR audit documentation updater
│
├── 📁 06_forecasting_and_charts/ (29_ … 32_)      # DAILY PREDICTION & VISUAL GENERATORS
│   ├── 📄 29_predict_nepse_oct5_2026.py           # Historical Oct 5, 2026 forecast generator
│   ├── 📄 30_generate_oct5_layman_chart.py        # Executive forecast visualization
│   └── 📄 32_generate_nepali_layman_chart.py      # Dual-language Nepali layman contextual visualizer
│
├── 📁 07_clef_multimodal/ (33_ … 35_)             # MULTIMODAL REASONING & LORA ENGINE
│   ├── 📄 33_clef_inference_bridge.py             # Cloudflare tunnel bridge to remote GPU Colab inference
│   ├── 📄 34_build_clef_training_dataset.py       # Builds multimodal vision-language training triplets
│   └── 📄 35_train_clef_lora_t4.py                # LoRA fine-tuning script for Qwen2.5-VL-3B on T4 GPU
│
└── 📁 08_dashboard_ui/                            # TERMINAL & WEB INTERFACES
    └── 📄 04_streamlit_terminal_ui.py             # 3-Tier progressive disclosure Streamlit cockpit
```
