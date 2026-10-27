# NEPSE Data Integrity & Architecture Bugfix Design

## Overview

The NEPSE quantitative trading system is experiencing severe model signal distortion and false alpha generation caused by five critical categories of bugs spanning data corruption, temporal integrity violations, feature computation failures, model validation gaps, and system concurrency issues. This comprehensive design addresses all categories in a unified architectural refactor to restore data integrity and system reliability across the entire quantitative engine pipeline.

The fix implements centralized DuckDB connection pooling, async FastAPI operations, atomic Parquet writes, strict anti-wash filtering, mandatory 1-session lag joins, complete feature computation pipelines, and robust model validation with explicit fallback handling.

## Glossary

- **Bug_Condition (C)**: The condition that triggers system failures - when concurrent operations, incorrect schema mappings, same-day joins, missing features, or unvalidated optimizer results cause data corruption or false signals
- **Property (P)**: The desired behavior when issues are detected - proper error handling, data integrity preservation, and temporal safety enforcement
- **Preservation**: Existing trading logic, API compatibility, historical data integrity, and monitoring systems that must remain unchanged by the fix
- **DuckDB Connection Pool**: Centralized thread-safe connection management preventing file-locking conflicts
- **Anti-Wash Filter**: Strict broker trade filtering ensuring buyer_broker_id != seller_broker_id to block wash trades
- **Temporal Lag Join**: Mandatory 1-session delay (date - INTERVAL 1 DAY) preventing look-ahead bias in feature joins
- **Feature Pipeline**: Complete computation system ensuring all declared features (frac_diff_close d=0.35, macd_norm, rsi_14) are computed
- **Model Validator**: Success checking system for optimizer results with explicit fallback status metadata

## Bug Details

### Bug Condition

The bugs manifest across five critical system categories when the quantitative engine processes market data, computes features, trains models, and executes trades. The system exhibits data corruption, temporal integrity violations, silent failures, and concurrency conflicts that destroy model reliability.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type SystemOperation
  OUTPUT: boolean
  
  RETURN input.operationType IN ['concurrent_db_access', 'broker_data_processing', 'feature_join', 'feature_computation', 'model_optimization']
         AND (
           (input.operationType == 'concurrent_db_access' AND hasFileLockingConflict(input))
           OR (input.operationType == 'broker_data_processing' AND hasSchemaMapping Errors(input))
           OR (input.operationType == 'feature_join' AND hasSameDayJoin(input))
           OR (input.operationType == 'feature_computation' AND hasMissingFeatures(input))
           OR (input.operationType == 'model_optimization' AND hasUnvalidatedResults(input))
         )
END FUNCTION
```

### Examples

- **Storage & Concurrency**: Multiple processes attempt DuckDB operations → file-locking conflicts and 8.42s latency spikes
- **Broker Data Corruption**: API returns `buyerMemberId/sellerMemberId` but anti-wash filter expects `Buyer/Seller` → 100% wash trades pass through
- **Temporal Leakage**: EOD broker signals joined with `ON date = date` → future institutional data leaks into training sets
- **Missing Features**: LightGBM training expects `frac_diff_close d=0.35, macd_norm, rsi_14` but only gets zero-fills → silent degradation
- **Model Validation**: Hawkes optimization fails but `res.success` unchecked → invalid parameters consumed downstream

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Core trading logic and signal generation for legitimate (non-wash) trades must continue operating identically
- API response schemas and external system compatibility must remain unchanged
- Historical price/volume data precision and technical indicator calculations must maintain exact numerical results
- System monitoring, alerting thresholds, and performance metrics must continue operating without false alerts

**Scope:**
All inputs that do NOT involve the five critical bug categories should be completely unaffected by this fix. This includes:
- Legitimate market data processing with proper broker segregation
- Historical backtesting with correctly lagged features
- Model training with complete, properly computed feature vectors
- API queries and UI interactions within normal operational parameters

## Hypothesized Root Cause

Based on the bug analysis across the quantitative engine pipeline, the most likely root causes are:

1. **Architectural Concurrency Design**: The system lacks centralized connection pooling for DuckDB operations
   - Multiple processes create independent connections leading to file-locking conflicts
   - FastAPI routes execute synchronous operations blocking the event loop
   - Parquet writes are non-atomic causing corruption during concurrent access

2. **Schema Mapping Inconsistencies**: The broker data processing pipeline has API schema evolution mismatches
   - Anti-wash filters expect legacy column names (Buyer/Seller) but API returns new schema (buyerMemberId/sellerMemberId)
   - Error handling silently generates synthetic broker IDs using modulo math instead of failing fast
   - Timestamp unavailability substitutes wallclock times destroying tick sequencing

3. **Temporal Join Implementation**: Feature joining lacks temporal safety enforcement
   - EOD broker concentration signals use same-day equality joins instead of mandatory lag
   - Training pipelines consume contaminated features with forward-looking information
   - Point-in-time data integrity is not systematically enforced across all feature computations

4. **Feature Pipeline Incompleteness**: The feature computation system has declaration-implementation gaps
   - Technical indicators like fractional differentiation (d=0.35), normalized MACD, and RSI-14 are declared but not computed
   - Missing features are silently zero-filled instead of raising runtime exceptions
   - Feature store consistency is not validated before model training

## Correctness Properties

Property 1: Bug Condition - Data Integrity and System Reliability

_For any_ system operation where the bug condition holds (concurrent access, schema mismatches, same-day joins, missing features, or unvalidated optimization), the fixed system SHALL properly handle the operation with data integrity preservation, temporal safety enforcement, complete feature computation, and explicit error handling instead of silent failures or data corruption.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13**

Property 2: Preservation - Existing System Behavior

_For any_ system operation that does NOT involve the five critical bug categories (legitimate trading operations, properly formatted data, historical analysis, complete features, successful optimization), the fixed system SHALL produce exactly the same results as the original system, preserving all existing trading logic, API compatibility, historical data integrity, and monitoring functionality.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10**

## Fix Implementation

### Changes Required

The architectural fixes span multiple system layers requiring coordinated changes across database access, API processing, feature engineering, model training, and validation frameworks.

**Files and Components**:

**1. Storage & Concurrency Management Layer**

*File*: `scripts/storage/duckdb_connection_manager.py` (new)
*File*: `scripts/03_data_access_and_storage/01_nepse_market_api_client.py` (modify)

**Specific Changes**:
1. **Centralized DuckDB Connection Pool**: Implement singleton connection manager with thread-safe pooling
   - Single-writer threadpool executor preventing concurrent file access conflicts
   - Connection lifecycle management with automatic cleanup and error recovery
   - Connection string normalization and database file path resolution

2. **Async FastAPI Wrapper**: Convert synchronous Pandas operations to async thread executors
   - Wrap CPU-bound operations in `asyncio.create_task()` with `ThreadPoolExecutor`
   - Implement non-blocking data transformation pipelines
   - Add async context managers for long-running computations

3. **Atomic Parquet Operations**: Implement `.tmp` write-then-rename atomic file operations
   - Create temporary files with unique suffixes during write operations
   - Atomic rename operation ensuring consistency during concurrent access
   - Error handling with automatic cleanup of temporary files

**2. Broker Data Integrity & Anti-Wash Filtering Layer**

*File*: `scripts/01_etl_and_ingestion/08_compute_floorsheet_broker_features.py` (modify)
*File*: `scripts/01_etl_and_ingestion/update_today_eod_lakehouse.py` (modify)

**Specific Changes**:
1. **API Schema Mapping Correction**: Update column name mappings for current NEPSE API
   - Map `buyerMemberId` → `buyer_broker_id` and `sellerMemberId` → `seller_broker_id`
   - Implement schema validation with version detection and automatic mapping
   - Add comprehensive logging for schema evolution tracking

2. **Strict Anti-Wash Filter Enforcement**: Implement rigorous wash trade detection
   - Enforce `buyer_broker_id != seller_broker_id` condition with no exceptions
   - Add statistical reporting of wash trade percentages and blocked amounts
   - Implement broker ID validation and range checking

3. **Fail-Fast Incomplete Data Handling**: Replace synthetic data generation with explicit failures
   - Raise `ValueError` exceptions when broker data is missing instead of generating synthetic IDs
   - Implement comprehensive data completeness validation before processing
   - Add detailed logging for data quality issues and rejection reasons

**3. Temporal Integrity Enforcement Layer**

*File*: `scripts/02_feature_engineering.py` (modify)
*File*: `scripts/02_modeling_and_calculations/03_train_and_backtest.py` (modify)

**Specific Changes**:
1. **Mandatory 1-Session Lag Joins**: Implement temporal safety in all feature joins
   - Replace `ON date = date` with `ON price_date = broker_date - INTERVAL 1 DAY`
   - Add systematic lag validation across all EOD feature combinations
   - Implement point-in-time data integrity checking framework

2. **Historical-Only Training Features**: Enforce temporal boundaries in model training
   - Add validation that all features contain only historical data available at prediction time
   - Implement training data contamination detection with automated rejection
   - Add temporal feature audit logging for compliance verification

**4. Complete Feature Computation Layer**

*File*: `scripts/02_modeling_and_calculations/fractional_differentiation.py` (modify)
*File*: `scripts/02_feature_engineering.py` (modify)

**Specific Changes**:
1. **Fractional Differentiation Pipeline**: Implement missing `frac_diff_close d=0.35` computation
   - Add fractional differentiation function with fixed-width window implementation
   - Integrate into main feature engineering pipeline with proper temporal alignment
   - Add ADF stationarity testing and memory retention validation

2. **Complete Technical Indicators**: Implement missing `macd_norm` and `rsi_14` features
   - Add normalized MACD computation (MACD / close_price) with proper scale invariance
   - Implement RSI-14 calculation with Wilder's smoothing method
   - Add comprehensive technical indicator validation and range checking

3. **Runtime Feature Validation**: Replace silent zero-fills with explicit exception handling
   - Implement feature completeness checking before model training
   - Raise `RuntimeError` for missing declared features instead of zero-filling
   - Add feature availability audit with detailed reporting

**5. Model Validation & Error Handling Layer**

*File*: `scripts/hawkes_process_optimizer.py` (modify)
*File*: `scripts/chronos_model_wrapper.py` (modify)
*File*: `scripts/triple_barrier_labeler.py` (modify)

**Specific Changes**:
1. **Optimizer Success Validation**: Implement rigorous optimization result checking
   - Add `assert res.success == True` validation for all scipy.optimize calls
   - Implement explicit failover mechanisms with status logging
   - Add convergence diagnostics and parameter validation

2. **Explicit Model Fallback Status**: Implement transparent degradation reporting
   - Add status metadata to all model prediction outputs indicating fallback mode
   - Implement fallback detection in downstream consumption with explicit alerts
   - Add model health monitoring and automated escalation

3. **Volatility Floor Implementation**: Implement minimum volatility floors for Triple-Barrier labels
   - Add `profit_barrier = max(volatility, min_vol) * 2.0` calculation
   - Implement dynamic minimum volatility based on market regime detection
   - Add label quality validation and statistical distribution monitoring

## Testing Strategy

### Validation Approach

The testing strategy follows a comprehensive three-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code to confirm root cause analysis; second, implement fixes and verify correct behavior for all buggy inputs; third, ensure preservation of existing functionality for all non-buggy operations.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each of the five bug categories BEFORE implementing fixes. Confirm root cause hypotheses and refute any incorrect assumptions requiring re-analysis.

**Test Plan**: Write comprehensive test suites that simulate each failure mode and run them on the UNFIXED codebase to observe failures, collect error patterns, and validate our understanding of the root causes.

**Test Cases**:
1. **Concurrent DuckDB Access Test**: Simulate multiple processes accessing DuckDB simultaneously (will fail on unfixed code)
2. **Schema Mapping Test**: Test anti-wash filter with current API schema `buyerMemberId/sellerMemberId` (will fail on unfixed code)
3. **Same-Day Join Test**: Test EOD broker feature joins without temporal lag (will fail on unfixed code)
4. **Missing Feature Test**: Test LightGBM training with incomplete feature vectors (will fail on unfixed code)
5. **Optimizer Validation Test**: Test Hawkes optimization failure handling (will fail on unfixed code)

**Expected Counterexamples**:
- File-locking errors and event loop blocking under concurrent access
- 100% wash trades passing through due to column name mismatches
- Look-ahead bias in training data from same-day joins
- Silent zero-filling of missing features in model inputs
- Invalid optimizer parameters consumed without validation

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed system produces the expected behavior with proper data integrity, temporal safety, complete features, and robust error handling.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedSystem(input)
  ASSERT expectedBehavior(result)
END FOR
```

**Test Categories**:
1. **Concurrency Safety**: Verify thread-safe DuckDB operations and async FastAPI handling
2. **Data Integrity**: Verify proper schema mapping and strict anti-wash filtering
3. **Temporal Safety**: Verify mandatory 1-session lag enforcement in all joins
4. **Feature Completeness**: Verify all declared features are computed and validated
5. **Model Robustness**: Verify optimization success checking and explicit fallback handling

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed system produces exactly the same results as the original system.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalSystem(input) = fixedSystem(input)
END FOR
```

**Testing Approach**: Property-based testing is essential for preservation checking because:
- It generates thousands of test cases automatically across the entire input domain
- It catches subtle edge cases that manual unit tests might miss
- It provides mathematical confidence that behavior is unchanged for all legitimate operations
- It validates numerical precision preservation in financial calculations

**Test Plan**: Execute comprehensive regression testing on UNFIXED code first to establish baseline behavior, then write property-based tests capturing exact behavioral expectations across all legitimate system operations.

**Test Cases**:
1. **Trading Logic Preservation**: Verify legitimate trades produce identical signals and portfolio weights
2. **API Compatibility Preservation**: Verify all external API endpoints return identical responses
3. **Historical Data Preservation**: Verify exact numerical precision in price/volume calculations
4. **Technical Indicator Preservation**: Verify identical results for all existing feature computations

### Unit Tests

- Test individual connection pool operations and concurrent access patterns
- Test schema mapping functions with various API response formats
- Test temporal lag enforcement in feature join operations
- Test feature computation pipelines with complete and incomplete inputs
- Test model validation functions with successful and failed optimization results

### Property-Based Tests

- Generate random market data scenarios and verify concurrency safety across all operations
- Generate random broker configurations and verify wash trade detection accuracy
- Generate random temporal sequences and verify lag enforcement prevents look-ahead bias
- Generate random feature combinations and verify computation completeness and validation
- Generate random optimization scenarios and verify robust error handling and fallback behavior

### Integration Tests

- Test full quantitative engine pipeline with realistic market data and concurrent operations
- Test end-to-end model training with properly lagged features and complete computation pipelines
- Test real-time trading execution with validated models and proper error handling
- Test system monitoring and alerting under both normal operations and failure conditions
- Test API endpoint performance and reliability under concurrent load with proper data integrity