# Explicit Calculations & Scripts Index

This scripts folder is explicitly named so you know **exactly** what each calculation script does before opening it:

```
scripts/
├── 📁 01_etl_and_ingestion/                                         # DATA MERGING & ETL PIPELINES
│   ├── 📄 01_merge_floorsheet_csvs.py                               # Merges individual daily floorsheet CSVs into a master dataset
│   ├── 📄 02_stream_merge_floorsheet_csvs.py                        # Low-memory streaming merger for massive floorsheet files
│   ├── 📄 03_export_news_parquet_to_csv.py                          # Exports Hive news Parquet datasets into tabular CSVs
│   ├── 📄 04_ingest_raw_floorsheet_data.py                          # Ingests and standardizes raw floorsheet trade transactions
│   ├── 📄 05_load_partitioned_market_data.py                        # High-speed data loader helper for machine learning models
│   └── 📄 06_split_large_zip_archives.py                            # Utility to split massive zip dataset archives
│
├── 📁 02_modeling_and_calculations/                                 # ANALYTICS, EVENT STUDIES & STRATEGIES
│   ├── 📄 01_calculate_event_study_abnormal_returns.py             # Calculates Cumulative Abnormal Returns (CAR) around news events
│   ├── 📄 02_backtest_nepse_trading_strategies.py                   # Quantitative strategy backtest engine & performance simulator
│   ├── 📄 03_classify_news_sentiment_and_topics.py                 # NLP classifier for Nepali news sentiment & topic tags
│   ├── 📄 04_run_end_to_end_ml_pipeline.py                          # Executes full data prep, feature extraction & model scoring
│   └── 📄 05_demo_feature_extraction_examples.py                    # Demonstration examples for extracting financial model features
│
├── 📁 03_data_access_and_storage/                                   # DATABASE, SCHEMAS & CALENDAR UTILITIES
│   ├── 📄 01_nepse_market_api_client.py                             # Market API client for live/historical quote retrieval
│   ├── 📄 02_nepal_stock_exchange_trading_calendar.py               # NEPSE market calendar (holidays, BS/AD date conversion)
│   ├── 📄 03_duckdb_news_database_connector.py                      # DuckDB database connection & SQL query helper
│   └── 📄 04_data_schemas_and_pydantic_entities.py                  # Pydantic data schemas & entity definitions
│
└── 📁 04_scrapers_and_harness/                                      # NEWS CRAWLERS & SCRAPING HARNESS
    ├── 📄 01_format_news_feed_for_analysis.py                      # Formats scraped news stream into structured model feeds
    ├── 📄 02_scrape_nepali_financial_news.py                        # Scrapes Ekantipur, Kathmandu Post, Nagarik & News24
    └── 📄 03_scrape_global_macro_news.py                            # Scrapes global macroeconomic & commodity news feeds
```
