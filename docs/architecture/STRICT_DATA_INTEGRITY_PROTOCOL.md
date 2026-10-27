# STRICT DATA & PRICE INTEGRITY PROTOCOL (`APEX WEALTH` & `NEPSE` WORKSPACE)

## 1. Zero-Synthetic-Price Guarantee (`NEVER_SYNTHESIZE_PRICE`)
- **Prohibited:** Random number generators (`np.random`), trigonometric/sine-wave price ticks (`math.sin` / `math.cos`), hardcoded placeholder prices, or unverified mock quotes.
- **Permitted Price Sources Only:**
  1. `REAL_NEPSE_HISTORICAL_CLOSE` — Verified historical NEPSE closing trade rates from `01_raw_data/nepse_floorsheet_*.json` and daily OHLCV closes from `nepse_data_all/*.csv` (with exact `as_of_date` provenance).
  2. `USER_ENTERED_PRICE` — Prices explicitly entered or imported by the user in Batch Add, Quick Add, CSV Import, or the Stock Tracker LTP Editor.

## 2. Explicit Prediction Disclosure (`EXPLICIT_PREDICTION_DISCLOSURE`)
- **Strict Separation:** Model predictions and optimization targets must never be mixed with or displayed as actual market prices (`LTP`).
- **Mandatory Tagging:** Every forecast or model output (`Chronos/Kronos 5-Day p10/p50/p90 Price Forecast`, `1-Week Return Forecast`, `Schur-RA-HRP Target Weight`, `Projected VaR_99`) must include:
  - Backend payload fields: `"is_prediction": true`, `"is_synthetic": false`, `"disclosure_label": "EXPLICIT MODEL PREDICTION — NOT ACTUAL MARKET PRICE"`, `"model_name"`, and `"horizon"`.
  - Frontend UI badge: **`[EXPLICIT MODEL PREDICTION]`** clearly distinguishing forecasted values from actual historical/user-fed market prices.
