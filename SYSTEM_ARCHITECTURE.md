# 🏗️ ApexMarketEngine: System Architecture & Dependency Graph

## 1. System Overview & Ingestion Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         APEXMARKETENGINE PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 01_raw / nepse_data_all CSVs                                                │
│      │                                                                      │
│      ▼                                                                      │
│ [scripts/01_build_master_union.py]                                          │
│      │  (DuckDB Deduplication & Schema Standardization)                    │
│      ▼                                                                      │
│ 02_processed_parquet/market_master_union.parquet                           │
│      │  (644,188 rows, 415 tickers, 2003-06-06 to 2026-10-02)                │
│      ▼                                                                      │
│ [scripts/02_feature_engineering.py]                                         │
│      │  (Fractional Diff d=0.35, Lagged Technicals, TextBlob Sentiment)     │
│      ▼                                                                      │
│ 03_feature_store/technical_indicators.parquet                               │
│      │                                                                      │
│      ▼                                                                      │
│ [scripts/17_institutional_ic_audit.py]                                      │
│      │  (Backward Cumulative Multipliers, Rank IC, 100-Permutation Null)     │
│      ▼                                                                      │
│ [scripts/04_streamlit_terminal_ui.py] (Port 8501 Dashboard)                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Inventory & Data Lineage

| Component / File | Purpose & Role | Status / Audit Finding |
| :--- | :--- | :--- |
| `01_raw/ticker_csvs/*.csv` | Master ticker daily OHLCV dumps | 517 CSV files, unadjusted historical data |
| `nepse_data_all/*.csv` | Daily floor sheets (2024–2026) | Expanded ground truth up to Oct 2, 2026 |
| `02_processed_parquet/market_master_union.parquet` | DuckDB unified Parquet store | Clean deduplicated OHLCV dataset |
| `scripts/01_build_master_union.py` | Ingestion script | Validated 0-row loss deduplication |
| `scripts/02_feature_engineering.py` | Feature store generator | FFD ($d=0.35$), TF-IDF, News Sentiment |
| `scripts/03_train_and_backtest.py` | Model training & backtest engine | CPCV Folds, LightGBM Ranker + Meta-Labeler |
| `scripts/15_execute_steps_1_to_6.py` | Diagnostic roadmap script | Isolated $t+0$ same-day close lookahead leak |
| `scripts/17_institutional_ic_audit.py` | Forensic IC & permutation audit | Correct backward adjustment, 100-perm null |
| `config.yaml` | System configuration file | Locked capital, fees, CGT (7.5%), ADV cap (5%) |

---

## 3. Code Hygiene & Dead Code Inventory

1. **Active Pipeline:** `scripts/01_build_master_union.py` $\to$ `scripts/02_feature_engineering.py` $\to$ `scripts/17_institutional_ic_audit.py`.
2. **Dead / Legacy Files:**
   * `scripts/02_modeling_and_calculations/04_run_end_to_end_ml_pipeline.py`: Legacy pipeline using unlagged features and unadjusted prices (DEPRECATED).
   * `scripts/02_modeling_and_calculations/02_backtest_nepse_trading_strategies.py`: Legacy backtester using $t+0$ close fills (DEPRECATED).
3. **Hardcoded Constants:**
   * Legacy scripts hardcoded annual trading days to 365 or 252 instead of NEPSE's ~240 trading days.

---

## 4. Blueprint vs. State Paradigm (Version Control vs. Local Storage)

This framework strictly separates the reproducible logic of the NEPSE terminal (version control) from heavy state and secrets (local storage).

### GitHub: The Blueprint (Code & Configuration)
The remote repository is strictly reserved for lightweight (~851 KB), reproducible application logic. Anyone cloning the repository receives this exact skeleton, ready to be hydrated with data.

| Component | Purpose | Examples in Project |
| :--- | :--- | :--- |
| **Core Architecture** | API frameworks and computation logic | Starlette ASGI routes, Python vectorization engines, model schemas |
| **Data Pipelines** | Scripts that fetch and process data, but not the data itself | Scraper scripts, DuckDB ingestion logic, data reconciliation directives |
| **Configuration** | Dependency locking and Git rules | `requirements.txt`, `.gitignore`, `.gitattributes` |
| **Documentation** | System design and instructions | `README.md`, Mermaid architecture diagrams, `CALCULATIONS_INDEX.md` |

### Local Environment: The State (Data, Secrets & Cache)
The local machine handles heavy data loads, sensitive credentials, and compiled runtime state. These files are excluded via `.gitignore` and never leave the local environment.

| Component | Purpose | Examples in Project |
| :--- | :--- | :--- |
| **Raw Data** | Unprocessed feeds and historical archives | `01_raw/`, `nepse_lakehouse/`, `nepse_data_all/` |
| **Processed Analytics** | Feature stores and vectorized outputs | `03_feature_store/`, `02_processed_parquet/`, DuckDB files (`.duckdb`), large `.json`/`.csv` outputs |
| **Secrets** | API keys, passwords, and environment configurations | `.env` file |
| **Runtime Cache** | Virtual environments and compiled byte code | `.venv/`, `__pycache__/`, `.pyc` files, `.pytest_cache/` |

### The Hydration Workflow
Because the GitHub repository serves as a lightweight blueprint, bridging the gap between Git and local execution relies on automated hydration:
1. Clone the repository and install frozen dependencies (`pip install -r requirements.txt`).
2. Run database initialization (`python scripts/init_duckdb.py`) to create schemas and zero-copy views.
3. Ingest raw market feeds or scrapers to populate `nepse_lakehouse/` and raw directories.
4. Execute the pipeline (`python scripts/run_all_pipelines.py`) to build Parquet stores and feature sets.

