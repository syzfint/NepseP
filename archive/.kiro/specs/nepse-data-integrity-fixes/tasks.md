# Implementation Plan - NEPSE Data Integrity Bugfix

## Phase 1: Bug Condition Exploration Tests

- [x] 1. Write bug condition exploration tests (BEFORE implementing fixes)
  - **Property 1: Bug Condition** - Data Integrity Violations Across Five Subsystems
  - **CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when they fail**
  - **NOTE**: These tests encode the expected behavior - they will validate the fix when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate each of the five bug categories exists
  
  - [x] 1.1 Storage & Concurrency Bug Test
    - **Scoped PBT Approach**: Test 10 concurrent FastAPI requests each creating independent duckdb.connect() calls
    - Create test script `tests/test_bug_storage_concurrency.py`
    - Test that concurrent requests trigger "database is locked" errors or exceed 40 connections
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Test FAILS with DuckDB locking errors or resource exhaustion
    - Document counterexamples (e.g., "Request 7/10 failed with 'database is locked' error")
    - _Requirements: 1.1.1, 1.1.2, 1.1.3, 1.1.4_
  
  - [x] 1.2 Anti-Wash Filter Bypass Bug Test
    - **Scoped PBT Approach**: Test wash trades with schema mismatches (buyerMemberId=sellerMemberId)
    - Create test script `tests/test_bug_anti_wash_bypass.py`
    - Test that wash trades pass through filter when schema columns don't align
    - Verify filter compares NULL != NULL returning false (allowing wash trades)
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Test FAILS - 100% of wash trades incorrectly pass through filter
    - Document counterexamples (e.g., "Trade {buyerMemberId:58, sellerMemberId:58} passed anti-wash filter")
    - _Requirements: 1.2.1, 1.2.4_
  
  - [x] 1.3 Temporal Leakage Bug Test
    - **Scoped PBT Approach**: Test that training data contains same-day broker concentration features
    - Create test script `tests/test_bug_temporal_leakage.py`
    - Query training data and verify future information exists in same-day joins
    - Test SQL joins using `ON date = date` leak future broker concentration
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Test FAILS - training data contains same-day institutional features
    - Document counterexamples (e.g., "Date 2024-06-15: price row joined with broker data from same date")
    - _Requirements: 1.3.1, 1.3.2_
  
  - [x] 1.4 Ghost Features Bug Test
    - **Scoped PBT Approach**: Test that declared features have no computation implementation
    - Create test script `tests/test_bug_ghost_features.py`
    - Load feature store and verify 5 features (frac_diff_close, macd_norm, rsi_14, log_return, range_vol) are 100% zeros
    - Test that .fillna(0.0) masks missing feature computation
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Test FAILS - 5 features show 100% zero values across all historical rows
    - Document counterexamples (e.g., "frac_diff_close: 15,847 rows all zero-filled")
    - _Requirements: 1.4.1, 1.4.2, 1.4.4_
  
  - [x] 1.5 Optimizer Failure Bug Test
    - **Scoped PBT Approach**: Force scipy.optimize.minimize to fail and verify system uses invalid parameters
    - Create test script `tests/test_bug_optimizer_failure.py`
    - Simulate optimization failure (res.success = False with 1e9 penalty)
    - Test that system consumes 1e9 as valid Hawkes parameter
    - Test that zero volatility creates profit_barrier = 0.0
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Test FAILS - system crashes or uses penalty value 1e9 as valid parameter
    - Document counterexamples (e.g., "Hawkes branching ratio = 1e9/1e9 = 1.0 for quiet stock")
    - _Requirements: 1.5.1, 1.5.3_

## Phase 2: Preservation Property Tests

- [x] 2. Write preservation property tests (BEFORE implementing fixes)
  - **Property 2: Preservation** - Non-Buggy Operations Remain Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs (cases where isBugCondition returns false)
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  
  - [x] 2.1 Storage Preservation Test
    - **Observation**: Run single-threaded batch job on unfixed code
    - Observe: Sequential DuckDB queries execute successfully with current SQL syntax
    - Observe: Single Parquet writes complete without corruption
    - Write property-based test: For all sequential single-connection operations, results match baseline
    - Create test script `tests/test_preserve_storage.py`
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
    - _Requirements: 3.1.1, 3.1.2, 3.1.3_
  
  - [x] 2.2 Ingestion Preservation Test
    - **Observation**: Run legitimate cross-broker trades on unfixed code
    - Observe: Complete API payloads with valid buyer_id != seller_id pass anti-wash filter
    - Observe: Trades with proper schema and timestamps store correctly
    - Write property-based test: For all valid cross-broker trades, anti-wash filter passes and data stores correctly
    - Create test script `tests/test_preserve_ingestion.py`
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
    - _Requirements: 3.2.1, 3.2.2, 3.2.3_
  
  - [x] 2.3 Temporal Preservation Test
    - **Observation**: Run multi-day lag feature calculations on unfixed code
    - Observe: 5-day moving averages, 20-day volatility calculate correctly
    - Observe: Historical backtesting on properly lagged data produces accurate metrics
    - Write property-based test: For all multi-day lag features, calculations match baseline
    - Create test script `tests/test_preserve_temporal.py`
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
    - _Requirements: 3.3.1, 3.3.2, 3.3.3_
  
  - [x] 2.4 Feature Store Preservation Test
    - **Observation**: Run existing 6 feature computations on unfixed code
    - Observe: volume_zscore_20, kline_body_density, amihud_illiquidity produce correct values
    - Observe: Legitimate NULL handling for edge cases (first-day IPO) works correctly
    - Write property-based test: For all 6 existing features, calculations match baseline
    - Create test script `tests/test_preserve_features.py`
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
    - _Requirements: 3.4.1, 3.4.2, 3.4.3_
  
  - [x] 2.5 Model Governance Preservation Test
    - **Observation**: Run successful Hawkes optimization on unfixed code
    - Observe: scipy.optimize.minimize with res.success=True uses optimized parameters correctly
    - Observe: Chronos-Bolt models executing successfully produce predictions without fallback
    - Observe: Scrips with sufficient volatility generate accurate Triple-Barrier labels
    - Write property-based test: For all successful optimization cases, behavior matches baseline
    - Create test script `tests/test_preserve_model_governance.py`
    - Run on UNFIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
    - _Requirements: 3.5.1, 3.5.2, 3.5.3, 3.5.4, 3.5.5_

## Phase 3: Implementation - Fix 1: Storage & Concurrency Architecture

- [x] 3. Implement centralized DuckDB connection management and async execution

  - [x] 3.1 Create DuckDB Connection Manager
    - Create file `scripts/03_data_access_and_storage/duckdb_connection_manager.py`
    - Implement `DuckDBConnectionManager` singleton class with thread-safe connection pool
    - Maximum 5-10 connections with `threading.Lock()` for concurrency control
    - Implement context manager protocol (`__enter__`, `__exit__`) for automatic cleanup
    - Add connection lifecycle management (acquire, release, health checks)
    - Add connection pool monitoring and metrics (active connections, wait times)
    - _Bug_Condition: isBugCondition(input) where input.concurrent_requests > 3 AND duckdb_connections >= 40_
    - _Expected_Behavior: Connection pool reuses 5-10 connections with zero locking conflicts_
    - _Preservation: Single-threaded batch jobs continue to execute queries successfully_
    - _Requirements: 2.1.1_

  - [x] 3.2 Create Async DuckDB Executor
    - Create file `scripts/03_data_access_and_storage/async_duckdb_executor.py`
    - Implement `AsyncDuckDBExecutor` using `ThreadPoolExecutor` (max_workers=4)
    - Wrap CPU-bound operations in `asyncio.to_thread()` for event loop compatibility
    - Pattern: `result = await executor.execute_query(sql, params)`
    - Add query timeout handling and error propagation
    - _Bug_Condition: isBugCondition(input) where Pandas/Matplotlib operations block event loop_
    - _Expected_Behavior: Operations offloaded to thread pool, event loop remains responsive_
    - _Preservation: Lightweight synchronous operations continue with sub-100ms latency_
    - _Requirements: 2.1.2, 2.1.4_

  - [x] 3.3 Implement Atomic Parquet Write Operations
    - Add `atomic_parquet_write()` helper function to `async_duckdb_executor.py`
    - Write to `.tmp` staging file first using `df.to_parquet(tmp_path)`
    - Atomic rename using `Path.rename()` (POSIX atomic operation)
    - Pattern: `tmp_path = target_path.with_suffix('.tmp'); tmp_path.rename(target_path)`
    - Add error handling and cleanup for failed writes
    - _Bug_Condition: isBugCondition(input) where parquet_write_in_progress AND concurrent_read_attempted_
    - _Expected_Behavior: Atomic rename prevents file corruption during concurrent reads_
    - _Preservation: Sequential Parquet writes continue to produce valid files_
    - _Requirements: 2.1.3_

  - [x] 3.4 Replace duckdb.connect() calls in ETL modules
    - Modify `scripts/01_etl_and_ingestion/init_duckdb.py`
    - Modify `scripts/01_etl_and_ingestion/duckdb_lakehouse_loader.py`
    - Modify `scripts/01_etl_and_ingestion/08_compute_floorsheet_broker_features.py`
    - Replace all `duckdb.connect()` with `with connection_manager.acquire() as conn:`
    - Add import: `from scripts.03_data_access_and_storage.duckdb_connection_manager import connection_manager`
    - Verify queries execute successfully with pooled connections
    - _Bug_Condition: Multiple independent connections causing resource exhaustion_
    - _Expected_Behavior: All ETL modules reuse pooled connections_
    - _Preservation: Existing SQL syntax and query logic unchanged_
    - _Requirements: 2.1.1_

  - [x] 3.5 Replace duckdb.connect() calls in feature engineering
    - Modify `scripts/02_feature_engineering.py`
    - Replace all `duckdb.connect()` with `with connection_manager.acquire() as conn:`
    - Ensure feature computation queries use pooled connections
    - Verify feature calculation results remain identical
    - _Bug_Condition: Feature engineering creating independent connections_
    - _Expected_Behavior: Feature engineering reuses pooled connections_
    - _Preservation: Feature calculation logic and results unchanged_
    - _Requirements: 2.1.1_

  - [x] 3.6 Replace duckdb.connect() calls in model training
    - Modify `scripts/03_train_and_backtest.py`
    - Replace all `duckdb.connect()` with `with connection_manager.acquire() as conn:`
    - Ensure training data queries use pooled connections
    - Verify training data extraction remains identical
    - _Bug_Condition: Training pipeline creating independent connections_
    - _Expected_Behavior: Training pipeline reuses pooled connections_
    - _Preservation: Training data queries and model training unchanged_
    - _Requirements: 2.1.1_

  - [x] 3.7 Integrate async executor with FastAPI routes
    - Modify `scripts/pulse_terminal_server.py`
    - Import `AsyncDuckDBExecutor` and create global instance
    - Wrap CPU-bound operations (Pandas, Matplotlib) in `await executor.execute()`
    - Replace blocking `duckdb.connect()` calls with async queries
    - Add request timeout handling (30 seconds default)
    - Test concurrent request handling (10+ simultaneous requests)
    - _Bug_Condition: FastAPI async handlers blocking event loop with synchronous operations_
    - _Expected_Behavior: All CPU-bound operations offloaded, event loop responsive_
    - _Preservation: API response schemas and data unchanged_
    - _Requirements: 2.1.2, 2.1.4_

  - [x] 3.8 Replace remaining duckdb.connect() calls across codebase
    - Search for all remaining `duckdb.connect()` calls using grep
    - Identify files: ingestion connectors, utility scripts, analysis notebooks
    - Replace all instances with pooled connection pattern
    - Verify all modules can access connection manager
    - Document any exceptions requiring direct connections (if any)
    - _Bug_Condition: Any remaining independent connection creation_
    - _Expected_Behavior: Zero independent connections, all use pool_
    - _Preservation: All existing functionality preserved_
    - _Requirements: 2.1.1_

## Phase 4: Implementation - Fix 2: Ingestion & Anti-Wash Gate Architecture

- [x] 4. Implement schema canonicalization and strict anti-wash filtering

  - [x] 4.1 Create Schema Canonicalization Module
    - Create file `scripts/01_etl_and_ingestion/schema_canonicalization.py`
    - Implement `canonicalize_trade_schema(df: pd.DataFrame) -> pd.DataFrame`
    - Define canonical column mappings:
      ```
      CANONICAL_SCHEMA = {
        'buyerMemberId': 'buyer_broker_id',
        'Buyer': 'buyer_broker_id',
        'sellerMemberId': 'seller_broker_id',
        'Seller': 'seller_broker_id',
        'Quantity': 'quantity',
        'Rate': 'price',
        'Amount': 'amount'
      }
      ```
    - Apply mapping with fallback to original names if not in mapping
    - Add validation logging for applied transformations
    - _Bug_Condition: isBugCondition(input) where api_payload.has_broker_ids AND NOT schema_canonicalized_
    - _Expected_Behavior: All column names mapped to canonical schema before processing_
    - _Preservation: Trades with correct schema continue to process normally_
    - _Requirements: 2.2.1_

  - [x] 4.2 Implement Strict Anti-Wash Filter
    - Modify `scripts/01_etl_and_ingestion/08_compute_floorsheet_broker_features.py`
    - Add schema canonicalization call before anti-wash filter: `df = canonicalize_trade_schema(df)`
    - Replace SQL filter: `(CAST(Buyer AS VARCHAR) = CAST(Seller AS VARCHAR))`
    - With: `(buyer_broker_id = seller_broker_id)` after canonicalization
    - Add assertion: `assert 'buyer_broker_id' in df.columns and 'seller_broker_id' in df.columns`
    - Add explicit logging for rejected wash trades
    - _Bug_Condition: isBugCondition(input) where schema mismatch causes NULL != NULL evaluations_
    - _Expected_Behavior: Anti-wash filter rejects all trades where buyer_broker_id == seller_broker_id_
    - _Preservation: Legitimate cross-broker trades continue to pass filter_
    - _Requirements: 2.2.1, 2.2.4_

  - [x] 4.3 Implement Fail-Fast Payload Validation
    - Add function `validate_trade_payload(payload: Dict) -> Result` to schema_canonicalization.py
    - Define required fields: `['buyer_broker_id', 'seller_broker_id', 'timestamp', 'quantity', 'price']`
    - Check for missing fields and reject with explicit error logging
    - Remove synthetic broker ID generation fallback `(contract_id % 50) + 1`
    - Remove wallclock timestamp substitution fallback
    - Return rejection status with detailed error message
    - _Bug_Condition: isBugCondition(input) where api_payload.broker_ids_incomplete AND synthetic_ids_generated_
    - _Expected_Behavior: Incomplete payloads rejected with explicit logging, no synthetic data_
    - _Preservation: Complete API payloads continue to process successfully_
    - _Requirements: 2.2.2, 2.2.3_

  - [x] 4.4 Create Dead-Letter Queue for Rejected Trades
    - Create directory `01_raw_data/rejected_trades/` if not exists
    - Implement `log_rejected_trade(payload: Dict, reason: str)` function
    - Write rejected trades to `01_raw_data/rejected_trades/{date}_rejected.parquet`
    - Include fields: timestamp, rejection_reason, full_payload_json
    - Add daily rotation for rejected trade files
    - Enable forensic analysis without data loss
    - _Bug_Condition: Rejected trades lost without audit trail_
    - _Expected_Behavior: All rejected trades logged to dead-letter queue with reason_
    - _Preservation: Accepted trades continue normal processing flow_
    - _Requirements: 2.2.2, 2.2.3_

  - [x] 4.5 Integrate Canonicalization with API Ingestion
    - Modify `scripts/01_etl_and_ingestion/update_today_eod_lakehouse.py`
    - Add schema canonicalization call at ingestion entry point
    - Apply validation before any downstream processing
    - Integrate dead-letter queue logging for rejections
    - Add metrics collection (acceptance rate, rejection reasons)
    - _Bug_Condition: API ingestion bypassing schema validation_
    - _Expected_Behavior: All API ingestion flows validated and canonicalized_
    - _Preservation: Valid API data continues to flow through pipeline_
    - _Requirements: 2.2.1, 2.2.2, 2.2.3_

  - [x] 4.6 Integrate Canonicalization with NEPSE Connectors
    - Modify NEPSE ingestion connectors (if separate from update_today_eod_lakehouse.py)
    - Apply schema canonicalization to all NEPSE API response data
    - Add payload validation before storage
    - Log rejected payloads to dead-letter queue
    - Verify floorsheet data passes through canonicalization
    - _Bug_Condition: NEPSE connectors bypassing validation_
    - _Expected_Behavior: All NEPSE data validated and canonicalized_
    - _Preservation: Valid NEPSE data continues to process_
    - _Requirements: 2.2.1, 2.2.4_

## Phase 5: Implementation - Fix 3: Temporal Integrity Enforcement

- [x] 5. Implement mandatory temporal lag enforcement and contamination detection

  - [x] 5.1 Enforce 1-Session Lag in Feature Engineering SQL
    - Modify `scripts/02_feature_engineering.py`
    - Locate broker concentration join in `run_feature_engineering()` function
    - Replace same-day join: `ON e.ticker = f.ticker AND e.date = CAST(f.date AS DATE)`
    - With lagged join: `ON e.ticker = f.ticker AND e.date = CAST(f.date AS DATE) + INTERVAL 1 DAY`
    - Add SQL comment: `-- Temporal Safety: 1-session lag enforced to prevent future information leakage`
    - Verify join results contain only lagged broker features
    - _Bug_Condition: isBugCondition(input) where join_queries.contains_same_day_joins AND NOT lagged_
    - _Expected_Behavior: All broker concentration features lagged by 1 session_
    - _Preservation: Multi-day lag features (5-day MA, 20-day vol) continue correctly_
    - _Requirements: 2.3.1_

  - [x] 5.2 Create Temporal Validator Module
    - Create file `scripts/03_data_access_and_storage/temporal_validator.py`
    - Implement `validate_temporal_joins(df: pd.DataFrame, feature_cols: List[str]) -> Result`
    - Check for same-day contamination by verifying feature date < price date
    - Implement `detect_same_day_contamination(df)` to scan for temporal violations
    - Raise `TemporalContaminationError` if same-day features detected
    - Add logging for validation results
    - _Bug_Condition: Training data containing same-day features_
    - _Expected_Behavior: Validation detects and rejects contaminated training data_
    - _Preservation: Properly lagged data passes validation_
    - _Requirements: 2.3.2_

  - [x] 5.3 Implement Column Name Alignment Verification
    - Add function `verify_column_alignment(storage_schema, scoring_schema) -> Result` to temporal_validator.py
    - Assert column names match across feature store Parquet files:
      - `03_feature_store/technical_indicators.parquet`
      - `03_feature_store/floorsheet_broker_signals.parquet`
    - Compare against model training DataFrame columns
    - Raise `ColumnMismatchError` on alignment failure with detailed mismatch report
    - Log successful alignment verification
    - _Bug_Condition: Column name misalignments causing silent feature mismatches_
    - _Expected_Behavior: Strict alignment verified before training_
    - _Preservation: Correctly aligned columns continue to work_
    - _Requirements: 2.3.3_

  - [x] 5.4 Integrate Temporal Validation in Training Pipeline
    - Modify `scripts/03_train_and_backtest.py`
    - Import temporal validator: `from scripts.03_data_access_and_storage.temporal_validator import validate_temporal_joins, verify_column_alignment`
    - Add validation step after training data construction:
      ```
      validate_temporal_joins(df_train, LAGGED_FEATURES)
      verify_column_alignment(storage_cols, df_train.columns)
      ```
    - Define LAGGED_FEATURES list (all broker concentration features)
    - Halt training on validation failure with detailed error message
    - _Bug_Condition: Training pipeline using contaminated data_
    - _Expected_Behavior: Training halts if temporal violations detected_
    - _Preservation: Clean training data continues to train models_
    - _Requirements: 2.3.2, 2.3.3_

  - [x] 5.5 Add Temporal Validation to Backtesting
    - In `scripts/03_train_and_backtest.py`, add validation to backtest data
    - Apply `validate_temporal_joins()` to backtest folds before evaluation
    - Verify no forward-looking bias in backtest data
    - Add assertion: all features in backtest data properly lagged
    - Log validation results for each backtest fold
    - _Bug_Condition: Backtest data containing future information_
    - _Expected_Behavior: Backtest validation catches temporal contamination_
    - _Preservation: Clean backtest data continues to evaluate correctly_
    - _Requirements: 2.3.2_

  - [x] 5.6 Create Temporal Integrity Test Suite
    - Create test file `tests/test_temporal_integrity.py`
    - Test 1: Verify 1-session lag in SQL joins (query and inspect results)
    - Test 2: Verify validate_temporal_joins() detects contamination
    - Test 3: Verify column alignment detection works
    - Test 4: Verify training pipeline rejects contaminated data
    - Test 5: Verify multi-day lag features still calculate correctly
    - Run full test suite to confirm temporal safety
    - _Bug_Condition: Temporal integrity not validated_
    - _Expected_Behavior: Comprehensive test coverage confirms temporal correctness_
    - _Preservation: Existing valid temporal logic verified_
    - _Requirements: 2.3.1, 2.3.2, 2.3.3_

## Phase 6: Implementation - Fix 4: Feature Computation Pipeline

- [x] 6. Implement explicit computation for ghost features with Pandera validation

  - [x] 6.1 Implement frac_diff_close Feature (d=0.35)
    - Modify `scripts/02_feature_engineering.py`
    - Add dependency: `from fracdiff import fdiff`
    - Implement fractional differencing:
      ```python
      df['frac_diff_close'] = df.groupby('ticker')['close'].transform(
          lambda x: fdiff(x, d=0.35)
      )
      ```
    - Handle edge cases: first N rows where computation impossible (mark as NaN, forward-fill)
    - Add logging: `logger.info(f"Computed frac_diff_close: mean={df['frac_diff_close'].mean():.4f}")`
    - Verify non-zero values across historical data
    - _Bug_Condition: isBugCondition(input) where feature_set.declared_features != computed_features_
    - _Expected_Behavior: frac_diff_close computed for all tickers with d=0.35_
    - _Preservation: Other fractional diff features (if any) continue to work_
    - _Requirements: 2.4.1_

  - [x] 6.2 Implement macd_norm Feature (Normalized MACD)
    - In `scripts/02_feature_engineering.py`, add MACD computation
    - Calculate EMA-12 and EMA-26:
      ```python
      ema_12 = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=12).mean())
      ema_26 = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=26).mean())
      macd = ema_12 - ema_26
      signal = macd.ewm(span=9).mean()
      df['macd_norm'] = (macd - signal) / (df['close'] + 1e-6)
      ```
    - Handle division by zero with epsilon
    - Add logging: `logger.info(f"Computed macd_norm: mean={df['macd_norm'].mean():.4f}")`
    - Verify non-zero values and reasonable ranges
    - _Bug_Condition: macd_norm declared but not computed_
    - _Expected_Behavior: macd_norm computed as normalized MACD histogram_
    - _Preservation: Other MACD-based features (if any) continue to work_
    - _Requirements: 2.4.1_

  - [x] 6.3 Implement rsi_14 Feature (RSI with Wilder's Smoothing)
    - In `scripts/02_feature_engineering.py`, add RSI computation
    - Calculate Relative Strength Index:
      ```python
      delta = df.groupby('ticker')['close'].diff()
      gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
      loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
      rs = gain / (loss + 1e-8)
      df['rsi_14'] = 100 - (100 / (1 + rs))
      ```
    - Ensure RSI values in range [0, 100]
    - Add logging: `logger.info(f"Computed rsi_14: mean={df['rsi_14'].mean():.2f}, min={df['rsi_14'].min():.2f}, max={df['rsi_14'].max():.2f}")`
    - Verify non-zero values and valid range
    - _Bug_Condition: rsi_14 declared but not computed_
    - _Expected_Behavior: rsi_14 computed with Wilder's smoothing, values in [0,100]_
    - _Preservation: Other RSI-based features (if any) continue to work_
    - _Requirements: 2.4.1_

  - [x] 6.4 Implement log_return Feature (Log Returns)
    - In `scripts/02_feature_engineering.py`, add log returns computation
    - Calculate natural log returns:
      ```python
      df['log_return'] = df.groupby('ticker')['close'].transform(
          lambda x: np.log(x / x.shift(1))
      )
      ```
    - Handle first row (NaN) appropriately
    - Add logging: `logger.info(f"Computed log_return: mean={df['log_return'].mean():.6f}, std={df['log_return'].std():.6f}")`
    - Verify non-zero values and realistic magnitude
    - _Bug_Condition: log_return declared but not computed_
    - _Expected_Behavior: log_return computed as ln(price_t / price_t-1)_
    - _Preservation: Other return features continue to work_
    - _Requirements: 2.4.1_

  - [x] 6.5 Implement range_vol Feature (Range-Based Volatility)
    - In `scripts/02_feature_engineering.py`, add range volatility computation
    - Calculate range-based volatility:
      ```python
      df['daily_range'] = (df['high'] - df['low']) / (df['close'] + 1e-6)
      df['range_vol'] = df.groupby('ticker')['daily_range'].transform(
          lambda x: x.rolling(20).std()
      )
      ```
    - Ensure non-negative values
    - Add logging: `logger.info(f"Computed range_vol: mean={df['range_vol'].mean():.6f}, std={df['range_vol'].std():.6f}")`
    - Verify non-zero values across historical data
    - _Bug_Condition: range_vol declared but not computed_
    - _Expected_Behavior: range_vol computed as 20-period rolling std of daily ranges_
    - _Preservation: Other volatility features continue to work_
    - _Requirements: 2.4.1_

  - [x] 6.6 Add Pandera Dependency and Define Schema
    - Add `pandera>=0.20.0` to `requirements.txt`
    - In `scripts/02_feature_engineering.py`, add import: `import pandera as pa`
    - Define feature schema:
      ```python
      FEATURE_SCHEMA = pa.DataFrameSchema({
          'frac_diff_close': pa.Column(float, nullable=False),
          'macd_norm': pa.Column(float, nullable=False),
          'rsi_14': pa.Column(float, pa.Check.in_range(0, 100), nullable=False),
          'log_return': pa.Column(float, nullable=False),
          'range_vol': pa.Column(float, pa.Check.greater_than_or_equal_to(0), nullable=False),
          # Add existing 6 features
          'volume_zscore_20': pa.Column(float, nullable=False),
          'kline_body_density': pa.Column(float, nullable=False),
          'amihud_illiquidity': pa.Column(float, nullable=False),
          'top_buyer_concentration': pa.Column(float, nullable=False),
          'buyer_hhi': pa.Column(float, nullable=False),
          'broker_net_imbalance': pa.Column(float, nullable=False)
      })
      ```
    - _Bug_Condition: No runtime validation of feature completeness_
    - _Expected_Behavior: Pandera schema defined for all 11 features_
    - _Preservation: Existing features included in schema_
    - _Requirements: 2.4.2_

  - [x] 6.7 Replace .fillna(0.0) with Pandera Validation
    - In `scripts/02_feature_engineering.py`, locate all `.fillna(0.0)` calls
    - Remove silent zero-filling for feature columns
    - Add Pandera validation after feature computation:
      ```python
      try:
          df_validated = FEATURE_SCHEMA.validate(df[FEATURE_SCHEMA.columns])
      except pa.errors.SchemaError as e:
          logger.error(f"Feature validation failed: {e}")
          logger.error(f"Failure cases: {e.failure_cases}")
          raise FeatureComputationError(f"Missing or invalid features: {e.failure_cases}")
      ```
    - Define custom exception: `class FeatureComputationError(Exception): pass`
    - Test validation with incomplete features (should raise exception)
    - _Bug_Condition: isBugCondition(input) where .fillna(0.0) masks failures_
    - _Expected_Behavior: Pandera raises exceptions on validation failures instead of silent fills_
    - _Preservation: Valid features pass validation without error_
    - _Requirements: 2.4.2_

  - [x] 6.8 Implement Feature Completeness Validation in Training
    - Modify `scripts/03_train_and_backtest.py`
    - Define required features list:
      ```python
      REQUIRED_FEATURES = [
          'frac_diff_close', 'macd_norm', 'rsi_14', 'log_return', 'range_vol',
          'volume_zscore_20', 'kline_body_density', 'amihud_illiquidity',
          'top_buyer_concentration', 'buyer_hhi', 'broker_net_imbalance'
      ]
      ```
    - Add pre-training validation:
      ```python
      def validate_feature_completeness(df):
          missing = set(REQUIRED_FEATURES) - set(df.columns)
          if missing:
              raise FeatureValidationError(f"Missing features: {missing}")
          
          # Check for zero-filled ghost features
          for feat in REQUIRED_FEATURES:
              zero_pct = (df[feat] == 0.0).mean()
              if zero_pct > 0.95:
                  logger.warning(f"Feature {feat} is {zero_pct*100:.1f}% zeros - possible ghost feature")
      ```
    - Call before model training: `validate_feature_completeness(df_train)`
    - _Bug_Condition: isBugCondition(input) where models train on incomplete features_
    - _Expected_Behavior: Training halts if any feature missing or 95%+ zeros_
    - _Preservation: Training with complete features continues normally_
    - _Requirements: 2.4.3_

  - [x] 6.9 Add Feature Computation Logging
    - In `scripts/02_feature_engineering.py`, add explicit logging after each feature computation
    - Log summary statistics for verification:
      ```python
      logger.info("Feature Computation Summary:")
      logger.info(f"  frac_diff_close: mean={df['frac_diff_close'].mean():.4f}, std={df['frac_diff_close'].std():.4f}, non_zero={((df['frac_diff_close'] != 0).sum() / len(df) * 100):.1f}%")
      # ... repeat for all 11 features
      ```
    - Log warnings for suspicious patterns (too many zeros, invalid ranges)
    - Save feature computation report to `03_feature_store/feature_computation_report.txt`
    - _Bug_Condition: Silent feature computation failures_
    - _Expected_Behavior: Explicit logging confirms successful computation_
    - _Preservation: Existing logging continues_
    - _Requirements: 2.4.4_

  - [x] 6.10 Create Feature Computation Test Suite
    - Create test file `tests/test_feature_computation.py`
    - Test each feature individually with known inputs/outputs
    - Test Pandera validation catches missing features
    - Test feature completeness validation in training
    - Test that zero-filling detection works (95% threshold)
    - Verify all 11 features compute correctly on sample data
    - _Bug_Condition: Feature computation not tested_
    - _Expected_Behavior: Comprehensive tests verify all features_
    - _Preservation: Existing feature tests continue_
    - _Requirements: 2.4.1, 2.4.2, 2.4.3_

## Phase 7: Implementation - Fix 5: Model Governance Framework

- [x] 7. Implement optimizer validation, volatility floors, and model status tracking

  - [x] 7.1 Add Optimizer Success Validation in Hawkes MLE
    - Modify `scripts/02_modeling_and_calculations/hawkes_broker_cascade.py`
    - Locate `fit()` method with `scipy.optimize.minimize` call
    - Add success validation after optimization:
      ```python
      res = minimize(
          self._neg_log_likelihood,
          init_params,
          args=(ts_rel, T),
          method="L-BFGS-B",
          bounds=bounds
      )
      
      # NEW: Explicit success validation
      if not res.success:
          logger.warning(f"Hawkes MLE optimization failed for ticker {ticker}: {res.message}")
          logger.warning(f"Falling back to safe defaults")
          return HawkesParameters(
              mu=0.01, alpha=0.0, beta=1.0, branching_ratio=0.0,
              log_likelihood=0.0, is_supercritical=False, 
              cascade_hazard_score=0.0, regime='OPTIMIZER_FAILED'
          )
      
      # Only use optimized parameters if successful
      mu, alpha, beta = res.x
      ```
    - _Bug_Condition: isBugCondition(input) where scipy_optimize_result.success == False AND params_used_anyway_
    - _Expected_Behavior: Assert res.success == True, fallback to safe defaults on failure_
    - _Preservation: Successful optimizations continue to use optimized parameters_
    - _Requirements: 2.5.1_

  - [x] 7.2 Define Safe Default Hawkes Parameters
    - In `hawkes_broker_cascade.py`, define module-level constants:
      ```python
      SAFE_HAWKES_DEFAULTS = {
          'mu': 0.01,      # Minimal background rate
          'alpha': 0.0,    # No excitation (no cascade effect)
          'beta': 1.0,     # Standard decay rate
          'branching_ratio': 0.0,  # Subcritical regime
          'regime': 'OPTIMIZER_FAILED'
      }
      ```
    - Document the rationale for each default value
    - Add unit test verifying safe defaults produce stable predictions
    - _Bug_Condition: No defined safe defaults for optimizer failures_
    - _Expected_Behavior: Explicit safe defaults defined and documented_
    - _Preservation: Successful optimizations unaffected_
    - _Requirements: 2.5.1_

  - [x] 7.3 Implement Volatility Floor Enforcement in Triple-Barrier Labeling
    - Modify `scripts/03_train_and_backtest.py`
    - Locate Triple-Barrier labeling code (profit_barrier calculation)
    - Replace: `df["profit_barrier"] = df["volatility_20"] * 2.0`
    - With volatility floor enforcement:
      ```python
      MIN_VOLATILITY_FLOOR = 0.01  # 1% minimum
      df["effective_volatility"] = df["volatility_20"].clip(lower=MIN_VOLATILITY_FLOOR)
      df["profit_barrier"] = df["effective_volatility"] * 2.0
      
      # Verify no zero barriers
      assert (df["profit_barrier"] > 0).all(), "Zero profit barriers detected after floor enforcement"
      ```
    - Add logging: `logger.info(f"Applied volatility floor: {(df['volatility_20'] < MIN_VOLATILITY_FLOOR).sum()} scrips floored")`
    - _Bug_Condition: isBugCondition(input) where triple_barrier_volatility == 0.0 AND profit_barrier == 0.0_
    - _Expected_Behavior: profit_barrier = max(volatility, 0.01) * 2.0 enforces minimum floor_
    - _Preservation: Scrips with sufficient volatility continue with original barriers_
    - _Requirements: 2.5.3_

  - [x] 7.4 Add Explicit Alerts for Model Fallback
    - Create module `scripts/02_modeling_and_calculations/model_alerts.py`
    - Implement alert functions:
      ```python
      def alert_optimizer_failure(ticker: str, error_msg: str):
          logger.error(f"[ALERT] Hawkes optimizer failed for {ticker}: {error_msg}")
          # Future: integrate with monitoring system (Slack, PagerDuty, etc.)
      
      def alert_model_fallback(ticker: str, primary_model: str, fallback_model: str):
          logger.warning(f"[ALERT] Model fallback for {ticker}: {primary_model} → {fallback_model}")
      ```
    - Call alerts in appropriate failure points
    - Add alert aggregation (don't spam on every failure)
    - _Bug_Condition: isBugCondition(input) where silent downgrade to GBM fallback occurs_
    - _Expected_Behavior: Explicit alerts fire on optimizer failure or model fallback_
    - _Preservation: Successful predictions continue without alerts_
    - _Requirements: 2.5.2_

  - [x] 7.5 Implement Model Status Metadata Tagging
    - Modify all prediction output generators across codebase
    - Add status metadata to prediction outputs:
      ```python
      prediction_output = {
          'symbol': symbol,
          'prediction': pred_value,
          'model_status': 'LIVE_CHRONOS',  # or 'GBM_FALLBACK', 'OPTIMIZER_FAILED'
          'model_version': 'chronos-bolt-v1.0',
          'fallback_reason': None,  # or error message
          'timestamp': datetime.now(timezone.utc).isoformat(),
          'hawkes_regime': hawkes_params.regime  # or 'OPTIMIZER_FAILED'
      }
      ```
    - Ensure all prediction outputs include status metadata
    - Add logging: `logger.info(f"Prediction for {symbol}: model_status={prediction_output['model_status']}")`
    - _Bug_Condition: isBugCondition(input) where no metadata distinguishes LIVE_CHRONOS vs GBM_FALLBACK_
    - _Expected_Behavior: All predictions include explicit model_status metadata_
    - _Preservation: Prediction values and schemas remain backward compatible_
    - _Requirements: 2.5.5_

  - [x] 7.6 Refit Isolation Forest on Historical Distributions
    - Locate Isolation Forest training code in model governance modules
    - Replace dynamic test batch fitting with historical clean data:
      ```python
      # OLD: iso_forest.fit(test_batch_features)
      
      # NEW: Fit on clean historical training distribution
      historical_clean_data = load_historical_features(
          start_date='2023-01-01',
          end_date='2024-12-31',
          filters={'wash_trade_ratio': '<0.05', 'data_quality': 'VERIFIED'}
      )
      
      anomaly_features = ['log_return', 'volume_zscore_20', 'broker_net_imbalance', 'range_vol']
      iso_forest.fit(historical_clean_data[anomaly_features])
      
      # Save fitted model for production use
      joblib.dump(iso_forest, 'models/isolation_forest_historical_fit.pkl')
      logger.info(f"Isolation Forest fitted on {len(historical_clean_data)} historical samples")
      ```
    - Define historical data quality filters
    - Add validation: verify fitted model detects known anomalies
    - _Bug_Condition: isBugCondition(input) where Isolation Forest fitted on dynamic test batches_
    - _Expected_Behavior: Isolation Forest fitted on clean historical distributions_
    - _Preservation: Anomaly detection continues to work correctly_
    - _Requirements: 2.5.4_

  - [x] 7.7 Add Model Governance Logging and Monitoring
    - Create log file `logs/model_governance.log` for centralized governance logging
    - Log all optimizer failures, fallbacks, and status changes
    - Implement daily summary reports:
      ```python
      def generate_daily_governance_report():
          report = {
              'date': datetime.today().date(),
              'optimizer_failures': count_optimizer_failures(),
              'model_fallbacks': count_model_fallbacks(),
              'volatility_floors_applied': count_volatility_floors(),
              'predictions_by_status': count_predictions_by_status()
          }
          save_report(report, f'logs/governance_report_{report["date"]}.json')
      ```
    - Schedule daily report generation
    - _Bug_Condition: No centralized governance monitoring_
    - _Expected_Behavior: Comprehensive logging and daily reports_
    - _Preservation: Existing logging continues_
    - _Requirements: 2.5.1, 2.5.2, 2.5.3, 2.5.4, 2.5.5_

  - [x] 7.8 Create Model Governance Test Suite
    - Create test file `tests/test_model_governance.py`
    - Test 1: Verify optimizer failure triggers safe defaults
    - Test 2: Verify volatility floor enforcement prevents zero barriers
    - Test 3: Verify model status metadata included in predictions
    - Test 4: Verify alerts fire on failures
    - Test 5: Verify Isolation Forest fitted on historical data
    - Run full test suite to confirm governance framework
    - _Bug_Condition: Model governance not tested_
    - _Expected_Behavior: Comprehensive tests verify governance framework_
    - _Preservation: Existing model tests continue_
    - _Requirements: 2.5.1, 2.5.2, 2.5.3, 2.5.4, 2.5.5_

## Phase 8: Fix Verification

- [x] 8. Verify bug condition exploration tests now pass (Expected Behavior validation)

  - [x] 8.1 Re-run Storage & Concurrency Test
    - **Property 1: Expected Behavior** - Centralized Connection Pooling
    - **IMPORTANT**: Re-run the SAME test from Phase 1.1 - do NOT write a new test
    - The test from Phase 1.1 encodes the expected behavior
    - Run test: `pytest tests/test_bug_storage_concurrency.py -v`
    - **EXPECTED OUTCOME**: Test PASSES (confirms connection pooling works)
    - Verify: 10 concurrent requests complete without "database locked" errors
    - Verify: Active connections ≤ 10 at all times
    - _Requirements: 2.1.1, 2.1.2, 2.1.3, 2.1.4_

  - [x] 8.2 Re-run Anti-Wash Filter Test
    - **Property 1: Expected Behavior** - Strict Anti-Wash Filtering
    - **IMPORTANT**: Re-run the SAME test from Phase 1.2 - do NOT write a new test
    - Run test: `pytest tests/test_bug_anti_wash_bypass.py -v`
    - **EXPECTED OUTCOME**: Test PASSES (confirms wash trades rejected)
    - Verify: All trades with buyer_broker_id == seller_broker_id rejected
    - Verify: Schema canonicalization applied correctly
    - _Requirements: 2.2.1, 2.2.2, 2.2.3, 2.2.4_

  - [x] 8.3 Re-run Temporal Leakage Test
    - **Property 1: Expected Behavior** - Temporal Integrity Enforcement
    - **IMPORTANT**: Re-run the SAME test from Phase 1.3 - do NOT write a new test
    - Run test: `pytest tests/test_bug_temporal_leakage.py -v`
    - **EXPECTED OUTCOME**: Test PASSES (confirms 1-session lag enforced)
    - Verify: No same-day broker concentration in training data
    - Verify: All features properly lagged by 1 session
    - _Requirements: 2.3.1, 2.3.2, 2.3.3_

  - [x] 8.4 Re-run Ghost Features Test
    - **Property 1: Expected Behavior** - Explicit Feature Computation
    - **IMPORTANT**: Re-run the SAME test from Phase 1.4 - do NOT write a new test
    - Run test: `pytest tests/test_bug_ghost_features.py -v`
    - **EXPECTED OUTCOME**: Test PASSES (confirms all 5 features computed)
    - Verify: frac_diff_close, macd_norm, rsi_14, log_return, range_vol all non-zero
    - Verify: Pandera validation passes for all features
    - _Requirements: 2.4.1, 2.4.2, 2.4.3, 2.4.4_

  - [x] 8.5 Re-run Optimizer Failure Test
    - **Property 1: Expected Behavior** - Fail-Closed Optimizer Validation
    - **IMPORTANT**: Re-run the SAME test from Phase 1.5 - do NOT write a new test
    - Run test: `pytest tests/test_bug_optimizer_failure.py -v`
    - **EXPECTED OUTCOME**: Test PASSES (confirms safe defaults on failure)
    - Verify: Optimizer failures trigger safe defaults, not 1e9 parameters
    - Verify: Volatility floor prevents zero profit barriers
    - _Requirements: 2.5.1, 2.5.2, 2.5.3, 2.5.4, 2.5.5_

## Phase 9: Preservation Verification

- [x] 9. Verify preservation tests still pass (No Regression validation)

  - [x] 9.1 Re-run Storage Preservation Test
    - **Property 2: Preservation** - Sequential Operations Unchanged
    - **IMPORTANT**: Re-run the SAME tests from Phase 2.1 - do NOT write new tests
    - Run test: `pytest tests/test_preserve_storage.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in sequential operations)
    - Verify: Single-threaded batch jobs execute successfully
    - Verify: Parquet writes produce valid files
    - _Requirements: 3.1.1, 3.1.2, 3.1.3_

  - [x] 9.2 Re-run Ingestion Preservation Test
    - **Property 2: Preservation** - Legitimate Trades Unchanged
    - **IMPORTANT**: Re-run the SAME tests from Phase 2.2 - do NOT write new tests
    - Run test: `pytest tests/test_preserve_ingestion.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in trade ingestion)
    - Verify: Cross-broker trades pass anti-wash filter
    - Verify: Complete API payloads process correctly
    - _Requirements: 3.2.1, 3.2.2, 3.2.3_

  - [x] 9.3 Re-run Temporal Preservation Test
    - **Property 2: Preservation** - Multi-Day Features Unchanged
    - **IMPORTANT**: Re-run the SAME tests from Phase 2.3 - do NOT write new tests
    - Run test: `pytest tests/test_preserve_temporal.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in multi-day features)
    - Verify: 5-day moving averages, 20-day volatility calculate correctly
    - Verify: Historical backtesting produces accurate metrics
    - _Requirements: 3.3.1, 3.3.2, 3.3.3_

  - [x] 9.4 Re-run Feature Store Preservation Test
    - **Property 2: Preservation** - Existing Features Unchanged
    - **IMPORTANT**: Re-run the SAME tests from Phase 2.4 - do NOT write new tests
    - Run test: `pytest tests/test_preserve_features.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in existing features)
    - Verify: 6 existing features produce correct values
    - Verify: Legitimate NULL handling works correctly
    - _Requirements: 3.4.1, 3.4.2, 3.4.3_

  - [x] 9.5 Re-run Model Governance Preservation Test
    - **Property 2: Preservation** - Successful Optimizations Unchanged
    - **IMPORTANT**: Re-run the SAME tests from Phase 2.5 - do NOT write new tests
    - Run test: `pytest tests/test_preserve_model_governance.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in successful cases)
    - Verify: Successful optimizations use optimized parameters
    - Verify: Chronos-Bolt predictions produce correct outputs
    - _Requirements: 3.5.1, 3.5.2, 3.5.3, 3.5.4, 3.5.5_

## Phase 10: Final Checkpoint

- [x] 10. Checkpoint - Ensure all tests pass and system integrity verified
  - Run complete test suite: `pytest tests/ -v`
  - Verify all bug condition tests pass (Phase 8.1-8.5)
  - Verify all preservation tests pass (Phase 9.1-9.5)
  - Verify no new regressions introduced
  - Generate test coverage report
  - Review test results with user
  - Document any edge cases or limitations discovered
  - Ensure all requirements validated (2.1.1 through 3.5.5)
  - Ask the user if questions arise or manual verification needed

---

## Notes

### Test Execution Order (CRITICAL)

1. **Phase 1 (Bug Condition Exploration)**: Write and run tests on UNFIXED code - tests MUST FAIL
2. **Phase 2 (Preservation Tests)**: Write and run tests on UNFIXED code - tests MUST PASS
3. **Phase 3-7 (Implementation)**: Implement all fixes across 5 core categories
4. **Phase 8 (Fix Verification)**: Re-run Phase 1 tests - tests MUST NOW PASS
5. **Phase 9 (Preservation Verification)**: Re-run Phase 2 tests - tests MUST STILL PASS
6. **Phase 10 (Checkpoint)**: Verify all tests pass, review with user

### Implementation Priority

**Week 1 (Critical Path)**:
- Phase 3: Storage & Concurrency (Foundation for all other fixes)
- Phase 4: Ingestion & Anti-Wash Gate (Data quality foundation)
- Phase 5: Temporal Integrity (Prevents future information leakage)

**Week 2 (High Priority)**:
- Phase 6: Feature Computation (Eliminates ghost features)
- Phase 7: Model Governance (Ensures model stability)

**Week 3 (Verification)**:
- Phase 8-10: Testing and validation

### Dependencies

**New Python Packages Required**:
- `pandera>=0.20.0` (for feature validation)
- `fracdiff>=1.0.0` (for fractional differencing)

**External Dependencies**:
- DuckDB (already installed)
- scipy (already installed)
- pandas (already installed)
- numpy (already installed)

### Specification References

All tasks reference specifications from `design.md`:
- **Bug_Condition**: `isBugCondition()` pseudocode from design
- **Expected_Behavior**: `expectedBehavior()` properties from design
- **Preservation**: Preservation Requirements sections from design
- **Requirements**: Clause numbers from `bugfix.md` (1.1.1 through 3.5.5)
