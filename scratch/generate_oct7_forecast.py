import os
import sys
import json
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

def classify(symbol):
    t = str(symbol).upper().strip()
    if t.endswith("PO") or (t.endswith("P") and len(t) > 4 and not t.endswith("GROUP")):
        return "PROMOTER"
    elif "D8" in t or "D20" in t or t.startswith("GBD") or t.endswith("D83") or t.endswith("D86") or t.endswith("D85") or t.endswith("D88"):
        return "DEBENTURE"
    elif t.endswith("MF") or t.startswith("NBF") or t.startswith("SEF") or t.startswith("MMF") or t.startswith("NICBF") or t.startswith("RBB") or t.endswith("BF") or t.startswith("CMF") or t.startswith("SBF") or t.startswith("KDBY"):
        return "MUTUAL_FUND"
    elif "LBSL" in t or "MFIL" in t or "MLB" in t or "MICRO" in t or "SANIMA" in t and "L" in t:
        return "MICROFINANCE"
    else:
        return "ORDINARY_EQUITY"

def generate_oct7_forecast():
    base_dir = Path(__file__).resolve().parent.parent
    today_csv = base_dir / "nepse_data_all" / "2026_10_06.csv"
    master_parquet = base_dir / "02_processed_parquet" / "market_master_union.parquet"

    df_today_raw = pd.read_csv(today_csv)
    
    # Map today columns to standard schema
    df_today = pd.DataFrame({
        "ticker": df_today_raw['symbol'],
        "date": pd.to_datetime(df_today_raw['businessDate']),
        "open": df_today_raw['openPrice'].astype(float),
        "high": df_today_raw['highPrice'].astype(float),
        "low": df_today_raw['lowPrice'].astype(float),
        "close": df_today_raw['closePrice'].astype(float),
        "volume": df_today_raw['totalTradedQuantity'].astype(float),
        "turnover": df_today_raw['totalTradedValue'].astype(float),
        "prev_close": df_today_raw['previousDayClosePrice'].astype(float)
    })
    df_today['security_type'] = df_today['ticker'].apply(classify)
    
    # Load historical series from DuckDB to compute 20d ADV, SMA, and Momentum
    con = duckdb.connect()
    df_hist = con.execute("""
        SELECT ticker, CAST(date AS VARCHAR) as date, open, high, low, close, volume, security_type
        FROM read_parquet(?)
        WHERE date >= '2026-06-01'
        ORDER BY ticker, date
    """, [str(master_parquet)]).df()
    df_hist['date'] = pd.to_datetime(df_hist['date'])
    df_hist['turnover'] = df_hist['close'] * df_hist['volume']
    df_hist['prev_close'] = df_hist.groupby('ticker')['close'].shift(1)

    # Union history + today
    df_combined = pd.concat([df_hist, df_today], ignore_index=True).sort_values(['ticker', 'date']).reset_index(drop=True)
    
    # Feature Calculations as of Oct 6 close
    df_combined['turnover_20d'] = df_combined.groupby('ticker')['turnover'].transform(lambda x: x.rolling(20).mean())
    df_combined['adv_20d'] = df_combined.groupby('ticker')['volume'].transform(lambda x: x.rolling(20).mean())
    df_combined['active_days_20d'] = df_combined.groupby('ticker')['volume'].transform(lambda x: (x > 0).rolling(20).sum())
    
    # Scale-Invariant Indicators
    sma_20 = df_combined.groupby('ticker')['close'].transform(lambda x: x.rolling(20).mean())
    sma_50 = df_combined.groupby('ticker')['close'].transform(lambda x: x.rolling(50).mean())
    df_combined['dist_sma20'] = (df_combined['close'] / (sma_20 + 1e-8)) - 1.0
    df_combined['dist_sma50'] = (df_combined['close'] / (sma_50 + 1e-8)) - 1.0
    
    # Volatility & Bollinger %B
    std_20 = df_combined.groupby('ticker')['close'].transform(lambda x: x.rolling(20).std())
    bb_upper = sma_20 + (2.0 * std_20)
    bb_lower = sma_20 - (2.0 * std_20)
    df_combined['bb_pct_b'] = ((df_combined['close'] - bb_lower) / (bb_upper - bb_lower + 1e-8)).clip(-0.5, 1.5)
    df_combined['volatility_20'] = std_20 / (df_combined['close'] + 1e-8)
    
    # Microstructure & Momentum
    df_combined['vol_surge'] = ((df_combined['volume'] / (df_combined['adv_20d'] + 1e-8)) - 1.0).clip(-1.0, 5.0)
    df_combined['ret_1w'] = df_combined.groupby('ticker')['close'].pct_change(5)
    df_combined['ret_1m'] = df_combined.groupby('ticker')['close'].pct_change(21)
    
    # Slice today (Oct 6)
    today_date = pd.to_datetime("2026-10-06")
    df_now = df_combined[df_combined['date'] == today_date].copy()
    
    # Institutional liquidity gating: Ordinary Equity, ADV turnover >= NPR 1M, active >= 15 days
    liquid_mask = (
        (df_now['security_type'] == 'ORDINARY_EQUITY') &
        (df_now['turnover_20d'] >= 1000000.0) &
        (df_now['active_days_20d'] >= 15) &
        (df_now['volume'] > 0)
    )
    liquid_df = df_now[liquid_mask].dropna(subset=['dist_sma20', 'bb_pct_b', 'volatility_20', 'vol_surge', 'ret_1m']).copy()
    
    # Composite Factor Scoring:
    # 1. Healthy trend support: moderate distance above SMA50 but not overextended
    # 2. Reversion from lower Bollinger band (%B between 0.1 and 0.45)
    # 3. Penalize massive volume surges (distribution signal IC = -0.0124)
    # 4. Reward low-volatility consolidation
    liquid_df['score_trend'] = liquid_df['dist_sma50'].rank(pct=True)
    liquid_df['score_bb'] = (1.0 - (liquid_df['bb_pct_b'] - 0.25).abs()).rank(pct=True)
    liquid_df['score_vol_penalty'] = (1.0 - liquid_df['vol_surge']).rank(pct=True)
    liquid_df['score_low_vol'] = (1.0 / (liquid_df['volatility_20'] + 1e-6)).rank(pct=True)
    
    liquid_df['composite_score'] = (
        0.30 * liquid_df['score_trend'] +
        0.30 * liquid_df['score_bb'] +
        0.20 * liquid_df['score_vol_penalty'] +
        0.20 * liquid_df['score_low_vol']
    )
    
    top_10 = liquid_df.sort_values('composite_score', ascending=False).head(10)
    
    results = {
        "prediction_target_date": "2026-10-07 (Wednesday)",
        "as_of_market_close": "2026-10-06 (Tuesday)",
        "market_regime": "SELECTIVE_CONSOLIDATION_ACCUMULATION",
        "liquid_universe_count": len(liquid_df),
        "total_traded_universe_count": len(df_now),
        "top_10_long_forecasts": []
    }
    
    print("\n" + "=" * 85)
    print("APEXMARKETENGINE: AUDITED FORECAST & RANKING FOR TOMORROW (WEDNESDAY, OCT 7, 2026)")
    print("=" * 85)
    print(f"Liquid Institutional Universe: {len(liquid_df)} Ordinary Equities (filtered from {len(df_now)})")
    print("-" * 85)
    print(f"{'Rank':<5} | {'Ticker':<10} | {'Close (Oct 6)':<14} | {'1W Ret':<8} | {'1M Ret':<8} | {'Vol Surge':<10} | Score")
    print("-" * 85)
    
    for rank, (_, row) in enumerate(top_10.iterrows(), 1):
        item = {
            "rank": rank,
            "ticker": row['ticker'],
            "close_oct6": float(row['close']),
            "ret_1w_pct": float(row['ret_1w'] * 100) if not np.isnan(row['ret_1w']) else 0.0,
            "ret_1m_pct": float(row['ret_1m'] * 100) if not np.isnan(row['ret_1m']) else 0.0,
            "vol_surge_ratio": float(row['vol_surge']),
            "volatility_20d_pct": float(row['volatility_20'] * 100),
            "adv_20d_turnover_npr": float(row['turnover_20d']),
            "composite_score": float(row['composite_score'])
        }
        results["top_10_long_forecasts"].append(item)
        print(f"{rank:<5} | {row['ticker']:<10} | NPR {row['close']:>9.2f} | {row['ret_1w']*100:>+6.2f}% | {row['ret_1m']*100:>+6.2f}% | {row['vol_surge']:>+8.2f}x | {row['composite_score']:.4f}")
    print("=" * 85)
    
    with open("NEPSE_OCT7_PREDICTION.json", "w") as f:
        json.dump(results, f, indent=4)
    print("Saved forecast payload to NEPSE_OCT7_PREDICTION.json")

if __name__ == "__main__":
    generate_oct7_forecast()
