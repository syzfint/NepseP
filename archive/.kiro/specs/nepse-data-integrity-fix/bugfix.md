# Bugfix Requirements Document

## Introduction

The NEPSE quantitative trading system is experiencing severe model signal distortion and false alpha generation caused by five critical categories of bugs spanning data corruption, temporal integrity violations, feature computation failures, model validation gaps, and system concurrency issues. This comprehensive fix addresses all categories in a unified refactor to restore data integrity and system reliability across the entire quantitative engine pipeline.

## Bug Analysis

### Current Behavior (Defect)

**1. Storage & Concurrency Failures**

1.1 WHEN multiple processes attempt concurrent DuckDB operations THEN the system experiences file-locking conflicts and crashes
1.2 WHEN FastAPI routes execute synchronous Pandas transformations THEN the event loop blocks causing up to 8.42s latency spikes
1.3 WHEN Parquet files are written non-atomically THEN streaming daemon crashes occur during concurrent access

**2. Broker Data Corruption & Failed Anti-Wash Filtering**

1.4 WHEN anti-wash trade filters process API schema data THEN column name mismatches (expecting Buyer/Seller vs buyerMemberId/sellerMemberId) cause NULL evaluations allowing 100% wash trades through
1.5 WHEN broker data is missing from API responses THEN synthetic broker IDs are generated using modulo math ((contract_id % 50) + 1) corrupting institutional metrics
1.6 WHEN timestamp data is unavailable THEN wallclock retrieval times are substituted destroying intraday tick sequencing

**3. Same-Day Look-Ahead Leakage**

1.7 WHEN EOD broker concentration signals are joined to price bars THEN same-day date equality joins (ON date = date) leak future institutional accumulation data into training sets
1.8 WHEN models train with contaminated features THEN false alpha generation occurs due to forward-looking information

**4. Ghost Features & Silent Zero-Fills**

1.9 WHEN LightGBM training processes feature vectors THEN 5 out of 11 declared features (frac_diff_close d=0.35, macd_norm, rsi_14) are never computed in feature store
1.10 WHEN missing features are detected during training THEN silent zero-fills (0.0) are applied across all historical rows without error notification

**5. Un-Validated Optimizer & Model Fallbacks**

1.11 WHEN Hawkes process scipy.optimize.minimize operations fail THEN res.success status is unchecked allowing consumption of 1e9 penalty values and invalid branching ratios
1.12 WHEN Chronos-Bolt deep learning predictions encounter errors THEN silent downgrade to Geometric Brownian Motion occurs without alerts
1.13 WHEN Triple-Barrier labeling processes suspended or zero-volatility scrips THEN profit_barrier evaluates to 0.0 artificially labeling every positive tick as successful (meta_label = 1)

### Expected Behavior (Correct)

**1. Storage & Concurrency Management**

2.1 WHEN multiple processes require database access THEN the system SHALL use centralized DuckDB connection pooling with single-writer threadpool to prevent file-locking conflicts
2.2 WHEN FastAPI routes handle CPU-bound operations THEN the system SHALL wrap synchronous operations in async thread executors to prevent event loop blocking
2.3 WHEN writing Parquet files THEN the system SHALL use atomic operations (.tmp write -> rename) to ensure consistency during concurrent access

**2. Broker Data Integrity & Anti-Wash Filtering**

2.4 WHEN processing broker trade data THEN the system SHALL correctly map API schema fields (buyerMemberId -> buyer_broker_id, sellerMemberId -> seller_broker_id)
2.5 WHEN evaluating wash trade conditions THEN the system SHALL enforce strict filtering (buyer_broker_id != seller_broker_id) to block all wash trades
2.6 WHEN API responses contain incomplete broker data THEN the system SHALL fail-fast with explicit logging rather than generating synthetic data

**3. Temporal Integrity Enforcement**

2.7 WHEN joining EOD broker features to price data THEN the system SHALL enforce mandatory 1-session lag (date - INTERVAL 1 DAY) to prevent look-ahead leakage
2.8 WHEN training models THEN the system SHALL ensure all features contain only historical data available at prediction time

**4. Complete Feature Computation**

2.9 WHEN building feature vectors THEN the system SHALL explicitly compute all declared features (frac_diff_close d=0.35, macd_norm, rsi_14) in the feature pipeline
2.10 WHEN missing features are detected THEN the system SHALL raise runtime exceptions rather than silent zero-filling

**5. Model Validation & Error Handling**

2.11 WHEN Hawkes process optimization completes THEN the system SHALL assert res.success == True and trigger explicit failover on convergence failure
2.12 WHEN Chronos model predictions degrade THEN the system SHALL attach explicit status metadata to enable downstream detection of fallback modes
2.13 WHEN computing Triple-Barrier labels THEN the system SHALL apply minimum volatility floors (profit_barrier = max(volatility, min_vol) * 2.0) to prevent target inflation

### Unchanged Behavior (Regression Prevention)

**1. Core Trading Logic Preservation**

3.1 WHEN legitimate (non-wash) trades are processed THEN the system SHALL CONTINUE TO apply all existing trading logic and signal generation
3.2 WHEN valid broker concentration metrics are available THEN the system SHALL CONTINUE TO generate institutional flow signals as designed
3.3 WHEN models operate with complete, properly computed features THEN the system SHALL CONTINUE TO produce the same prediction outputs

**2. API Compatibility**

3.4 WHEN external systems query NEPSE data APIs THEN the system SHALL CONTINUE TO return responses in the same format and schema
3.5 WHEN UI components request market data THEN the system SHALL CONTINUE TO serve responses within acceptable latency bounds (sub-second)

**3. Historical Data Integrity**

3.6 WHEN accessing historical price and volume data THEN the system SHALL CONTINUE TO maintain exact numerical precision and temporal ordering
3.7 WHEN computing technical indicators on clean datasets THEN the system SHALL CONTINUE TO produce identical mathematical results
3.8 WHEN model training uses properly lagged features THEN the system SHALL CONTINUE TO achieve the same or better prediction accuracy

**4. System Monitoring & Alerting**

3.9 WHEN system performance metrics are within normal ranges THEN the system SHALL CONTINUE TO operate without generating false alerts
3.10 WHEN legitimate model optimization succeeds THEN the system SHALL CONTINUE TO apply optimized parameters without intervention