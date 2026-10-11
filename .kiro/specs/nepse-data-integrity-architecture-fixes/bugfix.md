# NEPSE Quantitative Engine Data Integrity & Architecture Fixes

## Overview

This specification addresses critical system integrity bugs in the NEPSE quantitative engine that cause data corruption, race conditions, temporal contamination, missing features, and optimizer failures. These issues compromise the reliability and accuracy of the trading system.

## Bug Classification

**Severity**: Critical  
**Type**: System Integrity & Data Corruption  
**Impact**: Production trading system failures, data contamination, resource exhaustion  
**Components**: Storage layer, ingestion pipeline, feature computation, model validation, API concurrency

---

## 1. Requirements

### 1.1 Storage & Concurrency Management Requirements

**R1.1** - DuckDB Connection Management  
The system MUST implement centralized, thread-safe connection pooling to prevent resource exhaustion and deadlocks.

**R1.2** - Async Event Loop Protection  
FastAPI endpoints MUST never block the asyncio event loop with synchronous CPU-bound or I/O operations.

**R1.3** - Atomic File Operations  
All Parquet file writes MUST be atomic to prevent corruption during concurrent reads.

**R1.4** - DDL Schema Consistency  
Database schema definitions MUST be consistent across all initialization points.

### 1.2 Broker Data Integrity Requirements

**R2.1** - API Schema Canonicalization  
All broker data ingestion MUST use standardized column names and data types.

**R2.2** - Wash Trade Detection Integrity  
Anti-wash filters MUST never be bypassed by synthetic data generation.

**R2.3** - Fail-Fast Error Handling  
Ingestion failures MUST raise explicit errors rather than generating synthetic data.

### 1.3 Temporal Integrity Requirements

**R3.1** - Look-Ahead Prevention  
All institutional features MUST be lagged by at least 1 session to prevent temporal contamination.

**R3.2** - Feature Schema Alignment  
Feature column names MUST be consistent across writing and reading operations.

### 1.4 Feature Computation Requirements

**R4.1** - Complete Feature Implementation  
All declared features MUST be computed, not zero-filled.

**R4.2** - Runtime Feature Validation  
Missing features MUST cause explicit failures, not silent backfilling.

### 1.5 Model Validation Requirements

**R5.1** - Optimizer Success Validation  
All optimization routines MUST verify convergence before using results.

**R5.2** - Explicit Fallback Status  
Model fallbacks MUST be explicitly flagged in output metadata.

**R5.3** - Volatility Floor Enforcement  
Barrier calculations MUST enforce minimum volatility thresholds.

---

## 2. Bug Conditions

### 2.1 Storage & Concurrency Bug Conditions

**C1.1** - DuckDB Resource Exhaustion  
**Current Defect**: Over 40 unpooled `duckdb.connect(path)` calls cause resource exhaustion and deadlocks  
**Bug Condition**: `isBugCondition(operation) = (operation.type == "duckdb_connect") AND (operation.connection_pool == null)`

**C1.2** - Event Loop Blocking  
**Current Defect**: Synchronous operations in async handlers block event loop for up to 45 seconds  
**Bug Condition**: `isBugCondition(handler) = (handler.is_async == true) AND (contains_sync_io_or_cpu_bound(handler) == true)`

**C1.3** - Non-Atomic Writes  
**Current Defect**: Direct Parquet writes cause corruption during concurrent reads  
**Bug Condition**: `isBugCondition(write) = (write.target == "parquet") AND (write.atomic == false)`

### 2.2 Data Integrity Bug Conditions

**C2.1** - Schema Mapping Failures  
**Current Defect**: Column name mismatches cause NULL evaluation in anti-wash filters  
**Bug Condition**: `isBugCondition(mapping) = (source_schema != target_schema) AND (anti_wash_filter_uses(mapping))`

**C2.2** - Synthetic ID Generation  
**Current Defect**: Fabricated broker IDs bypass wash trade detection  
**Bug Condition**: `isBugCondition(record) = (record.broker_id == null) AND (record.synthetic_id_generated == true)`

### 2.3 Temporal Contamination Bug Conditions

**C3.1** - Same-Day Join Contamination  
**Current Defect**: Same-day joins leak future information into training  
**Bug Condition**: `isBugCondition(join) = (institutional_features.date == price_returns.date)`

### 2.4 Feature Computation Bug Conditions

**C4.1** - Missing Feature Implementation  
**Current Defect**: 45% of features are zero-filled instead of computed  
**Bug Condition**: `isBugCondition(feature) = (feature in declared_features) AND (feature not in computed_features)`

### 2.5 Model Validation Bug Conditions  

**C5.1** - Optimizer Failure Ignored  
**Current Defect**: Failed optimization results are used without validation  
**Bug Condition**: `isBugCondition(optimization) = (optimization.success == false) AND (optimization.result_used == true)`

---

## 3. Expected Behavior

### 3.1 Storage & Concurrency Expected Behavior

**E1.1** - Connection Pool Manager  
**Expected**: Thread-safe connection pooling with proper resource cleanup  
**Verification**: `connectionPool.getConnection().isValid() == true AND connectionPool.activeConnections <= maxConnections`

**E1.2** - Async Operation Offloading  
**Expected**: CPU-bound tasks offloaded to worker threads  
**Verification**: `eventLoop.isBlocked() == false AND cpuBoundTask.executedInThread == true`

**E1.3** - Atomic File Operations  
**Expected**: Temp file + atomic rename pattern  
**Verification**: `writeOperation.isAtomic() == true AND concurrentRead.corrupted == false`

### 3.2 Data Integrity Expected Behavior

**E2.1** - Canonical Schema Mapping  
**Expected**: Consistent column names across all data sources  
**Verification**: `antiWashFilter.columnsFound == true AND brokerIdType == Integer`

**E2.2** - Strict Validation  
**Expected**: Incomplete records are rejected, not fabricated  
**Verification**: `incompleteRecord.action == "REJECT" AND syntheticData.generated == false`

### 3.3 Temporal Integrity Expected Behavior

**E3.1** - Lagged Feature Joins  
**Expected**: Institutional features lagged by 1+ sessions  
**Verification**: `institutionalFeatures.date < priceReturns.date`

### 3.4 Feature Computation Expected Behavior

**E4.1** - Complete Feature Implementation  
**Expected**: All declared features computed with correct algorithms  
**Verification**: `fracDiffComputed == true AND macdNormComputed == true AND rsi14Computed == true`

### 3.5 Model Validation Expected Behavior

**E5.1** - Validated Optimization  
**Expected**: Only successful optimization results used  
**Verification**: `optimization.success == true OR fallbackUsed == true`

---

## 4. Preservation Requirements

### 4.1 Performance Preservation
- System throughput MUST maintain current levels after fixes
- Memory usage MUST not increase significantly
- Query response times MUST remain acceptable

### 4.2 API Compatibility Preservation
- Existing API endpoints MUST continue to function
- Output formats MUST remain consistent
- Client applications MUST continue to work

### 4.3 Data Accuracy Preservation
- Historical data integrity MUST be maintained
- Calculation precision MUST be preserved
- Model output consistency MUST be retained

---

## 5. Implementation Scope

### 5.1 Files Requiring Modification
- Connection pool manager: `scripts/03_data_access_and_storage/duckdb_connection_manager.py`
- Ingestion pipeline: `scripts/01_etl_and_ingestion/nepse_ingestion_connectors.py`
- Feature computation: `scripts/02_modeling_and_calculations/feature_engineering.py`
- FastAPI endpoints: `scripts/08_dashboard_ui/main.py`
- Model validation: `scripts/02_modeling_and_calculations/hawkes_point_process.py`

### 5.2 New Components Required
- Centralized connection pool
- Schema validation framework
- Atomic file operation utilities
- Feature computation pipeline
- Model validation framework

### 5.3 Testing Requirements
- Unit tests for all new components
- Integration tests for data pipeline
- Performance regression tests
- Concurrency safety tests

---

## 6. Success Criteria

### 6.1 Primary Success Metrics
- Zero DuckDB connection errors under concurrent load
- Zero event loop blocking events > 100ms
- Zero data corruption incidents
- 100% feature computation coverage
- 100% optimizer validation coverage

### 6.2 Performance Targets
- API response time < 2 seconds (95th percentile)
- Throughput >= current production levels  
- Memory usage increase < 20%
- Zero data loss events

### 6.3 Reliability Targets
- System uptime > 99.9%
- Zero temporal contamination incidents
- Zero wash trade detection bypasses
- Zero synthetic data generation events