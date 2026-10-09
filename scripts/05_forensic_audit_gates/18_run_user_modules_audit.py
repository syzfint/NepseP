import os
import warnings
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
import statsmodels.api as sm

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"

def clean_and_adjust_prices(df_raw: pd.DataFrame, events_df: pd.DataFrame = None) -> pd.DataFrame:
    df = df_raw.sort_values(['ticker', 'date']).copy()
    df['date'] = pd.to_datetime(df['date'])
    
    if events_df is not None and not events_df.empty:
        events_df['date'] = pd.to_datetime(events_df['date'])
        df = pd.merge(df, events_df[['ticker', 'date', 'adj_factor']], on=['ticker', 'date'], how='left')
        df['adj_factor'] = df.groupby('ticker')['adj_factor'].ffill().fillna(1.0)
        df['adj_close'] = df['close'] * df['adj_factor']
        df['adj_open'] = df['open'] * df['adj_factor']
    else:
        # Correct Backward Adjustment for Corporate Actions
        prev_close = df.groupby("ticker")["close"].shift(1).fillna(df["close"]).values
        raw_ratio = np.where(prev_close > 0, df["close"].values / prev_close, 1.0)
        adj_factor = np.where((raw_ratio < 0.88) & (raw_ratio > 0.05), raw_ratio, 1.0)
        log_factor = np.log(np.maximum(adj_factor, 1e-8))

        ticker_arr = df["ticker"].values
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

        df['adj_close'] = df['close'] * cum_factor
        df['adj_open'] = df['open'] * cum_factor

    df['raw_volume'] = df['volume']
    df = df[df['adj_close'] > 0].reset_index(drop=True)
    return df

def build_features_and_labels(df: pd.DataFrame, horizon: int = 5, pt_sigma: float = 2.0, sl_sigma: float = 1.5) -> pd.DataFrame:
    df = df.sort_values(['ticker', 'date']).copy()

    df['ret_1d_raw'] = df.groupby('ticker')['adj_close'].pct_change(1)
    df['mom_5d_raw'] = df.groupby('ticker')['adj_close'].pct_change(5)
    df['vol_20d_raw'] = df.groupby('ticker')['ret_1d_raw'].transform(lambda x: x.rolling(20).std())
    
    feature_cols = ['ret_1d_raw', 'mom_5d_raw', 'vol_20d_raw']
    for col in feature_cols:
        clean_name = col.replace('_raw', '')
        df[clean_name] = df.groupby('ticker')[col].shift(1)

    df['exec_price_t1'] = df.groupby('ticker')['adj_open'].shift(-1)
    df['target_price_tH'] = df.groupby('ticker')['adj_close'].shift(-(1 + horizon))
    
    df['fwd_return'] = (df['target_price_tH'] / df['exec_price_t1']) - 1.0

    df['upper_barrier'] = df['vol_20d'] * pt_sigma
    df['lower_barrier'] = -df['vol_20d'] * sl_sigma

    cond_valid = df['fwd_return'].notna() & df['upper_barrier'].notna()
    cond_pt = df['fwd_return'] >= df['upper_barrier']
    
    df['tb_label'] = np.where(~cond_valid, np.nan, np.where(cond_pt, 1.0, 0.0))
    return df

def compute_rank_ic_audit(df: pd.DataFrame, feature_col: str, horizon: int = 5, n_permutations: int = 10) -> dict:
    valid_mask = (
        df[feature_col].notna() & 
        df['fwd_return'].notna() & 
        (df['raw_volume'] > 0)
    )
    df_valid = df[valid_mask].copy()

    df_valid['feature_rank'] = df_valid.groupby('date')[feature_col].rank(pct=True)
    df_valid['fwd_rank'] = df_valid.groupby('date')['fwd_return'].rank(pct=True)

    cov = (df_valid['feature_rank'] * df_valid['fwd_rank']).groupby(df_valid['date']).mean() - (df_valid['feature_rank'].groupby(df_valid['date']).mean() * df_valid['fwd_rank'].groupby(df_valid['date']).mean())
    std_s = df_valid['feature_rank'].groupby(df_valid['date']).std()
    std_y = df_valid['fwd_rank'].groupby(df_valid['date']).std()
    
    daily_ic = (cov / (std_s * std_y + 1e-8)).dropna()
    ic_values = daily_ic.values

    if len(ic_values) == 0:
        raise ValueError("No valid cross-sectional trading days found.")

    mean_ic = np.mean(ic_values)

    nw_lag = max(1, horizon - 1)
    ols_model = sm.OLS(ic_values, np.ones_like(ic_values)).fit(
        cov_type='HAC', 
        cov_kwds={'maxlags': nw_lag}
    )
    nw_t_stat = ols_model.tvalues[0]
    p_val_two_sided = ols_model.pvalues[0]

    perm_means = []
    np.random.seed(42)
    fwd_vals = df_valid['fwd_return'].values
    for i in range(n_permutations):
        df_valid['fwd_perm'] = np.random.permutation(fwd_vals)
        df_valid['fwd_perm_rank'] = df_valid.groupby('date')['fwd_perm'].rank(pct=True)
        cov_p = (df_valid['feature_rank'] * df_valid['fwd_perm_rank']).groupby(df_valid['date']).mean() - (df_valid['feature_rank'].groupby(df_valid['date']).mean() * df_valid['fwd_perm_rank'].groupby(df_valid['date']).mean())
        std_yp = df_valid['fwd_perm_rank'].groupby(df_valid['date']).std()
        perm_ic = (cov_p / (std_s * std_yp + 1e-8)).dropna().mean()
        perm_means.append(perm_ic)

    return {
        'feature_evaluated': feature_col,
        'mean_rank_ic': mean_ic,
        'newey_west_t_stat': nw_t_stat,
        'two_sided_p_value': p_val_two_sided,
        'permutation_null_mean': np.mean(perm_means),
        'permutation_null_std': np.std(perm_means),
        'total_trading_days': len(ic_values)
    }

def main():
    print("=" * 85)
    print("      EXECUTING AUDIT ON USER-PROVIDED CODE MODULES")
    print("=" * 85)

    master_path = os.path.join(PROCESSED_DIR, "market_master_union.parquet")
    df_raw = pd.read_parquet(master_path)
    df_raw["date"] = pd.to_datetime(df_raw["date"])
    df_raw = df_raw[df_raw["date"] >= "2010-01-01"].reset_index(drop=True)

    print("\n1. Running clean_and_adjust_prices()...")
    df_clean = clean_and_adjust_prices(df_raw)

    print("2. Running build_features_and_labels() with horizon=5d...")
    df_feat = build_features_and_labels(df_clean, horizon=5)

    print("3. Running compute_rank_ic_audit() for features...")
    for feat in ['mom_5d', 'ret_1d', 'vol_20d']:
        res = compute_rank_ic_audit(df_feat, feat, horizon=5, n_permutations=10)
        print(f"Feature: {res['feature_evaluated']:<10} | Mean Rank IC (5d): {res['mean_rank_ic']:+.4f} | Newey-West t-stat: {res['newey_west_t_stat']:+.2f} | NW p-val: {res['two_sided_p_value']:.4f} | Perm Null: {res['permutation_null_mean']:+.4f}")

if __name__ == "__main__":
    main()
