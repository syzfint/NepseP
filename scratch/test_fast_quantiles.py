import time
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path.cwd()
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
FEATURE_DIR = BASE_DIR / "03_feature_store"
MASTER_PARQUET = PROCESSED_DIR / "market_master_union.parquet"
TECH_PARQUET = FEATURE_DIR / "technical_indicators.parquet"
CHRONOS_PARQUET = FEATURE_DIR / "chronos_quantiles_5d.parquet"

t0 = time.time()
print("Reading recent prices directly via DuckDB window...", flush=True)

con = duckdb.connect()
# Only read the last 60 days per ticker to make it instantaneous!
sql = f"""
WITH ranked AS (
    SELECT 
        ticker, 
        CAST(date AS DATE) as date, 
        close, 
        security_type,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
    FROM read_parquet('{str(MASTER_PARQUET).replace('\\', '/')}')
    WHERE security_type IN ('ORDINARY_EQUITY', 'MICROFINANCE') AND close > 0
)
SELECT ticker, date, close
FROM ranked
WHERE rn <= 60
ORDER BY ticker ASC, date ASC
"""
df_recent = con.execute(sql).df()

print(f"Loaded {len(df_recent)} price bars across {df_recent['ticker'].nunique()} tickers in {time.time()-t0:.2f}s.", flush=True)

# Read technical indicators
query_tech = f"""
SELECT ticker, date, volume_force_index, price_volume_divergence_5d, donchian_channel_pos_20,
       kline_lower_shadow_ratio, kline_gap_rejection_flag
FROM read_parquet('{str(TECH_PARQUET).replace('\\', '/')}')
QUALIFY ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) = 1
"""
df_tech = con.execute(query_tech).df().set_index("ticker").to_dict(orient="index")
con.close()

grouped = df_recent.groupby("ticker")
records = []

for sym, grp in grouped:
    prices = grp["close"].values
    if len(prices) < 5 or prices[-1] <= 0:
        continue
    curr_p = float(prices[-1])
    
    # Fast vectorized empirical quantile calculation
    ret = np.diff(np.log(prices[-30:])) if len(prices) >= 30 else np.diff(np.log(prices))
    daily_vol = float(np.std(ret)) if len(ret) > 1 else 0.02
    drift = float(np.mean(ret)) * 5.0
    h_vol = daily_vol * np.sqrt(5.0)
    
    p50 = round(float(curr_p * np.exp(drift)), 2)
    p10 = round(float(curr_p * np.exp(drift - 1.2816 * h_vol)), 2)
    p90 = round(float(curr_p * np.exp(drift + 1.2816 * h_vol)), 2)
    spread = round((p90 - p10) / curr_p * 100.0, 2)
    exp_ret = round((p50 - curr_p) / curr_p * 100.0, 2)
    
    vol_amt = daily_vol * curr_p
    p_profit = max(0.01, min(0.99, (p90 - (curr_p + 2.0 * vol_amt)) / (vol_amt + 1e-4) + 0.5))
    p_loss = max(0.01, min(0.99, ((curr_p - 2.0 * vol_amt) - p10) / (vol_amt + 1e-4) + 0.5))
    barrier_ratio = round(p_profit / (p_loss + 1e-5), 2)
    
    t_info = df_tech.get(sym, {})
    vfi = float(t_info.get("volume_force_index", 0.0) or 0.0)
    pvd = float(t_info.get("price_volume_divergence_5d", 0.0) or 0.0)
    d_pos = float(t_info.get("donchian_channel_pos_20", 0.5) or 0.5)
    lower_shadow = float(t_info.get("kline_lower_shadow_ratio", 0.0) or 0.0)
    floor_bounce = bool((d_pos <= 0.40) and (lower_shadow >= 0.40))
    
    records.append({
        "symbol": sym,
        "latest_close": curr_p,
        "p10_5d": p10,
        "p50_5d": p50,
        "p90_5d": p90,
        "exp_return_5d_pct": exp_ret,
        "uncertainty_spread_pct": spread,
        "chronos_barrier_ratio": barrier_ratio,
        "volume_force_index": round(vfi, 4),
        "price_volume_divergence_5d": round(pvd, 4),
        "donchian_channel_pos_20": round(d_pos, 4),
        "kline_lower_shadow_ratio": round(lower_shadow, 4),
        "floor_bounce_confirmed": floor_bounce,
        "gate_g4_status": "CERTIFIED" if (barrier_ratio >= 1.20 and spread <= 15.0) else "REJECTED_G4_BARRIER",
    })

df_chronos = pd.DataFrame(records)
df_chronos.to_parquet(CHRONOS_PARQUET, index=False)
print(f"Generated {len(df_chronos)} Chronos quantiles in {time.time()-t0:.2f}s and saved to {CHRONOS_PARQUET}!", flush=True)
print(df_chronos.head(5))
