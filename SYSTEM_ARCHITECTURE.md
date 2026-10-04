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
