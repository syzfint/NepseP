import duckdb
import pandas as pd
import numpy as np

path = "02_processed_parquet/market_master_union.parquet"
conn = duckdb.connect(":memory:")

# Query daily aggregate statistics from 2026-03-27 to 2026-10-07
query = f"""
WITH daily_stock_stats AS (
    SELECT 
        ticker,
        date,
        close,
        volume,
        close * volume as turnover,
        security_type,
        LAG(close) OVER (PARTITION BY ticker ORDER BY date) as prev_close
    FROM "{path}"
    WHERE date >= '2026-03-20'
),
valid_bars AS (
    SELECT 
        date,
        ticker,
        close,
        volume,
        turnover,
        security_type,
        prev_close,
        (close - prev_close) / prev_close as ret
    FROM daily_stock_stats
    WHERE date >= '2026-03-27' AND prev_close IS NOT NULL
)
SELECT 
    date,
    count(distinct ticker) as active_traded_symbols,
    sum(CASE WHEN ret > 0 THEN 1 ELSE 0 END) as gainers,
    sum(CASE WHEN ret < 0 THEN 1 ELSE 0 END) as losers,
    sum(CASE WHEN ret = 0 THEN 1 ELSE 0 END) as unchanged,
    sum(turnover) / 1e9 as turnover_billions_npr,
    avg(ret) * 100 as equal_weight_return_pct,
    sum(ret * turnover) / sum(turnover) * 100 as turnover_weighted_return_pct
FROM valid_bars
GROUP BY date
ORDER BY date ASC;
"""

df_market = conn.execute(query).df()
print(f"Total trading days between March 27, 2026 and Oct 7, 2026: {len(df_market)}")
print("First 5 sessions:")
print(df_market.head().to_string())
print("\nLast 5 sessions:")
print(df_market.tail().to_string())

# Save daily timeseries to CSV for full forensic review
df_market.to_csv("reports/NEPSE_MARCH27_OCT8_DAILY_ANALYSIS.csv", index=False)
print("\nSaved daily series to reports/NEPSE_MARCH27_OCT8_DAILY_ANALYSIS.csv")
