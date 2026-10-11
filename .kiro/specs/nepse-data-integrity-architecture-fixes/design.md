# NEPSE Data Integrity & Architecture Fixes - Design Document

## Overview

This design document outlines the technical solutions for addressing critical system integrity bugs in the NEPSE quantitative engine. The fixes target five major areas: storage concurrency, data integrity, temporal contamination, feature computation, and model validation.

---

## 1. Bug Condition Analysis

### 1.1 Storage & Concurrency Bug Conditions

#### Bug Condition: DuckDB Resource Exhaustion
**isBugCondition(operation)**:
```python
def isBugCondition(operation):
    return (operation.type == "duckdb_connect" and 
            operation.connection_pool is None and
            operation.concurrent_access == True)
```

**Current Failure**: Over 40 independent `duckdb.connect(path)` calls create resource exhaustion and deadlocks.

#### Bug Condition: Event Loop Blocking  
**isBugCondition(handler)**:
```python
def isBugCondition(handler):
    return (handler.is_async == True and 
            (contains_sync_io(handler) or contains_cpu_bound_ops(handler)))
```

**Current Failure**: Synchronous operations in async handlers block event loop for up to 45 seconds.

#### Bug Condition: Non-Atomic Writes
**isBugCondition(write_operation)**:
```python
def isBugCondition(write_operation):
    return (write_operation.target_format == "parquet" and 
            write_operation.atomic == False and
            write_operation.concurrent_readers > 0)
```

**Current Failure**: Direct Parquet writes cause corruption during concurrent daemon reads.

### 1.2 Data Integrity Bug Conditions

#### Bug Condition: Schema Mapping Failures
**isBugCondition(data_mapping)**:
```python
def isBugCondition(data_mapping):
    return (data_mapping.source_schema != data_mapping.target_schema and
            anti_wash_filter_uses_mapping(data_mapping) and
            data_mapping.column_mapping.get("buyer_broker_id") is None)
```

**Current Failure**: Column name mismatches (`Buyer` vs `buyerMemberId`) cause NULL evaluation.

#### Bug Condition: Synthetic ID Bypass
**isBugCondition(trade_record)**:
```python  
def isBugCondition(trade_record):
    return (trade_record.buyer_broker_id is None and
            trade_record.synthetic_id_generated == True and
            fabrication_prevents_wash_detection(trade_record))
```

**Current Failure**: `buyer_id = (contract_id % 50) + 1` and `seller_id = ((contract_id + 7) % 50) + 1` ensures `buyer_id != seller_id`.

### 1.3 Temporal Integrity Bug Conditions

#### Bug Condition: Same-Day Contamination
**isBugCondition(feature_join)**:
```python
def isBugCondition(feature_join):
    return (feature_join.institutional_features_date == feature_join.price_returns_date and
            feature_join.used_in_training == True)
```

**Current Failure**: `ON e.ticker = f.ticker AND e.trade_date = CAST(f.trade_date AS DATE)` creates look-ahead bias.

### 1.4 Feature Computation Bug Conditions

#### Bug Condition: Missing Feature Implementation
**isBugCondition(feature)**:
```python
def isBugCondition(feature):
    return (feature in ["frac_diff_close", "macd_norm", "rsi_14", "log_return", "range_vol"] and
            feature in declared_feature_columns and
            feature not in computed_features and
            feature_value_filled_with_zero(feature))
```

**Current Failure**: 45% of features are zero-filled instead of computed.

### 1.5 Model Validation Bug Conditions

#### Bug Condition: Optimizer Failure Ignored
**isBugCondition(optimization_result)**:
```python
def isBugCondition(optimization_result):
    return (optimization_result.success == False and
            optimization_result.parameters_used_in_production == True and
            no_fallback_status_reported())
```

**Current Failure**: Failed L-BFGS-B optimization parameters used without success validation.

---

## 2. Expected Behavior Specifications

### 2.1 Storage & Concurrency Expected Behavior

#### Expected Behavior: Connection Pool Manager
**expectedBehavior(result)**:
```python
def expectedBehavior(result):
    return (result.connection_pool.initialized == True and
            result.connection_pool.thread_safe == True and
            result.connection_pool.max_connections <= 10 and
            result.resource_cleanup.automatic == True)
```

#### Expected Behavior: Async Operation Offloading
**expectedBehavior(async_handler)**:
```python
def expectedBehavior(async_handler):
    return (async_handler.cpu_bound_tasks.executed_in_thread_pool == True and
            async_handler.event_loop.blocked == False and
            async_handler.response_time < 2.0)
```

#### Expected Behavior: Atomic File Operations
**expectedBehavior(file_write)**:
```python  
def expectedBehavior(file_write):
    return (file_write.temp_file_created == True and
            file_write.atomic_rename_completed == True and
            file_write.concurrent_read_corruption == False)
```

### 2.2 Data Integrity Expected Behavior

#### Expected Behavior: Schema Canonicalization
**expectedBehavior(data_ingestion)**:
```python
def expectedBehavior(data_ingestion):
    return (data_ingestion.column_names_standardized == True and
            data_ingestion.broker_id_type == "Integer" and
            data_ingestion.anti_wash_filter_functional == True)
```

#### Expected Behavior: Strict Validation
**expectedBehavior(trade_validation)**:
```python
def expectedBehavior(trade_validation):
    return (trade_validation.incomplete_records_rejected == True and
            trade_validation.synthetic_data_generated == False and
            trade_validation.wash_detection_bypassed == False)
```

### 2.3 Temporal Integrity Expected Behavior

#### Expected Behavior: Lagged Feature Joins
**expectedBehavior(temporal_join)**:
```python
def expectedBehavior(temporal_join):
    return (temporal_join.institutional_features_lag >= 1 and
            temporal_join.look_ahead_bias_eliminated == True and
            temporal_join.training_contamination == False)
```

### 2.4 Feature Computation Expected Behavior

#### Expected Behavior: Complete Feature Implementation  
**expectedBehavior(feature_pipeline)**:
```python
def expectedBehavior(feature_pipeline):
    return (feature_pipeline.frac_diff_computed == True and
            feature_pipeline.macd_norm_computed == True and
            feature_pipeline.rsi_14_computed == True and
            feature_pipeline.zero_fill_count == 0)
```

### 2.5 Model Validation Expected Behavior

#### Expected Behavior: Validated Optimization
**expectedBehavior(model_optimization)**:
```python
def expectedBehavior(model_optimization):
    return (model_optimization.success_validated == True or
            model_optimization.fallback_status_explicit == True and
            model_optimization.failed_results_unused == True)
```

---

## 3. Preservation Requirements

### 3.1 Performance Preservation Requirements

**P3.1** - System throughput must maintain >= 95% of current performance levels  
**P3.2** - Memory usage increase must be <= 20% of baseline  
**P3.3** - API response times must remain <= 2.0 seconds (95th percentile)  
**P3.4** - Database query performance must not degrade by > 10%

### 3.2 API Compatibility Preservation Requirements

**P3.5** - All existing REST API endpoints must continue to function  
**P3.6** - WebSocket message formats must remain unchanged  
**P3.7** - Client application compatibility must be maintained  
**P3.8** - Output data formats must preserve structure and precision

### 3.3 Data Integrity Preservation Requirements

**P3.9** - Historical data accuracy must be maintained  
**P3.10** - Calculation precision must not decrease  
**P3.11** - Model prediction consistency must be preserved  
**P3.12** - Audit trail completeness must be maintained

---

## 4. Technical Design Solutions

### 4.1 Centralized Connection Pool Architecture

#### Design: DuckDB Connection Manager
```python
# File: scripts/03_data_access_and_storage/duckdb_connection_manager.py
class DuckDBConnectionManager:
    def __init__(self, db_path: str, max_connections: int = 5):
        self._db_path = db_path
        self._connection_pool = queue.Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._initialize_pool()
    
    def get_connection(self) -> DuckDBConnection:
        """Get thread-safe connection from pool with timeout"""
        
    def return_connection(self, conn: DuckDBConnection):
        """Return connection to pool after use"""
        
    def execute_query(self, query: str, params=None):
        """Execute query with automatic connection management"""
```

#### Integration Points:
- Replace all `duckdb.connect()` calls across 40+ files
- Integrate with existing audit and logging systems
- Provide backward-compatible interface

### 4.2 Async Task Offloading Framework

#### Design: Thread Pool Executor Integration  
```python
# File: scripts/08_dashboard_ui/async_task_manager.py
class AsyncTaskManager:
    def __init__(self, max_workers: int = 4):
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def execute_cpu_bound(self, func, *args, **kwargs):
        """Offload CPU-bound task to thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args, **kwargs)
    
    async def execute_io_bound(self, url: str, method: str = "GET", **kwargs):
        """Execute async HTTP request"""
        response = await self.http_client.request(method, url, **kwargs)
        return response
```

#### Modified FastAPI Endpoints:
- `clef_synthesize`: Replace `requests.post()` with async HTTP client
- Chart rendering: Offload matplotlib operations to thread pool
- DataFrame transformations: Execute in background threads

### 4.3 Atomic File Operation Framework

#### Design: Atomic Parquet Writer
```python
# File: scripts/03_data_access_and_storage/atomic_file_operations.py
class AtomicParquetWriter:
    def __init__(self, target_path: str):
        self.target_path = Path(target_path)
        self.temp_path = self.target_path.with_suffix(f"{self.target_path.suffix}.tmp")
    
    def write_dataframe(self, df: pd.DataFrame):
        """Write DataFrame atomically using temp file + rename"""
        try:
            # Write to temporary file
            df.to_parquet(self.temp_path, engine='pyarrow')
            
            # Atomic rename
            self.temp_path.replace(self.target_path)
            
        except Exception as e:
            self.temp_path.unlink(missing_ok=True)
            raise e
```

### 4.4 Schema Canonicalization Pipeline

#### Design: Universal Data Mapper
```python
# File: scripts/01_etl_and_ingestion/schema_canonicalizer.py
class SchemaCanonicalizer:
    BROKER_ID_MAPPINGS = {
        'Buyer': 'buyer_broker_id',
        'buyerMemberId': 'buyer_broker_id', 
        'Seller': 'seller_broker_id',
        'sellerMemberId': 'seller_broker_id'
    }
    
    def canonicalize_broker_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names and data types"""
        df_clean = df.rename(columns=self.BROKER_ID_MAPPINGS)
        
        # Convert broker IDs to clean integers
        for col in ['buyer_broker_id', 'seller_broker_id']:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(str).str.replace('.0', '').astype(int)
        
        return df_clean
```

### 4.5 Temporal Integrity Enforcement

#### Design: Lagged Feature Join Engine
```python
# File: scripts/02_modeling_and_calculations/temporal_integrity_engine.py
class TemporalIntegrityEngine:
    def __init__(self, mandatory_lag_sessions: int = 1):
        self.lag_sessions = mandatory_lag_sessions
    
    def create_lagged_features_join(self, institutional_features_query: str, 
                                  price_returns_query: str) -> str:
        """Generate SQL with mandatory lag for institutional features"""
        return f"""
        SELECT p.*, i.*
        FROM ({price_returns_query}) p
        LEFT JOIN ({institutional_features_query}) i
        ON p.ticker = i.ticker 
        AND i.trade_date = p.trade_date - INTERVAL {self.lag_sessions} DAY
        """
```

### 4.6 Complete Feature Computation Pipeline

#### Design: Feature Factory with Validation
```python
# File: scripts/02_modeling_and_calculations/feature_computation_engine.py
class FeatureComputationEngine:
    REQUIRED_FEATURES = [
        'frac_diff_close', 'macd_norm', 'rsi_14', 'log_return', 'range_vol'
    ]
    
    def compute_fractional_diff(self, close_prices: pd.Series, d: float = 0.35) -> pd.Series:
        """Compute fractional differentiation with d=0.35"""
        from fracdiff import fdiff
        return fdiff(close_prices, d)
    
    def compute_macd_normalized(self, close_prices: pd.Series) -> pd.Series:
        """Compute normalized MACD indicator"""
        exp1 = close_prices.ewm(span=12).mean()
        exp2 = close_prices.ewm(span=26).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9).mean()
        return (macd - signal) / close_prices.rolling(20).std()
    
    def validate_feature_completeness(self, df: pd.DataFrame) -> None:
        """Strict validation - raise exception if features missing"""
        missing = [f for f in self.REQUIRED_FEATURES if f not in df.columns]
        if missing:
            raise ValueError(f"Missing required features: {missing}")
```

### 4.7 Model Validation Framework

#### Design: Optimizer Success Validator
```python
# File: scripts/02_modeling_and_calculations/model_validation_framework.py
class ModelValidationFramework:
    def validate_optimization_result(self, result) -> Dict[str, Any]:
        """Validate optimizer success and provide fallback status"""
        if result.success:
            return {
                'status': 'OPTIMIZER_SUCCESS',
                'parameters': result.x,
                'use_result': True
            }
        else:
            return {
                'status': 'OPTIMIZER_FAILED_FALLBACK_USED',
                'parameters': self.get_robust_fallback_parameters(),
                'use_result': True,
                'fallback_reason': result.message
            }
    
    def get_robust_fallback_parameters(self) -> np.ndarray:
        """Provide pre-validated fallback parameters"""
        return np.array([0.1, 0.05, 0.02])  # Conservative defaults
```

---

## 5. Implementation Architecture

### 5.1 Module Dependencies
```
DuckDBConnectionManager
    ├── Used by: All data access modules
    ├── Replaces: 40+ direct duckdb.connect() calls
    └── Dependencies: threading, queue, duckdb

AsyncTaskManager  
    ├── Used by: FastAPI endpoints
    ├── Replaces: Sync operations in async handlers
    └── Dependencies: asyncio, ThreadPoolExecutor, httpx

AtomicParquetWriter
    ├── Used by: All Parquet writing operations
    ├── Replaces: Direct pandas.to_parquet() calls
    └── Dependencies: pathlib, pandas, pyarrow

SchemaCanonicalizer
    ├── Used by: Ingestion pipeline
    ├── Replaces: Inconsistent column mappings
    └── Dependencies: pandas, typing

TemporalIntegrityEngine
    ├── Used by: Feature engineering pipeline
    ├── Replaces: Same-day joins
    └── Dependencies: SQL generation utilities

FeatureComputationEngine
    ├── Used by: Model training pipeline  
    ├── Replaces: Zero-fill feature handling
    └── Dependencies: pandas, fracdiff, ta-lib

ModelValidationFramework
    ├── Used by: All model training modules
    ├── Replaces: Unvalidated optimization results
    └── Dependencies: numpy, scipy
```

### 5.2 File Modification Plan

#### High Priority Files (Critical Path):
1. `scripts/03_data_access_and_storage/duckdb_connection_manager.py` - New file
2. `scripts/01_etl_and_ingestion/nepse_ingestion_connectors.py` - Modify to use connection pool
3. `scripts/08_dashboard_ui/main.py` - Add async task offloading
4. `scripts/02_modeling_and_calculations/feature_engineering.py` - Add complete feature computation

#### Medium Priority Files:
1. `scripts/03_data_access_and_storage/atomic_file_operations.py` - New file
2. `scripts/01_etl_and_ingestion/schema_canonicalizer.py` - New file
3. `scripts/02_modeling_and_calculations/temporal_integrity_engine.py` - New file

#### Low Priority Files (Validation & Testing):
1. `scripts/02_modeling_and_calculations/model_validation_framework.py` - New file
2. `tests/test_data_integrity_fixes.py` - New comprehensive test suite

### 5.3 Testing Strategy

#### Unit Testing Framework:
```python
# File: tests/test_data_integrity_fixes.py
class TestDataIntegrityFixes:
    def test_connection_pool_thread_safety(self):
        """Test concurrent connection pool access"""
        
    def test_atomic_parquet_operations(self):
        """Test atomic file write operations"""
        
    def test_temporal_integrity_enforcement(self):
        """Test 1-session lag enforcement"""
        
    def test_feature_computation_completeness(self):
        """Test all features are computed, not zero-filled"""
        
    def test_optimizer_validation(self):
        """Test optimizer success validation"""
```

### 5.4 Performance Impact Analysis

#### Expected Performance Changes:
- **Connection pooling**: +5-10% throughput improvement
- **Async offloading**: -50-80% API response time reduction  
- **Atomic writes**: +2-5ms write latency increase
- **Feature computation**: +10-15% CPU usage during training
- **Overall impact**: Net positive performance improvement

#### Memory Impact:
- Connection pool: +50MB baseline memory
- Thread pool executors: +20MB per worker thread
- Feature computation: +100MB during training phases
- Total increase: ~200MB (+15% of baseline)

---

## 6. Rollout Strategy

### 6.1 Phase 1: Core Infrastructure (Week 1-2)
1. Implement `DuckDBConnectionManager`
2. Replace critical connection calls in data access modules
3. Add basic atomic file operations
4. Comprehensive testing of concurrency improvements

### 6.2 Phase 2: Data Pipeline Integrity (Week 3-4)
1. Deploy schema canonicalization
2. Implement temporal integrity enforcement  
3. Add strict validation and fail-fast error handling
4. Verify anti-wash filter functionality

### 6.3 Phase 3: Feature & Model Validation (Week 5-6)
1. Complete feature computation implementation
2. Add model validation framework
3. Deploy async task offloading for FastAPI
4. Performance optimization and monitoring

### 6.4 Phase 4: Validation & Production (Week 7-8)
1. Comprehensive integration testing
2. Performance regression testing
3. Production deployment with gradual rollout
4. Monitoring and alerting setup

Each phase includes rollback plans and success criteria validation before proceeding to the next phase.