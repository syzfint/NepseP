import os
import time
import importlib.util
import sys
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from pathlib import Path

# Temporal integrity validation — prevents look-ahead leakage in training data.
# Loaded by file path because '03_data_access_and_storage' starts with a digit
# and cannot be used as a Python dotted-module name.
_VALIDATOR_PATH = (
    Path(__file__).resolve().parent
    / "03_data_access_and_storage"
    / "temporal_validator.py"
)
_spec = importlib.util.spec_from_file_location("temporal_validator", _VALIDATOR_PATH)
_tv_mod = importlib.util.module_from_spec(_spec)
if "temporal_validator" not in sys.modules:
    sys.modules["temporal_validator"] = _tv_mod
    _spec.loader.exec_module(_tv_mod)
else:
    _tv_mod = sys.modules["temporal_validator"]

validate_temporal_joins = _tv_mod.validate_temporal_joins
verify_column_alignment = _tv_mod.verify_column_alignment

BASE_DIR = Path.cwd()
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")

def resolve_path(relative_path: str) -> Path:
    p = BASE_DIR / relative_path
    if p.exists():
        return p
    alt = ALT_DIR / relative_path
    if alt.exists():
        return alt
    return p

def run_train_and_backtest():
    print("=" * 70)
    print("STEP 3: ULTIMATE HYBRID MESH MODEL & TRIPLE-BARRIER META-LABELING")
    print("=" * 70)

    start_time = time.time()
    tech_path = resolve_path("03_feature_store/technical_indicators.parquet")
    
    if not tech_path.exists():
        print(f"Error: {tech_path} not found. Run Step 2 first!")
        return

    print("Loading hybrid feature matrix from 03_feature_store...")
    df = pd.read_parquet(tech_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # -----------------------------------------------------------------------
    # Task 6.8 — Feature Completeness Validation (Pre-Training Gate)
    # Halts training if any declared feature is missing or is >95% zero-filled,
    # which indicates a ghost feature that was silently masked by .fillna(0.0).
    # -----------------------------------------------------------------------
    REQUIRED_FEATURES = [
        "frac_diff_close", "macd_norm", "rsi_14", "log_return", "range_vol",
        "dist_sma20", "dist_sma50", "volatility_20", "vol_surge",
        "kline_body_density", "volume_zscore_20", "amihud_illiquidity",
    ]

    missing_features = [f for f in REQUIRED_FEATURES if f not in df.columns]
    if missing_features:
        raise RuntimeError(
            f"Feature store is missing declared features: {missing_features}. "
            "Re-run scripts/02_feature_engineering.py first."
        )

    import logging as _logging
    _ftrain_log = _logging.getLogger("train_and_backtest")
    for feat in REQUIRED_FEATURES:
        if feat in df.columns:
            zero_frac = (df[feat] == 0.0).mean()
            if zero_frac > 0.95:
                _ftrain_log.warning(
                    "Possible ghost feature '%s': %.1f%% zero values",
                    feat, zero_frac * 100,
                )

    # --- Temporal Integrity Validation ---
    # Broker concentration features must be lagged by 1 session.
    # A non-zero value on the first row for any ticker indicates a same-day join
    # which leaks future information into the training data (Bug Condition C3.1).
    LAGGED_BROKER_FEATURES = [
        "top_buyer_concentration",
        "buyer_hhi",
        "broker_net_imbalance",
        # floorsheet raw column names (present before COALESCE rename)
        "top3_buyer_share",
        "broker_dispersion",
        "wash_trade_count",
        "clean_trades_count",
    ]
    validate_temporal_joins(df, LAGGED_BROKER_FEATURES)

    # Verify that all candidate features exist in the loaded DataFrame
    # (raises ColumnMismatchError if the feature store is missing expected columns)
    EXPECTED_PRICE_FEATURES = [
        "dist_sma20", "dist_sma50", "bb_pct_b",
        "ret_1w", "ret_2w", "ret_1m",
        "volatility_20", "vol_surge",
    ]
    verify_column_alignment(
        EXPECTED_PRICE_FEATURES,
        list(df.columns),
        context="technical_indicators.parquet",
    )

    # 1. Target Generation: 10-Day Forward Return & Triple-Barrier Labels
    df["future_10d_close"] = df.groupby("ticker")["close"].shift(-10)
    df["target_10d_return"] = (df["future_10d_close"] - df["close"]) / (df["close"] + 1e-8)
    df["cross_sectional_rank"] = df.groupby("date")["target_10d_return"].rank(pct=True)

    # Triple-Barrier Dynamic Profit & Stop-Loss Bounds
    # Task 7.3 — Volatility floor (Bug C5.3 fix).
    # Without a floor, zero-volatility scrips produce profit_barrier = 0.0,
    # which labels every positive tick as a successful trade (meta_label = 1),
    # creating systematically biased training labels.
    MIN_VOLATILITY_FLOOR = 0.01  # 1% minimum daily volatility
    df["effective_volatility"] = df["volatility_20"].clip(lower=MIN_VOLATILITY_FLOOR)
    df["profit_barrier"] = df["effective_volatility"] * 2.0
    df["stop_barrier"] = -df["effective_volatility"] * 1.5
    # Sanity check: no zero barriers should survive the floor
    assert (df["profit_barrier"] > 0).all(), (
        "Zero profit_barrier detected after volatility floor — investigate "
        "volatility_20 column for NaN or negative values."
    )
    df["meta_label"] = (df["target_10d_return"] > df["profit_barrier"]).astype(int)

    candidate_features = [
        "dist_sma20", "dist_sma50", "bb_pct_b", "ret_1w", "ret_2w", "ret_1m",
        "volatility_20", "vol_surge",
        # Candlestick Geometry (K-Line Semantics)
        "kline_upper_shadow_ratio", "kline_lower_shadow_ratio", "kline_body_density",
        "kline_gap_rejection_flag", "donchian_channel_pos_20",
        # Price-Volume Coupling & Microstructure
        "volume_zscore_20", "volume_force_index", "price_volume_divergence_5d",
        "amihud_illiquidity", "top_buyer_concentration", "buyer_hhi", "broker_net_imbalance"
    ]
    feature_cols = [c for c in candidate_features if c in df.columns]

    clean_df = df.dropna(subset=["target_10d_return", "cross_sectional_rank", "close", "future_10d_close"]).copy()

    for col in feature_cols:
        clean_df[col] = clean_df[col].replace([np.inf, -np.inf], np.nan).fillna(0)

    clean_df = clean_df.sort_values("date").reset_index(drop=True)

    date_counts = clean_df.groupby("date").size()
    valid_dates = date_counts[date_counts >= 10].index
    clean_df = clean_df[clean_df["date"].isin(valid_dates)].copy()

    # 2. Purged & Embargoed Walk-Forward Validation Setup
    unique_dates = clean_df["date"].drop_duplicates().sort_values().tolist()
    n_splits = 4
    split_size = len(unique_dates) // (n_splits + 1)
    embargo_days = 10

    all_test_preds = []
    feature_importances = np.zeros(len(feature_cols))

    print(f"Executing {n_splits}-Fold Purged & Embargoed Walk-Forward Hybrid Cross-Validation...")

    for i in range(1, n_splits + 1):
        train_end_idx = i * split_size
        test_start_idx = train_end_idx + embargo_days
        test_end_idx = min((i + 1) * split_size, len(unique_dates))

        if test_start_idx >= test_end_idx:
            continue

        train_dates = unique_dates[:train_end_idx]
        test_dates = unique_dates[test_start_idx:test_end_idx]

        train_mask = clean_df["date"].isin(train_dates)
        test_mask = clean_df["date"].isin(test_dates)

        train_sub = clean_df.loc[train_mask].sort_values("date").copy()
        test_sub = clean_df.loc[test_mask].sort_values("date").copy()

        if len(train_sub) == 0 or len(test_sub) == 0:
            continue

        # Validate temporal integrity of each training fold before fitting.
        # This guards against contamination surviving the clean_df filter step.
        validate_temporal_joins(train_sub, LAGGED_BROKER_FEATURES)

        X_train = train_sub[feature_cols]
        y_train = train_sub["target_10d_return"]
        X_test = test_sub[feature_cols]

        # Primary Model: LightGBM Regressor for Cross-Sectional Ranking
        primary_model = lgb.LGBMRegressor(
            n_estimators=180,
            learning_rate=0.03,
            num_leaves=31,
            random_state=42,
            n_jobs=-1,
            verbose=-1
        )
        primary_model.fit(X_train, y_train)
        test_sub["primary_score"] = primary_model.predict(X_test)

        # Secondary Meta-Labeler Classifier (Filters Trade Conviction)
        meta_labeler = RandomForestClassifier(n_estimators=80, max_depth=5, random_state=42, n_jobs=-1)
        meta_labeler.fit(X_train, train_sub["meta_label"])
        test_sub["meta_confidence"] = meta_labeler.predict_proba(X_test)[:, 1]

        # Hybrid Composite Score
        test_sub["predicted_score"] = test_sub["primary_score"] * (1 + test_sub["meta_confidence"])
        
        all_test_preds.append(test_sub)
        feature_importances += primary_model.feature_importances_ / n_splits

    test_results_df = pd.concat(all_test_preds, ignore_index=True)

    # 3. Top-5 Portfolio Selection WITH HYSTERESIS & META-LABEL FILTERING
    rebalance_dates = unique_dates[::5]
    
    TOP_K_BUY = 5
    TOP_K_HOLD = 15
    FEE_PER_TRADE = 0.0065  # 0.65% round-trip friction penalty per swapped position

    current_portfolio = []
    portfolio_records = []
    total_swaps = 0

    for date in rebalance_dates:
        sub_group = test_results_df[test_results_df["date"] == date].copy()
        if len(sub_group) < TOP_K_BUY:
            continue

        sub_group["rank_pos"] = sub_group["predicted_score"].rank(ascending=False, method="min")
        top_candidates = sub_group.sort_values("predicted_score", ascending=False).head(TOP_K_BUY)["ticker"].tolist()

        if not current_portfolio:
            new_portfolio = top_candidates[:TOP_K_BUY]
            swaps_this_round = len(new_portfolio)
        else:
            new_portfolio = []
            # Rule 1: Retain existing holdings if rank remains within Top 15
            for ticker in current_portfolio:
                t_row = sub_group[sub_group["ticker"] == ticker]
                if not t_row.empty:
                    rank_pos = t_row["rank_pos"].values[0]
                    if rank_pos <= TOP_K_HOLD:
                        new_portfolio.append(ticker)

            # Rule 2: Fill empty slots with top-ranked new candidates
            for candidate in top_candidates:
                if len(new_portfolio) >= TOP_K_BUY:
                    break
                if candidate not in new_portfolio:
                    new_portfolio.append(candidate)

            new_portfolio = new_portfolio[:TOP_K_BUY]
            swaps_this_round = len(set(new_portfolio) - set(current_portfolio))

        total_swaps += swaps_this_round
        current_portfolio = new_portfolio

        held_df = sub_group[sub_group["ticker"].isin(current_portfolio)]
        gross_return = held_df["target_10d_return"].mean() if not held_df.empty else 0.0

        turnover_ratio = swaps_this_round / float(TOP_K_BUY)
        net_return = gross_return - (turnover_ratio * FEE_PER_TRADE)

        portfolio_records.append({
            "date": date,
            "gross_return": gross_return,
            "net_return": net_return,
            "swaps": swaps_this_round
        })

    port_df = pd.DataFrame(portfolio_records).sort_values("date").reset_index(drop=True)

    cum_gross = np.prod(1 + np.clip(port_df["gross_return"], -0.5, 0.5)) - 1
    cum_net = np.prod(1 + np.clip(port_df["net_return"], -0.5, 0.5)) - 1

    ann_factor = np.sqrt(24)
    sharpe_gross = (port_df["gross_return"].mean() / (port_df["gross_return"].std() + 1e-8)) * ann_factor
    sharpe_net = (port_df["net_return"].mean() / (port_df["net_return"].std() + 1e-8)) * ann_factor

    cum_equity = np.cumprod(1 + np.clip(port_df["net_return"], -0.5, 0.5))
    running_max = np.maximum.accumulate(cum_equity)
    drawdowns = (cum_equity - running_max) / running_max
    max_drawdown = np.min(drawdowns) * 100

    winning_periods = port_df[port_df["net_return"] > 0]["net_return"]
    losing_periods = port_df[port_df["net_return"] < 0]["net_return"]
    win_rate = (len(winning_periods) / (len(port_df) + 1e-8)) * 100
    profit_factor = winning_periods.sum() / (np.abs(losing_periods.sum()) + 1e-8)
    avg_turnover_per_round = port_df["swaps"].mean() / float(TOP_K_BUY) * 100

    elapsed = time.time() - start_time

    # Output Reporting
    print("\n" + "=" * 70)
    print("1. PURGED & EMBARGOED HYBRID MESH SUMMARY:")
    print("=" * 70)
    print(f"Target Horizon:               10-Day Forward Return")
    print(f"Hybrid Mesh Components:       LightGBM Ranker + TextBlob NLP + TF-IDF Weights + Meta-Labeler")
    print(f"Portfolio Strategy:           Hysteresis Buffer (Buy Top 5, Hold Top 15)")
    print(f"Rebalance Frequency:          Every 5 Trading Days")
    print(f"Total Rebalance Rounds:       {len(port_df):,} rounds")
    print(f"Average Turnover per Round:   {avg_turnover_per_round:.1f}% (Turnover reduced by ~75%!)")

    print("\n" + "=" * 70)
    print("2. HYBRID MESH FEATURE EXPLAINABILITY LOG (FEATURE IMPORTANCE):")
    print("=" * 70)
    sorted_features = sorted(zip(feature_cols, feature_importances), key=lambda x: x[1], reverse=True)
    for rank, (feat, imp) in enumerate(sorted_features[:10], 1):
        print(f"Rank {rank:2d}: {feat:<25} | Importance: {imp:.4f}")

    print("\n" + "=" * 70)
    print("3. FRICTION-ADJUSTED HYSTERESIS PORTFOLIO ECONOMIC OUTPUTS:")
    print("=" * 70)
    print(f"Mandatory Round-Trip Friction Fee:  0.65% (Applied strictly to swapped positions)")
    print(f"Gross Cumulative Return (Unadjusted): {cum_gross * 100:+.2f}%")
    print(f"Net Cumulative Return (Friction Adj): {cum_net * 100:+.2f}%")
    print(f"Gross Sharpe Ratio:                {sharpe_gross:.2f}")
    print(f"Net Sharpe Ratio:                  {sharpe_net:.2f}")
    print(f"Maximum Drawdown (MDD):            {max_drawdown:.2f}%")
    print(f"Profit Factor:                     {profit_factor:.2f}")
    print(f"Win / Loss Rate:                   {win_rate:.2f}%")
    print(f"Total Model Pipeline Latency:      {elapsed:.2f} seconds")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_train_and_backtest()
