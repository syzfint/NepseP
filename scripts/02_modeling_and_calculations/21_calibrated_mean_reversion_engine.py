import os
import warnings
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
import statsmodels.api as sm

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"

def run_calibrated_engine():
    print("=" * 85)
    print("      CALIBRATING NEPSE MEAN-REVERSION FEATURE ENGINE (RANK IC & T-STATS)")
    print("=" * 85)

    master_path = os.path.join(PROCESSED_DIR, "market_master_union.parquet")
    df = pd.read_parquet(master_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= "2010-01-01"].sort_values(["ticker", "date"]).reset_index(drop=True)

    # 1. Correct Backward Price Adjustment
    ticker_arr = df["ticker"].values
    close_arr = df["close"].values

    prev_close = df.groupby("ticker")["close"].shift(1).fillna(df["close"]).values
    raw_ratio = np.where(prev_close > 0, close_arr / prev_close, 1.0)
    adj_factor = np.where((raw_ratio < 0.88) & (raw_ratio > 0.05), raw_ratio, 1.0)
    log_factor = np.log(np.maximum(adj_factor, 1e-8))

    rev_ticker = ticker_arr[::-1]
    rev_log_factor = log_factor[::-1]

    ticker_starts = np.ones(len(rev_ticker), dtype=bool)
    ticker_starts[1:] = (rev_ticker[1:] != rev_ticker[:-1])

    rev_cum_log = np.zeros(len(rev_ticker), dtype=float)
    cur = 0.0
    for i in range(len(rev_ticker)):
        if ticker_starts[i]:
            cur = rev_log_factor[i]
        else:
            cur += rev_log_factor[i]
        rev_cum_log[i] = cur

    cum_log = rev_cum_log[::-1] - log_factor
    cum_factor = np.exp(cum_log)

    df["adj_close"] = df["close"] * cum_factor
    df["adj_open"] = df["open"] * cum_factor
    df["raw_volume"] = df["volume"]
    df["turnover"] = df["close"] * df["volume"]

    # Filter valid trading dates
    trading_day_vols = df.groupby("date")["volume"].sum()
    valid_trading_dates = sorted(trading_day_vols[trading_day_vols > 0].index)
    adj_clean = df[df["date"].isin(valid_trading_dates)].copy()

    # 2. Build Advanced Mean-Reversion Features at time t
    adj_clean['ret_1w_raw'] = adj_clean.groupby('ticker')['adj_close'].pct_change(5)
    adj_clean['ret_2w_raw'] = adj_clean.groupby('ticker')['adj_close'].pct_change(10)
    adj_clean['ret_3m_raw'] = adj_clean.groupby('ticker')['adj_close'].pct_change(60)
    adj_clean['vol_20d_raw'] = adj_clean.groupby('ticker')['adj_close'].pct_change().transform(lambda x: x.rolling(20).std())

    # Turnover & Liquidity deciles
    adj_clean['avg_turnover_20d'] = adj_clean.groupby('ticker')['turnover'].transform(lambda x: x.ewm(span=20).mean())
    adj_clean['turnover_decile'] = adj_clean.groupby('date')['avg_turnover_20d'].transform(
        lambda s: pd.qcut(s, 10, labels=False, duplicates='drop') + 1 if len(s) >= 10 else 5
    )

    # Inverted Reversal Components
    adj_clean['rev_1w_inv_raw'] = -adj_clean['ret_1w_raw']
    adj_clean['rev_2w_inv_raw'] = -adj_clean['ret_2w_raw']
    adj_clean['low_vol_rank_raw'] = -adj_clean['vol_20d_raw']

    # Distress LR3 Signal
    adj_clean['is_lr3'] = adj_clean.groupby('date')['ret_3m_raw'].transform(lambda s: (s < s.median()).astype(int) if len(s)>=5 else 0)
    market_daily_ret = adj_clean.groupby('date')['adj_close'].pct_change().groupby(adj_clean['date']).mean()
    market_vol_20d = market_daily_ret.ewm(span=20).std()
    adj_clean['market_vol_20d'] = adj_clean['date'].map(market_vol_20d)
    vol_threshold = adj_clean['market_vol_20d'].quantile(0.75)

    adj_clean['distress_signal_raw'] = np.where(
        (adj_clean['is_lr3'] == 1) & (adj_clean['market_vol_20d'] >= vol_threshold),
        -adj_clean['ret_1w_raw'], 0.0
    )

    # Combined Calibrated Score (Multi-Horizon Reversal + Distress + Low-Vol Filtering)
    adj_clean['calibrated_score_raw'] = (
        0.40 * adj_clean['rev_1w_inv_raw'] +
        0.30 * adj_clean['rev_2w_inv_raw'] +
        0.20 * adj_clean['distress_signal_raw'] +
        0.50 * adj_clean['low_vol_rank_raw']
    )

    # --- CRITICAL LEAKAGE GUARD: Explicit .shift(1) Lagging on ALL Features ---
    adj_clean['rev_1w_inv'] = adj_clean.groupby('ticker')['rev_1w_inv_raw'].shift(1)
    adj_clean['rev_2w_inv'] = adj_clean.groupby('ticker')['rev_2w_inv_raw'].shift(1)
    adj_clean['distress_signal'] = adj_clean.groupby('ticker')['distress_signal_raw'].shift(1)
    adj_clean['low_vol_rank'] = adj_clean.groupby('ticker')['low_vol_rank_raw'].shift(1)
    adj_clean['calibrated_score'] = adj_clean.groupby('ticker')['calibrated_score_raw'].shift(1)

    # Forward 5-day return evaluated from t+1 Open to t+1+5 Close
    adj_clean['exec_price_t1'] = adj_clean.groupby('ticker')['adj_open'].shift(-1)
    adj_clean['target_price_t5'] = adj_clean.groupby('ticker')['adj_close'].shift(-6)
    adj_clean['fwd_return_5d'] = (adj_clean['target_price_t5'] / adj_clean['exec_price_t1']) - 1.0

    # IC Evaluation Function
    def evaluate_ic(df_sub, score_col, horizon=5):
        valid_mask = df_sub[score_col].notna() & df_sub['fwd_return_5d'].notna() & (df_sub['raw_volume'] > 0)
        df_v = df_sub[valid_mask].copy()

        df_v['s_rank'] = df_v.groupby("date")[score_col].rank(pct=True)
        df_v['y_rank'] = df_v.groupby("date")['fwd_return_5d'].rank(pct=True)

        cov = (df_v['s_rank'] * df_v['y_rank']).groupby(df_v['date']).mean() - (df_v['s_rank'].groupby(df_v['date']).mean() * df_v['y_rank'].groupby(df_v['date']).mean())
        std_s = df_v['s_rank'].groupby(df_v['date']).std()
        std_y = df_v['y_rank'].groupby(df_v['date']).std()
        daily_ic = (cov / (std_s * std_y + 1e-8)).dropna()
        ic_vals = daily_ic.values

        mean_ic = np.mean(ic_vals)
        nw_lag = max(1, horizon - 1)
        ols = sm.OLS(ic_vals, np.ones_like(ic_vals)).fit(cov_type='HAC', cov_kwds={'maxlags': nw_lag})
        t_stat = ols.tvalues[0]
        p_val = ols.pvalues[0]

        # Quintile Spread
        q5_ret = df_v[df_v['s_rank'] >= 0.80].groupby('date')['fwd_return_5d'].mean()
        q1_ret = df_v[df_v['s_rank'] <= 0.20].groupby('date')['fwd_return_5d'].mean()
        sp_df = pd.DataFrame({'q5': q5_ret, 'q1': q1_ret}).dropna()
        spreads = sp_df['q5'] - sp_df['q1']
        ann_spread = spreads.mean() * 100 * (240 / 5)
        spread_sharpe = (spreads.mean() / (spreads.std() + 1e-8)) * np.sqrt(240 / 5)

        return mean_ic, t_stat, p_val, ann_spread, spread_sharpe, len(ic_vals)

    features_to_test = {
        "1W Inverted Reversal": "rev_1w_inv",
        "2W Inverted Reversal": "rev_2w_inv",
        "Distress Liquidity Signal": "distress_signal",
        "Low Volatility Filter": "low_vol_rank",
        "Calibrated Composite Score": "calibrated_score"
    }

    print(f"\n{'Mean-Reversion Feature':<30} | {'Mean Rank IC':<14} | {'NW t-stat':<12} | {'NW p-val':<10} | {'Ann Spread':<12} | {'Spread Sharpe':<14} | {'Audit Status'}")
    print("-" * 125)
    for name, col in features_to_test.items():
        m_ic, t_st, p_v, a_sp, sh_sp, n_days = evaluate_ic(adj_clean, col, horizon=5)
        status = "SUCCESS (IC > +0.03)" if (m_ic >= 0.03 and t_st > 2.0) else ("PASS (Significant Edge)" if t_st > 2.0 else "FAIL")
        print(f"{name:<30} | {m_ic:+.4f}        | {t_st:+.2f}       | {p_v:.4f}     | {a_sp:+.2f}%      | {sh_sp:+.2f}         | {status}")

if __name__ == "__main__":
    run_calibrated_engine()
