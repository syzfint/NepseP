import os
import glob
import numpy as np
import pandas as pd
import lightgbm as lgb
from scipy.stats import norm

BASE_DIR = r"c:\Users\achar\Downloads\neps"
FEATURE_DIR = os.path.join(BASE_DIR, "03_feature_store")
PROCESSED_DIR = os.path.join(BASE_DIR, "02_processed_parquet")

def run_remediation_benchmark():
    print("=" * 85)
    print("      APEXMARKETENGINE: INCREMENTAL REMEDIATION BENCHMARK SUITE")
    print("=" * 85)

    # 1. Load Data
    master_path = os.path.join(PROCESSED_DIR, "market_master_union.parquet")
    tech_path = os.path.join(FEATURE_DIR, "technical_indicators.parquet")

    if not os.path.exists(tech_path):
        print(f"Error: {tech_path} not found!")
        return

    df = pd.read_parquet(tech_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # 2. Daily Price Series & Targets
    df["future_10d_close"] = df.groupby("ticker")["close"].shift(-10)
    df["target_10d_return"] = ((df["future_10d_close"] - df["close"]) / df["close"]).clip(-0.30, 0.50)

    feature_cols = [
        "frac_diff_close", "log_return", "sma_20", "sma_50", 
        "macd", "macd_signal", "rsi_14", "bb_upper", "bb_lower", "volatility_20",
        "tfidf_weight", "textblob_polarity", "textblob_subjectivity"
    ]

    clean_df = df.dropna(subset=["target_10d_return"]).copy()
    for col in feature_cols:
        clean_df[col] = clean_df[col].replace([np.inf, -np.inf], np.nan).fillna(0)

    # 3. Model Training
    model = lgb.LGBMRegressor(n_estimators=180, learning_rate=0.03, num_leaves=31, random_state=42, verbose=-1, n_jobs=-1)
    model.fit(clean_df[feature_cols], clean_df["target_10d_return"])

    clean_df["predicted_score"] = model.predict(clean_df[feature_cols])

    # 4. Generate Full Daily Equity Curve
    unique_dates = sorted(clean_df["date"].unique())
    rebalance_dates = set(unique_dates[::5])

    current_portfolio = []
    daily_nav_raw = []
    daily_nav_fee = []
    daily_nav_cgt = []

    nav_raw = 1.0
    nav_fee = 1.0
    nav_cgt = 1.0

    accumulated_loss = 0.0  # CGT loss offset tracking

    TOP_K_BUY = 5
    TOP_K_HOLD = 15

    # Tiered Commission Function
    def get_broker_fee(trade_val):
        if trade_val <= 50000:
            rate = 0.0040
        elif trade_val <= 500000:
            rate = 0.0037
        elif trade_val <= 2000000:
            rate = 0.0034
        else:
            rate = 0.0030
        return rate + 0.00015  # Plus SEBON 0.015%

    results = []

    for d in unique_dates:
        sub = clean_df[clean_df["date"] == d].copy()
        
        # Check rebalance
        if d in rebalance_dates and len(sub) >= TOP_K_BUY:
            sub["rank_pos"] = sub["predicted_score"].rank(ascending=False, method="min")
            top_candidates = sub.sort_values("predicted_score", ascending=False).head(TOP_K_BUY)["ticker"].tolist()

            if not current_portfolio:
                new_portfolio = top_candidates[:TOP_K_BUY]
            else:
                new_portfolio = []
                for t in current_portfolio:
                    t_row = sub[sub["ticker"] == t]
                    if not t_row.empty and t_row["rank_pos"].values[0] <= TOP_K_HOLD:
                        new_portfolio.append(t)

                for c in top_candidates:
                    if len(new_portfolio) >= TOP_K_BUY:
                        break
                    if c not in new_portfolio:
                        new_portfolio.append(c)

                new_portfolio = new_portfolio[:TOP_K_BUY]

            swaps = len(set(new_portfolio) - set(current_portfolio))
            current_portfolio = new_portfolio
        else:
            swaps = 0

        # Calculate daily return of current portfolio holdings
        if current_portfolio and not sub.empty:
            held = sub[sub["ticker"].isin(current_portfolio)]
            if not held.empty:
                daily_ret = held["log_return"].mean()
            else:
                daily_ret = 0.0
        else:
            daily_ret = 0.0

        # Raw NAV
        nav_raw *= (1.0 + daily_ret)
        
        # Fee-adjusted NAV (applied on swaps)
        turnover_frac = swaps / float(TOP_K_BUY)
        fee_penalty = turnover_frac * get_broker_fee(100000)
        nav_fee *= (1.0 + daily_ret - fee_penalty)

        # CGT-adjusted NAV (Per-trade CGT withholding with loss offset)
        if daily_ret < 0:
            accumulated_loss += abs(daily_ret)
            cgt_deduction = 0.0
        else:
            taxable_gain = max(0.0, daily_ret - accumulated_loss)
            accumulated_loss = max(0.0, accumulated_loss - daily_ret)
            cgt_deduction = taxable_gain * 0.10  # 10% Corporate CGT

        nav_cgt *= (1.0 + daily_ret - fee_penalty - cgt_deduction)

        results.append({
            "date": d,
            "nav_raw": nav_raw,
            "nav_fee": nav_fee,
            "nav_cgt": nav_cgt,
            "daily_ret": daily_ret
        })

    res_df = pd.DataFrame(results)

    # 5. Compute Metrics for Before/After Table
    def compute_metrics(nav_series, daily_rets):
        tot_ret = (nav_series.iloc[-1] - 1.0) * 100
        ann_factor = np.sqrt(252)
        sharpe = (daily_rets.mean() / (daily_rets.std() + 1e-8)) * ann_factor
        
        running_max = np.maximum.accumulate(nav_series)
        dd = (nav_series - running_max) / running_max
        mdd = dd.min() * 100
        
        wins = daily_rets[daily_rets > 0]
        win_rate = (len(wins) / (len(daily_rets[daily_rets != 0]) + 1e-8)) * 100
        return tot_ret, sharpe, mdd, win_rate

    raw_ret, raw_sharpe, raw_mdd, raw_win = compute_metrics(res_df["nav_raw"], res_df["daily_ret"])
    fee_ret, fee_sharpe, fee_mdd, fee_win = compute_metrics(res_df["nav_fee"], res_df["daily_ret"])
    cgt_ret, cgt_sharpe, cgt_mdd, cgt_win = compute_metrics(res_df["nav_cgt"], res_df["daily_ret"])

    # Equal Weight Buy & Hold Benchmark
    ew_df = clean_df.groupby("date")["log_return"].mean().reset_index()
    ew_nav = np.cumprod(1 + ew_df["log_return"])
    ew_ret, ew_sharpe, ew_mdd, ew_win = compute_metrics(pd.Series(ew_nav), ew_df["log_return"])

    print("\n" + "=" * 85)
    print("           INCREMENTAL REMEDIATION BEFORE/AFTER BENCHMARK TABLE")
    print("=" * 85)
    print(f"{'Remediation Step / Model':<35} | {'Net Return':<12} | {'Sharpe':<8} | {'Daily MDD':<10} | {'Win Rate':<8}")
    print("-" * 85)
    print(f"{'0. Equal-Weight Buy & Hold (Bench)':<35} | {ew_ret:>+11.2f}% | {ew_sharpe:>7.2f} | {ew_mdd:>9.2f}% | {ew_win:>7.2f}%")
    print(f"{'1. Raw Strategy (Daily MTM NAV)':<35} | {raw_ret:>+11.2f}% | {raw_sharpe:>7.2f} | {raw_mdd:>9.2f}% | {raw_win:>7.2f}%")
    print(f"{'2. Tiered Broker Fee + DP Charge':<35} | {fee_ret:>+11.2f}% | {fee_sharpe:>7.2f} | {fee_mdd:>9.2f}% | {fee_win:>7.2f}%")
    print(f"{'3. Per-Trade 10% CGT (Loss Offset)':<35} | {cgt_ret:>+11.2f}% | {cgt_sharpe:>7.2f} | {cgt_mdd:>9.2f}% | {cgt_win:>7.2f}%")
    print("=" * 85 + "\n")

    # 6. Universe Count by Year (Survivorship Sensitivity Inspection)
    clean_df["year"] = clean_df["date"].dt.year
    year_counts = clean_df.groupby("year")["ticker"].nunique()
    print("UNIVERSE TICKER COUNT BY YEAR (SURVIVORSHIP INSPECTION):")
    print(year_counts.to_string())
    print("=" * 85 + "\n")

if __name__ == "__main__":
    run_remediation_benchmark()
