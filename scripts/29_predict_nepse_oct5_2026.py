import os
import sys
import json
import numpy as np
import pandas as pd
import duckdb

def main():
    print("==========================================================================")
    print("  APEXMARKETENGINE — NEPSE PREDICTION & RANKING FOR MONDAY, OCT 5, 2026    ")
    print("==========================================================================")
    
    db_path = "02_processed_parquet/market_master_union.parquet"
    if not os.path.exists(db_path):
        print(f"ERROR: {db_path} not found.")
        sys.exit(1)
        
    con = duckdb.connect()
    
    # 1. Fetch latest data up to 2026-10-02
    df = con.execute(f"""
        SELECT ticker, CAST(date AS VARCHAR) as date, open, high, low, close, volume
        FROM '{db_path}'
        WHERE date >= '2026-01-01'
        ORDER BY ticker, date
    """).df()
    df['date'] = pd.to_datetime(df['date'])
    
    latest_date = df['date'].max()
    print(f"Latest Market Close Date in Dataset: {latest_date.strftime('%Y-%m-%d')}")
    
    # 2. Compute Audited Features (as of t = 2026-10-02)
    # Technical Reversal: 1W (-ret_1w)
    df['ret_1w'] = df.groupby('ticker')['close'].pct_change(5)
    # Low Volatility: 1 / vol_20d
    df['vol_20d'] = df.groupby('ticker')['close'].pct_change().groupby(df['ticker']).transform(lambda x: x.rolling(20).std())
    # 20-day ADV Volume Cap
    df['adv_20d'] = df.groupby('ticker')['volume'].transform(lambda x: x.rolling(20).mean())
    
    # Filter for active tickers on latest trading day
    latest_df = df[df['date'] == latest_date].copy()
    latest_df = latest_df.dropna(subset=['ret_1w', 'vol_20d', 'close'])
    latest_df = latest_df[latest_df['volume'] > 0]
    
    # Feature scores (zero-leakage lag is implicitly enforced because features use t=Oct 2 close to forecast Oct 5 open)
    latest_df['score_rev'] = -latest_df['ret_1w']
    latest_df['score_vol'] = 1.0 / (latest_df['vol_20d'] + 1e-6)
    
    # Ranks (0.0 to 1.0)
    latest_df['rank_rev'] = latest_df['score_rev'].rank(pct=True)
    latest_df['rank_vol'] = latest_df['score_vol'].rank(pct=True)
    latest_df['composite_score'] = 0.5 * latest_df['rank_rev'] + 0.5 * latest_df['rank_vol']
    
    # Top 10 High-Confidence Mean-Reversion Long Opportunities
    top_buys = latest_df.sort_values('composite_score', ascending=False).head(10)
    
    # Market-wide Regime Diagnostic
    avg_market_ret_1w = latest_df['ret_1w'].mean()
    market_regime = "MEAN_REVERSION_BUY_DIP" if avg_market_ret_1w < 0 else "CONSOLIDATION_SELECTIVE"
    
    results = {
        "prediction_target_date": "2026-10-05 (Monday)",
        "as_of_market_close": latest_date.strftime('%Y-%m-%d'),
        "market_regime": market_regime,
        "active_universe_count": len(latest_df),
        "avg_market_1w_return_pct": float(avg_market_ret_1w * 100),
        "top_10_long_forecasts": []
    }
    
    print("\n--- TOP 10 RANKED BULLISH TICKERS FOR MONDAY, OCT 5, 2026 ---")
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
        
    with open("NEPSE_OCT5_PREDICTION.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\nNEPSE_OCT5_PREDICTION.json generated successfully.")

if __name__ == "__main__":
    main()
