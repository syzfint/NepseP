# Bugfix Requirements Document

## Introduction

The NEPSE quantitative trading engine suffers from critical data integrity and architectural issues across five core subsystems that compromise trading signal reliability, model accuracy, and system stability. These defects manifest as resource exhaustion, wash trade contamination, temporal data leakage, missing feature computations, and silent optimizer failures. The cumulative impact includes false alpha signals, training data contamination, and system crashes during concurrent operations. This document specifies requirements to restore data integrity, enforce temporal correctness, and implement fail-fast validation across all pipeline stages.

## Bug Analysis

### 1. Storage & Concurrency Defects

#### 1.1 Current Behavior (Defect)

1.1.1 WHEN the system executes multiple concurrent FastAPI requests THEN over 40 independent duckdb.connect() calls are created causing file-locking conflicts and resource exhaustion

1.1.2 WHEN Pandas/Matplotlib operations execute within FastAPI route handlers THEN synchronous operations block the event loop for up to 8.42 seconds causing request timeouts

1.1.3 WHEN daemon processes read Parquet files while concurrent writes are in progress THEN non-atomic writes cause file corruption and incomplete data reads

1.1.4 WHEN CPU-intensive calculations execute in FastAPI async route handlers THEN the event loop is blocked preventing other requests from processing

#### 1.2 Expected Behavior (Correct)

2.1.1 WHEN the system executes multiple concurrent FastAPI requests THEN a centralized, thread-safe DuckDB connection manager with connection pooling SHALL reuse connections and prevent resource exhaustion

2.1.2 WHEN Pandas/Matplotlib operations execute within FastAPI route handlers THEN operations SHALL be wrapped in asyncio.to_thread() or ThreadPoolExecutor to avoid blocking the event loop

2.1.3 WHEN daemon processes read Parquet files while concurrent writes are in progress THEN atomic writes using .tmp staging followed by atomic rename SHALL ensure file integrity

2.1.4 WHEN CPU-intensive calculations execute in FastAPI async route handlers THEN operations SHALL be offloaded to thread/process pools to maintain event loop responsiveness

#### 1.3 Unchanged Behavior (Regression Prevention)

3.1.1 WHEN single-threaded batch jobs access DuckDB THEN the system SHALL CONTINUE TO execute queries successfully with existing SQL syntax

3.1.2 WHEN legitimate sequential Parquet write operations complete THEN the system SHALL CONTINUE TO produce valid Parquet files readable by all consumers

3.1.3 WHEN FastAPI routes handle lightweight synchronous operations THEN the system SHALL CONTINUE TO process requests with sub-100ms latency

### 2. Ingestion & Anti-Wash Gate Defects

#### 2.1 Current Behavior (Defect)

1.2.1 WHEN anti-wash filters evaluate trades using legacy CSV column names (Buyer/Seller) but API data contains (buyerMemberId/sellerMemberId) THEN schema mismatch causes NULL evaluation allowing 100% of wash trades through the filter

1.2.2 WHEN broker ID data is incomplete or missing from API responses THEN synthetic broker IDs are generated using modulo math ((contract_id % 50) + 1) corrupting institutional metrics with fabricated data

1.2.3 WHEN API timestamp data is unavailable THEN wallclock timestamps are substituted destroying intraday sequencing and temporal ordering

1.2.4 WHEN the anti-wash filter compares broker IDs using mismatched schema columns THEN the comparison evaluates to NULL != NULL (false) incorrectly passing wash trades as legitimate

#### 2.2 Expected Behavior (Correct)

2.2.1 WHEN the system ingests trade data from the API THEN schema canonicalization SHALL map buyerMemberId → buyer_broker_id and sellerMemberId → seller_broker_id before anti-wash filtering

2.2.2 WHEN broker ID data is incomplete or missing from API responses THEN the system SHALL reject the payload with explicit logging and fail-fast behavior instead of generating synthetic IDs

2.2.3 WHEN API timestamp data is unavailable THEN the system SHALL reject the payload with explicit logging instead of substituting wallclock timestamps

2.2.4 WHEN the anti-wash filter evaluates trades THEN strict comparison buyer_broker_id != seller_broker_id SHALL execute with properly mapped columns rejecting all wash trades

#### 2.3 Unchanged Behavior (Regression Prevention)

3.2.1 WHEN legitimate cross-broker trades are ingested THEN the system SHALL CONTINUE TO pass anti-wash validation and store trades correctly

3.2.2 WHEN complete API payloads with valid broker IDs and timestamps arrive THEN the system SHALL CONTINUE TO process trades without rejection

3.2.3 WHEN historical data with correct schema is queried THEN the system SHALL CONTINUE TO return accurate institutional metrics

### 3. Temporal Integrity Defects

#### 3.1 Current Behavior (Defect)

1.3.1 WHEN EOD broker concentration metrics are joined with price data using same-day joins (ON date = date) THEN future institutional accumulation data leaks into training sets creating forward-looking information

1.3.2 WHEN training data contains same-day broker concentration joins THEN false alpha signals are generated from future information that would not be available at prediction time

1.3.3 WHEN feature columns are joined across storage and scoring pipelines THEN inconsistent column naming causes silent misalignments and feature mismatches

#### 3.2 Expected Behavior (Correct)

2.3.1 WHEN EOD broker concentration metrics are joined with price data THEN mandatory 1-session lag SHALL be enforced using ON price_date = broker_date - INTERVAL 1 DAY to prevent temporal leakage

2.3.2 WHEN training data is constructed THEN temporal contamination detection SHALL verify no future information is present and reject contaminated datasets

2.3.3 WHEN feature columns are joined across storage and scoring pipelines THEN strict feature column name alignment SHALL be enforced with validation assertions

#### 3.3 Unchanged Behavior (Regression Prevention)

3.3.1 WHEN multi-day lag features (e.g., 5-day moving averages) are computed THEN the system SHALL CONTINUE TO calculate correctly with appropriate lookback windows

3.3.2 WHEN historical backtesting is performed on properly lagged data THEN the system SHALL CONTINUE TO produce accurate performance metrics

3.3.3 WHEN real-time scoring uses lagged features THEN the system SHALL CONTINUE TO generate predictions using only past information

### 4. Ghost Features & Feature Store Defects

#### 4.1 Current Behavior (Defect)

1.4.1 WHEN LightGBM models declare 11 features but only 6 are computed (frac_diff_close d=0.35, macd_norm, rsi_14, log_return, range_vol are missing) THEN silent zero-fills (0.0) are applied across all historical rows without error notification

1.4.2 WHEN feature computation pipelines use .fillna(0.0) on missing features THEN failures are masked and models train on invalid zero-filled data producing unreliable predictions

1.4.3 WHEN feature completeness validation is absent before model training THEN models are trained on incomplete feature sets without detection

1.4.4 WHEN frac_diff_close, macd_norm, rsi_14, log_return, and range_vol are referenced in model configuration THEN no computation code executes resulting in ghost features

#### 4.2 Expected Behavior (Correct)

2.4.1 WHEN LightGBM models declare features THEN explicit computation SHALL be implemented for all declared features: frac_diff_close (d=0.35), macd_norm, rsi_14, log_return, range_vol

2.4.2 WHEN feature computation encounters missing data or computation failures THEN strict Pandera schema assertions SHALL raise runtime exceptions instead of silent zero-fills

2.4.3 WHEN models prepare for training THEN feature completeness validation SHALL verify all declared features are computed and raise exceptions for missing features

2.4.4 WHEN feature pipelines execute THEN explicit logging SHALL record successful computation of each feature with sample statistics for verification

#### 4.3 Unchanged Behavior (Regression Prevention)

3.4.1 WHEN the 6 currently computed features (volume, price ratios, etc.) are calculated THEN the system SHALL CONTINUE TO produce correct values

3.4.2 WHEN legitimate NULL values exist in raw data (e.g., first-day IPO with no prior price) THEN the system SHALL CONTINUE TO handle edge cases appropriately

3.4.3 WHEN feature engineering adds new valid features THEN the system SHALL CONTINUE TO support feature additions with proper computation

### 5. Model Governance & Optimizer Fail-Closed Defects

#### 5.1 Current Behavior (Defect)

1.5.1 WHEN scipy.optimize.minimize executes Hawkes MLE optimization and fails (res.success = False) THEN failures are unchecked and 1e9 penalty values are consumed as valid parameters

1.5.2 WHEN Chronos-Bolt model execution encounters errors THEN silent downgrade to GBM fallback occurs without alerts, status flags, or logging

1.5.3 WHEN Triple-Barrier labeling encounters zero-volatility scrips THEN profit_barrier = 0.0 causes every positive tick to be labeled as successful trade distorting labels

1.5.4 WHEN Isolation Forest anomaly detection is fitted THEN fitting occurs on dynamic test batches instead of clean historical distributions causing distribution shift

1.5.5 WHEN prediction outputs are generated using fallback models THEN no metadata indicates whether predictions came from LIVE_CHRONOS or GBM_FALLBACK

#### 5.2 Expected Behavior (Correct)

2.5.1 WHEN scipy.optimize.minimize executes Hawkes MLE optimization THEN res.success SHALL be asserted as True with explicit failover to safe defaults on failure

2.5.2 WHEN Chronos-Bolt model execution encounters errors THEN explicit alerts SHALL fire and status metadata SHALL indicate GBM_FALLBACK mode

2.5.3 WHEN Triple-Barrier labeling encounters scrips with calculated volatility THEN profit_barrier SHALL be computed as max(volatility, min_vol) * 2.0 to enforce minimum volatility floors

2.5.4 WHEN Isolation Forest anomaly detection is fitted THEN fitting SHALL occur on clean historical distributions, not dynamic test batches

2.5.5 WHEN prediction outputs are generated THEN explicit status metadata SHALL distinguish LIVE_CHRONOS vs GBM_FALLBACK in all prediction outputs

#### 5.3 Unchanged Behavior (Regression Prevention)

3.5.1 WHEN scipy.optimize.minimize succeeds with valid convergence THEN the system SHALL CONTINUE TO use optimized Hawkes parameters correctly

3.5.2 WHEN Chronos-Bolt models execute successfully THEN the system ASHALL CONTINUE TO produce predictions without fallback

3.5.3 WHEN scrips have sufficient volatility for Triple-Barrier labeling THEN the system SHALL CONTINUE TO generate accurate labels

3.5.4 WHEN Isolation Forest is fitted on clean historical data THEN the system SHALL CONTINUE TO detect anomalies correctly

3.5.5 WHEN prediction pipelines operate without errors THEN the system SHALL CONTINUE TO produce timely predictions for all active scrips
