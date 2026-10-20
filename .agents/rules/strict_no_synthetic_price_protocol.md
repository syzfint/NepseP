# STRICT DATA & PRICE INTEGRITY PROTOCOL (MANDATORY INVARIANT)

## Rule 1: Absolute Prohibition of Synthetic Prices & Synthetic Returns (`ZERO_SYNTHETIC_PRICE`)
1. **Never fabricate, hardcode, or randomly generate stock prices (`LTP`, `open`, `high`, `low`, `close`) or return time-series (`np.random`, sine waves, Brownian motion, Gaussian noise).**
2. Every market price displayed or used in portfolio valuation **MUST** originate strictly from one of two verified non-synthetic sources:
   - **`REAL_NEPSE_HISTORICAL_CLOSE`**: Verified historical closing trade/price from official NEPSE raw datasets (`01_raw_data/nepse_floorsheet_*.json` or `nepse_data_all/*.csv`), accompanied by the exact `businessDate` and source file.
   - **`USER_ENTERED_PRICE`**: An explicit price manually fed or edited by the user, tagged as `USER_ENTERED_PRICE`.
3. Every historical return matrix used for covariance shrinkage (Ledoit-Wolf) and portfolio optimization (Schur-RA-HRP) **MUST** be computed from real historical daily closes in `nepse_data_all/*.csv`.
4. When the NEPSE market is closed or no live broker socket is connected, prices must remain **100% static** at their last verified close or user-fed price. Never run background tick mutators.

## Rule 2: Mandatory Explicit Labeling of Predictions & Forecasts (`EXPLICIT_PREDICTION_DISCLOSURE`)
1. **Never present a model prediction, forecasted price, or target allocation weight as an actual market price.**
2. Any value produced by a quantitative or machine-learning model — including:
   - 5-Day / 1-Week Price or Return Forecasts (`p10_5d`, `p50_5d`, `p90_5d`, `exp_return_5d_pct`, `ret_1w_pct` from `NEPSE_MASTER_INTEGRATED_OUTPUT.json` or `NEPSE_OCT5_PREDICTION.json`)
   - Schur-RA-HRP Target Allocation Weights (`w_i^*`) and Ranks (`R_i(t)`)
   - Projected Risk Metrics (`VaR_99`, `CVaR_1d`, Projected Health Delta)
   **MUST** carry:
   - `is_prediction: true` in all API responses
   - `disclosure_label: "[EXPLICIT MODEL PREDICTION — NOT ACTUAL MARKET PRICE]"`
   - A visible **`[PREDICTION]`** or **`[MODEL FORECAST]`** badge in the UI stating the model name and forecast horizon.
