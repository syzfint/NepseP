import os
import sys
import json
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

# Add repo root to sys.path
base_dir = Path(__file__).resolve().parent.parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from scripts.03_data_access_and_storage.duckdb_connection_manager import connection_manager
from scripts.nepse_trading_calendar import (
    NEPSE_BUS_DAY,
    get_actual_nepse_trading_dates,
    get_next_trading_session,
    format_session_label,
    add_nepse_trading_days
)

def main():
    parser = argparse.ArgumentParser(description="APEXMARKETENGINE — NEPSE Quantitative Forecaster")
    parser.add_argument("--as-of-date", type=str, default=None, help="Evaluation anchor date (YYYY-MM-DD)")
    parser.add_argument("--target-date", type=str, default=None, help="Forecast target date (YYYY-MM-DD)")
    args = parser.parse_args()

    db_path = base_dir / "02_processed_parquet" / "market_master_union.parquet"
    if not db_path.exists():
        print(f"ERROR: {db_path} not found.")
        sys.exit(1)
        
    with connection_manager.acquire() as con:
        # Fetch historical bars up to available range
        df = con.execute("""
            SELECT ticker, CAST(date AS VARCHAR) as date, open, high, low, close, volume, security_type
            FROM read_parquet(?)
            WHERE date >= ?
            ORDER BY ticker, date
        """, [str(db_path), "2026-01-01"]).df()
    df['date'] = pd.to_datetime(df['date'])
    
    # Determine anchor date (last actual trading session)
    if args.as_of_date:
        latest_date = pd.to_datetime(args.as_of_date)
    else:
        latest_date = df['date'].max()
    
    last_actual_session = latest_date.strftime('%Y-%m-%d')
    last_actual_label = f"{latest_date.strftime('%Y-%m-%d (%A)')}"
    
    # Determine target session dynamically using NEPSE calendar engine
    if args.target_date:
        prediction_target_session = args.target_date
    else:
        prediction_target_session = get_next_trading_session(last_actual_session, str(db_path))
        
    target_dt = pd.to_datetime(prediction_target_session)
    prediction_target_label = f"{target_dt.strftime('%Y-%m-%d (%A)')}"
    
    print("==========================================================================")
    print(f"  APEXMARKETENGINE — NEPSE PREDICTION & RANKING ENGINE")
    print(f"  Anchor Close (t-1):    {last_actual_label}")
    print(f"  Forecast Session (t):  {prediction_target_label}")
    print("  Universe: Liquid Ordinary Equities (ADV >= NPR 1M, Active Days >= 15)   ")
    print("==========================================================================")
    
    # Filter bars up to anchor date to prevent future leakage
    df = df[df['date'] <= latest_date].copy()
    
    # 2. Compute Audited Stationary Features
    df['ret_1w'] = df.groupby('ticker')['close'].pct_change(5)
    df['vol_20d'] = df.groupby('ticker')['close'].pct_change().groupby(df['ticker']).transform(lambda x: x.rolling(20).std())
    
    df['turnover'] = df['close'] * df['volume']
    df['turnover_20d'] = df.groupby('ticker')['turnover'].transform(lambda x: x.shift(1).rolling(20).mean())
    df['adv_20d'] = df.groupby('ticker')['volume'].transform(lambda x: x.shift(1).rolling(20).mean())
    df['active_days_20d'] = df.groupby('ticker')['volume'].transform(lambda x: (x.shift(1) > 0).rolling(20).sum())
    
    # Enforce Institutional Liquidity Gating
    liquid_mask = (
        (df['security_type'] == 'ORDINARY_EQUITY') &
        (df['turnover_20d'] >= 1000000.0) &
        (df['active_days_20d'] >= 15) &
        (df['volume'] > 0)
    )
    
    latest_df = df[(df['date'] == latest_date) & liquid_mask].copy()
    latest_df = latest_df.dropna(subset=['ret_1w', 'vol_20d', 'close'])
    print(f"Liquid Institutional Universe Count: {len(latest_df)} tickers (filtered from {df[df['date'] == latest_date]['ticker'].nunique()} total)")
    
    # Feature scores (zero-leakage lag: t-1 close features predict t open)
    latest_df['score_rev'] = -latest_df['ret_1w']
    latest_df['score_vol'] = 1.0 / (latest_df['vol_20d'] + 1e-6)
    
    latest_df['rank_rev'] = latest_df['score_rev'].rank(pct=True)
    latest_df['rank_vol'] = latest_df['score_vol'].rank(pct=True)
    latest_df['composite_score'] = 0.5 * latest_df['rank_rev'] + 0.5 * latest_df['rank_vol']
    
    top_buys = latest_df.sort_values('composite_score', ascending=False).head(10)
    
    avg_market_ret_1w = latest_df['ret_1w'].mean()
    market_regime = "MEAN_REVERSION_BUY_DIP" if avg_market_ret_1w < 0 else "CONSOLIDATION_SELECTIVE"
    
    results = {
        "as_of_market_close": last_actual_label,
        "prediction_target_date": prediction_target_label,
        "target_date_iso": target_dt.strftime('%Y-%m-%d'),
        "target_weekday": target_dt.strftime('%A'),
        "market_regime": market_regime,
        "active_universe_count": len(latest_df),
        "avg_market_1w_return_pct": float(avg_market_ret_1w * 100),
        "top_10_long_forecasts": []
    }
    
    print(f"\n--- TOP 10 RANKED BULLISH TICKERS FOR {prediction_target_label.upper()} ---")
    for rank, (_, row) in enumerate(top_buys.iterrows(), 1):
        item = {
            "rank": rank,
            "ticker": row['ticker'],
            "latest_close": float(row['close']),
            "ret_1w_pct": float(row['ret_1w'] * 100),
            "vol_20d_pct": float(row['vol_20d'] * 100),
            "adv_20d_shares": float(row['adv_20d']),
            "composite_score": float(row['composite_score'])
        }
        results["top_10_long_forecasts"].append(item)
        print(f"{rank:2d}. {row['ticker']:<10} | Close: NPR {row['close']:>8.2f} | 1W Ret: {row['ret_1w']*100:>6.2f}% | Vol20d: {row['vol_20d']*100:>5.2f}% | Score: {row['composite_score']:.4f}")
        
    output_json_path = base_dir / "NEPSE_OCT5_PREDICTION.json"
    with open(output_json_path, "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"\nPrediction saved successfully to {output_json_path.name}.")

if __name__ == "__main__":
    main()
