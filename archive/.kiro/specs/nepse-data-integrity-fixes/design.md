# NEPSE Quantitative Engine Data Integrity Bugfix Design

## Overview

This design addresses five critical data integrity defects in the NEPSE quantitative trading engine that compromise trading signal reliability, model accuracy, and system stability. The bugs span resource management (DuckDB connection exhaustion), data validation (anti-wash filter bypass), temporal safety (forward-looking bias), feature computation (ghost features), and model governance (silent optimizer failures). The fix implements centralized connection pooling, strict schema canonicalization, mandatory temporal lag enforcement, explicit feature computation with Pandera validation, and fail-closed optimizer assertions. The cumulative impact eliminates false alpha signals, prevents training data contamination, and ensures system stability under concurrent load.

## Glossary

- **Bug_Condition (C)**: The condition that triggers data integrity violations - when any of the five subsystems (storage, ingestion, temporal joins, feature computation, or model governance) operate with unchecked failures or silent fallbacks
- **Property (P)**: The desired behavior - all subsystems must operate with explicit validation, fail-fast semantics, and zero silent fallbacks
- **Preservation**: All existing functionality for legitimate data processing, valid model training, and correct predictions must remain unchanged
- **DuckDB Connection Manager**: Centralized thread-safe connection pool (5-10 connections) replacing 40+ independent `duckdb.connect()` calls
- **Anti-Wash Filter**: Validation gate that rejects trades where `buyer_broker_id == seller_broker_id` (self-matched internal transactions)
- **Schema Canonicalization**: Universal column mapping layer (buyerMemberId/sellerMemberId → buyer_broker_id/seller_broker_id)
- **Temporal Lag Enforcement**: Mandatory 1-session lag in SQL joins (`ON price_date = broker_date - INTERVAL 1 DAY`)
- **Ghost Features**: Model-declared features (frac_diff_close, macd_norm, rsi_14, log_return, range_vol) that have no computation implementation
- **Hawkes MLE**: Maximum Likelihood Estimation via `scipy.optimize.minimize` for self-exciting point process parameters (μ, α, β)
- **Triple-Barrier Labeling**: Dynamic profit/stop-loss bounds (profit_barrier = volatility * 2.0) for meta-labeling
- **Pandera Schema Validation**: Runtime DataFrame schema assertions that raise exceptions on validation failures (replacing silent `.fillna(0.0)`)
- **Atomic Parquet Write**: `.tmp` staging + atomic rename pattern preventing file corruption during concurrent reads
- **FastAPI Event Loop**: Asynchronous request handling requiring CPU-bound operations to execute via `ThreadPoolExecutor`

## Bug Details

### Bug Condition

The data integrity violations manifest across five subsystems when validation and error handling are absent or bypassed. The bugs trigger during concurrent operations, API ingestion, feature engineering, model training, and real-time prediction.

**Formal Specification:**
```
FUNCTION isBugCondition(system_state)
  INPUT: system_state containing {concurrent_requests, api_payload, feature_set, 
         model_params, join_queries}
  OUTPUT: boolean
  
  RETURN (system_state.concurrent_requests > 3 AND duckdb_connections >= 40)
         OR (api_payload.has_broker_ids AND NOT schema_canonicalized(api_payload))
         OR (api_payload.broker_ids_incomplete AND synthetic_ids_generated)
         OR (join_queries.contains_same_day_joins AND NOT lagged)
         OR (feature_set.declared_features != feature_set.computed_features)
         OR (scipy_optimize_result.success == False AND params_used_anyway)
         OR (triple_barrier_volatility == 0.0 AND profit_barrier == 0.0)
         OR (parquet_write_in_progress AND concurrent_read_attempted)
END FUNCTION
```

### Examples

**Bug 1: Storage & Concurrency**
- **Input**: 10 concurrent FastAPI requests each creating `duckdb.connect()`
- **Current Behavior**: 40+ file handles opened causing "database locked" errors and resource exhaustion
- **Expected Behavior**: Centralized connection pool reuses 5-10 connections with zero locking conflicts

**Bug 2: Ingestion & Anti-Wash Filter**
- **Input**: API payload with `{"buyerMemberId": "58", "sellerMemberId": "58"}`
- **Current Behavior**: Schema mismatch causes filter to compare mismatched columns (NULL != NULL = false), allowing 100% wash trades through
- **Expected Behavior**: Schema canonicalization maps to `buyer_broker_id`/`seller_broker_id`, filter rejects wash trade with explicit logging

**Bug 3: Temporal Integrity**
- **Input**: SQL join `ON price_date = broker_date` 
- **Current Behavior**: Same-day join leaks future institutional accumulation into training set creating false alpha
- **Expected Behavior**: Mandatory lag `ON price_date = broker_date - INTERVAL 1 DAY` ensures temporal correctness

**Bug 4: Ghost Features**
- **Input**: LightGBM model declares 11 features but only 6 computed
- **Current Behavior**: `.fillna(0.0)` silently zero-fills 5 missing features (frac_diff_close, macd_norm, rsi_14, log_return, range_vol) across all historical rows
- **Expected Behavior**: Explicit computation of all 5 features with Pandera assertions raising exceptions on missing data

**Bug 5: Model Governance**
- **Input**: `scipy.optimize.minimize()` returns `res.success = False` with penalty value `1e9`
- **Current Behavior**: Unchecked failure consumes `1e9` as valid Hawkes parameter causing incorrect cascade detection
- **Expected Behavior**: Assert `res.success == True`, fallback to safe defaults (μ=0.01, α=0.0, β=1.0) on failure with explicit logging

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Single-threaded batch jobs accessing DuckDB must continue to execute queries successfully with existing SQL syntax
- Legitimate cross-broker trades with complete broker IDs must continue to pass anti-wash validation and store correctly
- Multi-day lag features (e.g., 5-day moving averages, 20-day volatility) must continue to calculate correctly with appropriate lookback windows
- The 6 currently computed features (volume, price ratios, etc.) must continue to produce correct values
- Historical backtesting on properly lagged data must continue to produce accurate performance metrics
- Scipy.optimize.minimize successful convergence must continue to use optimized Hawkes parameters correctly
- Scrips with sufficient volatility for Triple-Barrier labeling must continue to generate accurate labels
- Chronos-Bolt models executing successfully must continue to produce predictions without fallback
- FastAPI routes handling lightweight synchronous operations must continue to process requests with sub-100ms latency

**Scope:**
All inputs that do NOT involve the specific bug conditions should be completely unaffected by this fix. This includes:
- Sequential single-connection DuckDB operations
- Complete API payloads with properly formatted broker IDs and timestamps
- Historical data queries with correct schema
- Training pipelines with properly lagged features
- Model prediction workflows without optimizer failures
- Low-volatility scrips that correctly apply minimum volatility floors

## Hypothesized Root Cause

Based on the bug analysis across the five subsystems, the most likely root causes are:

### 1. **Storage & Concurrency: Per-Request Connection Instantiation**
   - FastAPI async route handlers each call `duckdb.connect()` independently
   - No connection pooling or lifecycle management exists
   - Synchronous Pandas/Matplotlib operations block the event loop (8.42s observed)
   - Parquet writes use direct `.to_parquet()` without atomic staging causing corruption during concurrent reads

### 2. **Ingestion: Schema Evolution Without Canonicalization**
   - Legacy CSV columns (Buyer/Seller) coexist with API columns (buyerMemberId/sellerMemberId)
   - Anti-wash filter comparisons execute on mismatched columns resulting in NULL evaluations
   - Missing broker IDs trigger fallback to synthetic ID generation `(contract_id % 50) + 1`
   - Missing timestamps trigger wallclock substitution destroying temporal ordering

### 3. **Temporal Integrity: Implicit Same-Day Joins**
   - Feature engineering SQL uses `ON date = date` for EOD broker concentration joins
   - No explicit lag enforcement in join predicates
   - Column name misalignments between storage and scoring pipelines
   - Temporal contamination detection absent from training data validation

### 4. **Feature Computation: Declaration-Implementation Mismatch**
   - Model configuration declares 11 features but `02_feature_engineering.py` implements only 6
   - No feature completeness validation before model training
   - Silent `.fillna(0.0)` masking failures instead of raising exceptions
   - Missing computation code for: frac_diff_close (d=0.35), macd_norm, rsi_14, log_return, range_vol

### 5. **Model Governance: Unchecked Optimizer Status**
   - `scipy.optimize.minimize` result object not validated for `res.success`
   - 1e9 penalty values from failed optimization consumed as valid parameters
   - Triple-Barrier labeling computes `profit_barrier = volatility * 2.0` without minimum floor
   - Zero volatility causes `profit_barrier = 0.0` labeling every positive tick as successful
   - Isolation Forest fitted on dynamic test batches instead of historical distributions
   - No status metadata distinguishing LIVE_CHRONOS vs GBM_FALLBACK predictions

## Correctness Properties

Property 1: Bug Condition - Data Integrity Validation

_For any_ system operation where the bug condition holds (isBugCondition returns true), the fixed system SHALL enforce fail-fast validation with explicit error handling preventing silent failures, invalid data propagation, or unchecked optimization failures.

**Validates: Requirements 2.1.1, 2.1.2, 2.1.3, 2.1.4, 2.2.1, 2.2.2, 2.2.3, 2.2.4, 2.3.1, 2.3.2, 2.3.3, 2.4.1, 2.4.2, 2.4.3, 2.4.4, 2.5.1, 2.5.2, 2.5.3, 2.5.4, 2.5.5**

Property 2: Preservation - Non-Buggy Operations

_For any_ system operation where the bug condition does NOT hold (isBugCondition returns false), the fixed system SHALL produce exactly the same behavior as the original system, preserving all existing functionality for legitimate data processing, valid model training, and correct predictions.

**Validates: Requirements 3.1.1, 3.1.2, 3.1.3, 3.2.1, 3.2.2, 3.2.3, 3.3.1, 3.3.2, 3.3.3, 3.4.1, 3.4.2, 3.4.3, 3.5.1, 3.5.2, 3.5.3, 3.5.4, 3.5.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct, the following implementation changes are required across five subsystems:

### Fix 1: Storage & Concurrency Architecture

**File**: `scripts/03_data_access_and_storage/duckdb_connection_manager.py` (NEW FILE)

**Specific Changes**:
1. **Create Centralized Connection Manager Class**:
   - Implement `DuckDBConnectionManager` singleton with thread-safe connection pool
   - Maximum 5-10 connections with `threading.Lock()` for concurrency control
   - Context manager protocol (`__enter__`, `__exit__`) for automatic cleanup
   - Connection lifecycle management (acquire, release, health checks)

2. **Integration with Existing Call Sites**:
   - Replace 40+ `duckdb.connect()` calls across:
     - `scripts/01_etl_and_ingestion/init_duckdb.py`
     - `scripts/01_etl_and_ingestion/duckdb_lakehouse_loader.py`
     - `scripts/01_etl_and_ingestion/08_compute_floorsheet_broker_features.py`
     - `scripts/02_feature_engineering.py`
     - `scripts/03_train_and_backtest.py`
     - FastAPI route handlers in `scripts/pulse_terminal_server.py`
   - Use pattern: `with connection_manager.acquire() as conn:`

3. **FastAPI Async Wrapper**:
   - Create `scripts/03_data_access_and_storage/async_duckdb_executor.py`
   - Implement `AsyncDuckDBExecutor` using `ThreadPoolExecutor` (max_workers=4)
   - Wrap Pandas/Matplotlib operations in `asyncio.to_thread()`
   - Pattern: `result = await executor.execute_query(sql, params)`

4. **Atomic Parquet Write Operations**:
   - Implement `atomic_parquet_write()` helper function
   - Write to `.tmp` staging file first
   - Atomic rename using `Path.rename()` (POSIX atomic operation)
   - Pattern: 
     ```python
     tmp_path = target_path.with_suffix('.tmp')
     df.to_parquet(tmp_path)
     tmp_path.rename(target_path)
     ```

**Modified Files Priority**:
- **P0 (Critical)**: `duckdb_connection_manager.py`, `async_duckdb_executor.py`
- **P1 (High)**: `pulse_terminal_server.py`, `02_feature_engineering.py`
- **P2 (Medium)**: All other files with `duckdb.connect()` calls

---

### Fix 2: Ingestion & Anti-Wash Gate Architecture

**File**: `scripts/01_etl_and_ingestion/schema_canonicalization.py` (NEW FILE)

**Specific Changes**:
1. **Universal Column Mapping Layer**:
   - Implement `canonicalize_trade_schema(df: pd.DataFrame) -> pd.DataFrame`
   - Column mappings:
     ```python
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
   - Apply mapping before anti-wash filter evaluation

2. **Strict Anti-Wash Filter Implementation**:
   - Modify `scripts/01_etl_and_ingestion/08_compute_floorsheet_broker_features.py`
   - Replace: `(CAST(Buyer AS VARCHAR) = CAST(Seller AS VARCHAR))`
   - With: `(buyer_broker_id = seller_broker_id)` after canonicalization
   - Add assertion: `assert 'buyer_broker_id' in df.columns`

3. **Fail-Fast Validation**:
   - Implement `validate_trade_payload(payload: Dict) -> Result`
   - Required fields: `['buyer_broker_id', 'seller_broker_id', 'timestamp', 'quantity', 'price']`
   - Reject incomplete payloads with explicit logging:
     ```python
     if not all(field in payload for field in required_fields):
         logger.error(f"REJECTED: Incomplete payload missing {missing_fields}")
         return Result.REJECTED
     ```
   - **NO synthetic ID generation**: Remove `(contract_id % 50) + 1` fallback
   - **NO wallclock substitution**: Reject missing timestamps

4. **Dead-Letter Queue**:
   - Create `01_raw_data/rejected_trades.parquet` for rejected records
   - Log rejection reason, timestamp, and full payload
   - Enable forensic analysis without data loss

**Modified Files Priority**:
- **P0 (Critical)**: `schema_canonicalization.py`, `08_compute_floorsheet_broker_features.py`
- **P1 (High)**: `update_today_eod_lakehouse.py`, `nepse_ingestion_connectors.py`

---

### Fix 3: Temporal Integrity Enforcement

**File**: `scripts/02_feature_engineering.py`

**Specific Changes**:
1. **Mandatory 1-Session Lag SQL Generation**:
   - Modify broker concentration join in `run_feature_engineering()`:
   - Replace:
     ```sql
     LEFT JOIN floorsheet_broker_signals f
       ON e.ticker = f.ticker AND e.date = CAST(f.date AS DATE)
     ```
   - With:
     ```sql
     LEFT JOIN floorsheet_broker_signals f
       ON e.ticker = f.ticker 
       AND e.date = CAST(f.date AS DATE) + INTERVAL 1 DAY
     ```
   - Add SQL comment: `-- Temporal Safety: 1-session lag enforced to prevent future information leakage`

2. **Feature Join Validation Framework**:
   - Create `scripts/03_data_access_and_storage/temporal_validator.py`
   - Implement `validate_temporal_joins(df: pd.DataFrame, feature_cols: List[str]) -> Result`
   - Check for same-day contamination:
     ```python
     def detect_same_day_contamination(df):
         # Verify no feature from day T appears in training for day T
         for col in feature_cols:
             if df.groupby('date')[col].count().max() > expected_lag:
                 raise TemporalContaminationError(f"{col} has same-day values")
     ```

3. **Column Name Alignment Verification**:
   - Implement `verify_column_alignment(storage_schema, scoring_schema) -> Result`
   - Assert column names match across:
     - `03_feature_store/technical_indicators.parquet`
     - `03_feature_store/floorsheet_broker_signals.parquet`
     - Model training DataFrames
   - Raise `ColumnMismatchError` on misalignment

4. **Training Data Contamination Detection**:
   - Add validation step in `scripts/03_train_and_backtest.py`:
     ```python
     def validate_training_data(df_train):
         # Verify all features are properly lagged
         assert not has_future_information(df_train)
         # Verify no same-day broker concentration in labels
         assert not has_same_day_features(df_train, LAGGED_FEATURES)
     ```

**Modified Files Priority**:
- **P0 (Critical)**: `02_feature_engineering.py`, `temporal_validator.py`
- **P1 (High)**: `03_train_and_backtest.py`

---

### Fix 4: Feature Computation Pipeline

**File**: `scripts/02_feature_engineering.py`

**Specific Changes**:
1. **Explicit Computation for Missing Features**:
   - **frac_diff_close (d=0.35)**:
     ```python
     from fracdiff import fdiff
     df['frac_diff_close'] = df.groupby('ticker')['close'].transform(
         lambda x: fdiff(x, d=0.35)
     )
     ```
   - **macd_norm (Normalized MACD)**:
     ```python
     ema_12 = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=12).mean())
     ema_26 = df.groupby('ticker')['close'].transform(lambda x: x.ewm(span=26).mean())
     macd = ema_12 - ema_26
     signal = macd.ewm(span=9).mean()
     df['macd_norm'] = (macd - signal) / (df['close'] + 1e-6)
     ```
   - **rsi_14 (RSI with Wilder's Smoothing)**:
     ```python
     delta = df.groupby('ticker')['close'].diff()
     gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
     loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
     rs = gain / (loss + 1e-8)
     df['rsi_14'] = 100 - (100 / (1 + rs))
     ```
   - **log_return (Log Returns)**:
     ```python
     df['log_return'] = df.groupby('ticker')['close'].transform(
         lambda x: np.log(x / x.shift(1))
     )
     ```
   - **range_vol (Range-Based Volatility)**:
     ```python
     df['range_vol'] = (df['high'] - df['low']) / (df['close'] + 1e-6)
     df['range_vol'] = df.groupby('ticker')['range_vol'].rolling(20).std()
     ```

2. **Pandera Schema Validation**:
   - Install `pandera` dependency: Add to `requirements.txt`
   - Define schema:
     ```python
     import pandera as pa
     
     FEATURE_SCHEMA = pa.DataFrameSchema({
         'frac_diff_close': pa.Column(float, nullable=False),
         'macd_norm': pa.Column(float, nullable=False),
         'rsi_14': pa.Column(float, pa.Check.in_range(0, 100), nullable=False),
         'log_return': pa.Column(float, nullable=False),
         'range_vol': pa.Column(float, pa.Check.greater_than_or_equal_to(0), nullable=False)
     })
     ```
   - Replace `.fillna(0.0)` with validation:
     ```python
     try:
         df_validated = FEATURE_SCHEMA.validate(df)
     except pa.errors.SchemaError as e:
         logger.error(f"Feature validation failed: {e}")
         raise FeatureComputationError(f"Missing features: {e.failure_cases}")
     ```

3. **Feature Completeness Validation**:
   - Add pre-training check in `scripts/03_train_and_backtest.py`:
     ```python
     REQUIRED_FEATURES = [
         'frac_diff_close', 'macd_norm', 'rsi_14', 'log_return', 'range_vol',
         'volume_zscore_20', 'kline_body_density', 'amihud_illiquidity',
         'top_buyer_concentration', 'buyer_hhi', 'broker_net_imbalance'
     ]
     
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

4. **Explicit Logging**:
   - Add feature computation logging:
     ```python
     logger.info(f"Computed frac_diff_close: mean={df['frac_diff_close'].mean():.4f}, std={df['frac_diff_close'].std():.4f}")
     logger.info(f"Computed macd_norm: mean={df['macd_norm'].mean():.4f}, std={df['macd_norm'].std():.4f}")
     logger.info(f"Computed rsi_14: mean={df['rsi_14'].mean():.2f}, min={df['rsi_14'].min():.2f}, max={df['rsi_14'].max():.2f}")
     ```

**Modified Files Priority**:
- **P0 (Critical)**: `02_feature_engineering.py`, `03_train_and_backtest.py`
- **P1 (High)**: Add `pandera` to `requirements.txt`

---

### Fix 5: Model Governance Framework

**File**: `scripts/02_modeling_and_calculations/hawkes_broker_cascade.py`

**Specific Changes**:
1. **Optimizer Success Validation**:
   - Modify `fit()` method:
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
         logger.warning(f"Hawkes MLE optimization failed: {res.message}")
         logger.warning(f"Falling back to safe defaults")
         return HawkesParameters(
             mu=0.01, alpha=0.0, beta=1.0, branching_ratio=0.0,
             log_likelihood=0.0, is_supercritical=False, cascade_hazard_score=0.0
         )
     
     # Only use optimized parameters if successful
     mu, alpha, beta = res.x
     ```

2. **Explicit Failover to Safe Defaults**:
   - Define constant safe defaults:
     ```python
     SAFE_HAWKES_DEFAULTS = {
         'mu': 0.01,      # Minimal background rate
         'alpha': 0.0,    # No excitation
         'beta': 1.0,     # Standard decay
         'branching_ratio': 0.0,
         'regime': 'OPTIMIZER_FAILED'
     }
     ```

3. **Volatility Floor Enforcement**:
   - Modify `scripts/03_train_and_backtest.py`:
     ```python
     # OLD: df["profit_barrier"] = df["volatility_20"] * 2.0
     
     # NEW: Enforce minimum volatility floor
     MIN_VOLATILITY_FLOOR = 0.01  # 1% minimum
     df["effective_volatility"] = df["volatility_20"].clip(lower=MIN_VOLATILITY_FLOOR)
     df["profit_barrier"] = df["effective_volatility"] * 2.0
     
     # Verify no zero barriers
     assert (df["profit_barrier"] > 0).all(), "Zero profit barriers detected"
     ```

4. **Status Metadata Tagging**:
   - Add model status to prediction outputs:
     ```python
     prediction_output = {
         'symbol': symbol,
         'prediction': pred_value,
         'model_status': 'LIVE_CHRONOS',  # or 'GBM_FALLBACK'
         'model_version': 'chronos-bolt-v1.0',
         'fallback_reason': None,  # or error message
         'timestamp': datetime.now(timezone.utc).isoformat()
     }
     ```

5. **Isolation Forest Fitting on Historical Data**:
   - Modify Isolation Forest training in model governance modules:
     ```python
     # OLD: fitted on dynamic test batches
     # iso_forest.fit(test_batch_features)
     
     # NEW: Fit on clean historical training distribution
     historical_clean_data = load_historical_features(
         start_date='2023-01-01',
         end_date='2024-12-31',
         filters={'wash_trade_ratio': '<0.05', 'data_quality': 'VERIFIED'}
     )
     iso_forest.fit(historical_clean_data[anomaly_features])
     
     # Save fitted model for production use
     joblib.dump(iso_forest, 'models/isolation_forest_historical_fit.pkl')
     ```

**Modified Files Priority**:
- **P0 (Critical)**: `hawkes_broker_cascade.py`, `03_train_and_backtest.py`
- **P1 (High)**: Model governance modules using Isolation Forest
- **P2 (Medium)**: All prediction output generators for status metadata

---

## Module Dependencies and Integration Architecture

### Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                    Fix 1: Storage Layer                         │
│  duckdb_connection_manager.py → async_duckdb_executor.py       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ├───→ Fix 2: Ingestion Layer
                 │     schema_canonicalization.py
                 │     08_compute_floorsheet_broker_features.py
                 │
                 ├───→ Fix 3: Feature Engineering Layer
                 │     02_feature_engineering.py
                 │     temporal_validator.py
                 │     ├─→ Fix 4: Feature Computation
                 │     │   (frac_diff, macd_norm, rsi_14, etc.)
                 │     │   pandera validation
                 │     │
                 │     └─→ Fix 3: Temporal Joins
                 │         (1-session lag enforcement)
                 │
                 └───→ Fix 5: Model Governance Layer
                       03_train_and_backtest.py
                       hawkes_broker_cascade.py
                       ├─→ Optimizer validation
                       ├─→ Volatility floor enforcement
                       ├─→ Status metadata tagging
                       └─→ Isolation Forest historical fitting
```

### Integration Points

1. **DuckDB Connection Manager**: All modules requiring database access
   - Priority: Implement first as foundation for all other fixes
   - Affects: ~15 Python modules across ETL, feature engineering, training

2. **Schema Canonicalization**: Anti-wash filter and all ingestion modules
   - Priority: Implement before Fix 3 (temporal joins need clean schema)
   - Affects: Data ingestion, floorsheet processing, real-time streaming

3. **Temporal Validator**: Feature engineering and model training
   - Priority: Implement after Fix 2 (needs canonical schema)
   - Affects: Training data construction, backtesting validation

4. **Feature Computation**: Feature engineering and validation
   - Priority: Can be implemented independently after Fix 1
   - Affects: Model training, real-time prediction

5. **Model Governance**: Training and prediction modules
   - Priority: Can be implemented independently
   - Affects: Model training, real-time prediction, backtest evaluation

### File Modification Plan

#### Priority 0 (Critical - Week 1)
1. **NEW**: `scripts/03_data_access_and_storage/duckdb_connection_manager.py`
2. **NEW**: `scripts/03_data_access_and_storage/async_duckdb_executor.py`
3. **NEW**: `scripts/01_etl_and_ingestion/schema_canonicalization.py`
4. **MODIFY**: `scripts/01_etl_and_ingestion/08_compute_floorsheet_broker_features.py`
5. **MODIFY**: `scripts/02_feature_engineering.py` (temporal lag + feature computation)

#### Priority 1 (High - Week 2)
6. **NEW**: `scripts/03_data_access_and_storage/temporal_validator.py`
7. **MODIFY**: `scripts/03_train_and_backtest.py` (validation + volatility floor)
8. **MODIFY**: `scripts/02_modeling_and_calculations/hawkes_broker_cascade.py`
9. **MODIFY**: `scripts/pulse_terminal_server.py` (async executor integration)
10. **MODIFY**: `scripts/01_etl_and_ingestion/update_today_eod_lakehouse.py`

#### Priority 2 (Medium - Week 3)
11. **MODIFY**: All remaining files with `duckdb.connect()` calls (~10 files)
12. **MODIFY**: Model governance modules (Isolation Forest fitting)
13. **MODIFY**: Prediction output generators (status metadata)
14. **UPDATE**: `requirements.txt` (add pandera, fracdiff dependencies)

---

## Testing Strategy

### Validation Approach

The testing strategy follows a three-phase approach: first, surface counterexamples demonstrating bugs on unfixed code (exploratory); second, verify fixes work correctly (fix checking); third, verify existing functionality is preserved (preservation checking).

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing fixes. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that exercise each bug condition on UNFIXED code to observe failures and understand root causes.

**Test Cases**:

1. **Storage Concurrency Test**: Simulate 10 concurrent FastAPI requests each calling `duckdb.connect()` (will fail with "database locked")
2. **Anti-Wash Bypass Test**: Ingest trades with `buyerMemberId=sellerMemberId` and verify filter fails to reject (will fail - wash trades pass through)
3. **Temporal Leakage Test**: Query training data and verify same-day broker concentration features exist (will fail - future information present)
4. **Ghost Feature Test**: Train model on declared 11 features and verify only 6 have non-zero values (will fail - 5 features zero-filled)
5. **Optimizer Failure Test**: Force `scipy.optimize.minimize` to fail and verify system crashes or uses invalid parameters (will fail - 1e9 consumed as parameter)
6. **Zero Volatility Test**: Create scrip with zero volatility and verify `profit_barrier=0.0` labels every tick as success (will fail - incorrect labels)

**Expected Counterexamples**:
- DuckDB "database is locked" errors under concurrent load
- 100% wash trades passing anti-wash filter with schema mismatch
- Training data containing same-day institutional features
- 5 features showing 100% zero values across all historical rows
- Hawkes branching ratio = 1e9 / 1e9 = 1.0 indicating "SUPERCRITICAL_CASCADE" for quiet stocks
- All positive price movements labeled as successful trades for zero-volatility scrips

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed system produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixed_system(input)
  ASSERT expectedBehavior(result)
END FOR
```

**Test Cases**:

1. **Connection Pool Stress Test**:
   ```python
   async def test_concurrent_requests():
       tasks = [make_fastapi_request() for _ in range(50)]
       results = await asyncio.gather(*tasks)
       assert all(r.status_code == 200 for r in results)
       assert connection_manager.active_connections <= 10
   ```

2. **Anti-Wash Filter Validation**:
   ```python
   def test_anti_wash_filter_strict():
       wash_trade = {"buyerMemberId": "58", "sellerMemberId": "58", ...}
       result = process_trade(wash_trade)
       assert result.status == "REJECTED"
       assert "wash trade" in result.rejection_reason.lower()
   ```

3. **Temporal Lag Enforcement**:
   ```python
   def test_temporal_lag_sql():
       df = run_feature_engineering()
       # Verify broker concentration from date T appears in features for date T+1
       for date in df['date'].unique():
           broker_feat = df[df['date'] == date]['top_buyer_concentration']
           assert not has_same_day_values(broker_feat, date)
   ```

4. **Feature Computation Validation**:
   ```python
   def test_all_features_computed():
       df = run_feature_engineering()
       required = ['frac_diff_close', 'macd_norm', 'rsi_14', 'log_return', 'range_vol']
       for feat in required:
           assert feat in df.columns
           zero_pct = (df[feat] == 0.0).mean()
           assert zero_pct < 0.50  # Less than 50% zeros
   ```

5. **Optimizer Success Validation**:
   ```python
   def test_hawkes_optimizer_failure_handling():
       # Force optimizer failure with degenerate data
       timestamps = np.array([0, 0, 0])  # Degenerate case
       params = hawkes_engine.fit(timestamps)
       assert params.mu == 0.01  # Safe default
       assert params.branching_ratio == 0.0
   ```

6. **Volatility Floor Enforcement**:
   ```python
   def test_zero_volatility_handling():
       df = pd.DataFrame({'volatility_20': [0.0, 0.001, 0.02]})
       df = apply_triple_barrier_labels(df)
       assert (df['profit_barrier'] > 0).all()
       assert df.loc[0, 'profit_barrier'] >= MIN_VOLATILITY_FLOOR * 2.0
   ```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed system produces the same result as the original system.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT original_system(input) = fixed_system(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for legitimate operations, then write property-based tests capturing that behavior.

**Test Cases**:

1. **Sequential DuckDB Operations Preservation**:
   ```python
   @given(st.lists(st.text(), min_size=1, max_size=100))
   def test_single_connection_queries_unchanged(ticker_list):
       # Single-threaded batch job
       with connection_manager.acquire() as conn:
           result_old = conn.execute(f"SELECT * FROM market WHERE ticker IN {tuple(ticker_list)}")
           result_new = conn.execute(f"SELECT * FROM market WHERE ticker IN {tuple(ticker_list)}")
       assert result_old.fetchall() == result_new.fetchall()
   ```

2. **Legitimate Trade Processing Preservation**:
   ```python
   @given(st.integers(1, 99), st.integers(1, 99), st.floats(10, 1000))
   def test_cross_broker_trades_preserved(buyer_id, seller_id, quantity):
       assume(buyer_id != seller_id)  # Legitimate cross-broker trade
       trade = {"buyer_broker_id": buyer_id, "seller_broker_id": seller_id, "quantity": quantity}
       assert process_trade(trade).status == "ACCEPTED"
   ```

3. **Multi-Day Lag Feature Preservation**:
   ```python
   def test_existing_features_unchanged():
       df_old = load_historical_features_v1()  # Before fix
       df_new = run_feature_engineering()      # After fix
       
       # Verify 6 existing features produce identical values
       existing_features = ['volume_zscore_20', 'kline_body_density', 'amihud_illiquidity', 
                           'dist_sma20', 'dist_sma50', 'bb_pct_b']
       for feat in existing_features:
           np.testing.assert_allclose(df_old[feat], df_new[feat], rtol=1e-5)
   ```

4. **Successful Optimizer Preservation**:
   ```python
   def test_successful_hawkes_optimization_unchanged():
       # Well-behaved timestamp sequence
       timestamps = np.cumsum(np.random.exponential(10, size=100))
       params_old = hawkes_engine_v1.fit(timestamps)
       params_new = hawkes_engine_v2.fit(timestamps)
       
       # Verify optimized parameters are identical (within numerical tolerance)
       assert abs(params_old.mu - params_new.mu) < 1e-4
       assert abs(params_old.alpha - params_new.alpha) < 1e-4
       assert abs(params_old.beta - params_new.beta) < 1e-4
   ```

5. **Normal Volatility Triple-Barrier Preservation**:
   ```python
   @given(st.floats(0.01, 0.10))
   def test_normal_volatility_barriers_unchanged(volatility):
       df = pd.DataFrame({'volatility_20': [volatility]})
       df_old = apply_triple_barrier_v1(df)
       df_new = apply_triple_barrier_v2(df)
       
       np.testing.assert_allclose(df_old['profit_barrier'], df_new['profit_barrier'], rtol=1e-6)
   ```

### Unit Tests

- Test DuckDB connection pool acquire/release cycles
- Test schema canonicalization for all legacy column name variants
- Test temporal lag SQL generation with various date formats
- Test individual feature computations (frac_diff, MACD, RSI, etc.)
- Test Pandera schema validation failures
- Test optimizer failure detection and safe default assignment
- Test volatility floor enforcement with edge cases
- Test atomic Parquet write rollback on write failure

### Property-Based Tests

- Generate random concurrent request patterns and verify connection pool stability
- Generate random trade payloads and verify schema canonicalization correctness
- Generate random date ranges and verify temporal lag consistency
- Generate random price series and verify all features compute to non-zero values
- Generate random optimization initial conditions and verify result handling
- Generate random volatility distributions and verify profit barriers always positive

### Integration Tests

- Full ETL pipeline: Raw CSV → Schema Canonicalization → Anti-Wash Filter → Feature Engineering → Model Training
- Concurrent API request stress test with 100+ simultaneous requests
- End-to-end prediction pipeline with LIVE_CHRONOS vs GBM_FALLBACK status tracking
- Historical backtest reproduction verifying identical results on legitimate data
- Feature store consistency check across storage/scoring pipelines
