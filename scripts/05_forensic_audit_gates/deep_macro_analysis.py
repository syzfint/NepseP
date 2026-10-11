import duckdb
import pandas as pd
import numpy as np
from scripts.db_connection import connection_manager

path = "02_processed_parquet/market_master_union.parquet"

# Monthly and sector analysis
sector_query = f"""
WITH base AS (
    SELECT 
        ticker,
        security_type,
        date,
        close,
        volume,
        close * volume as turnover,
        LAG(close) OVER (PARTITION BY ticker ORDER BY date) as prev_close
    FROM "{path}"
    WHERE date >= '2026-03-20'
),
daily_ret AS (
    SELECT 
        ticker,
        security_type,
        date,
        close,
        volume,
        turnover,
        (close - prev_close) / prev_close as ret
    FROM base
    WHERE date >= '2026-03-27' AND prev_close IS NOT NULL
)
SELECT 
    security_type,
    count(distinct ticker) as tickers,
    avg(ret) * 100 as avg_daily_ret_pct,
    sum(turnover) / 1e9 as total_turnover_billions
FROM daily_ret
GROUP BY security_type
ORDER BY total_turnover_billions DESC;
"""

month_query = f"""
WITH daily AS (
    SELECT 
        date,
        date_trunc('month', date) as month,
        count(distinct ticker) as tickers,
        sum(close * volume) / 1e9 as turnover_bn
    FROM "{path}"
    WHERE date >= '2026-03-27'
    GROUP BY date
)
SELECT 
    strftime(month, '%Y-%m') as month_str,
    count(*) as trading_days,
    sum(turnover_bn) as monthly_turnover_bn,
    avg(turnover_bn) as avg_daily_turnover_bn
FROM daily
GROUP BY month, month_str
ORDER BY month ASC;
"""

with connection_manager.acquire() as conn:
    df_sectors = conn.execute(sector_query).df()
    df_months = conn.execute(month_query).df()

print("Sector / Security Breakdown (March 27 - Oct 7, 2026):")
print(df_sectors.to_string())

print("\nMonthly Turnover Breakdown:")
print(df_months.to_string())

# Overall price trajectory calculation
# We can track cumulative market return from March 27 to Oct 7
df_daily = pd.read_csv("reports/NEPSE_MARCH27_OCT8_DAILY_ANALYSIS.csv")
df_daily['cum_turnover_weighted'] = (1 + df_daily['turnover_weighted_return_pct'] / 100).cumprod()
df_daily['cum_equal_weighted'] = (1 + df_daily['equal_weight_return_pct'] / 100).cumprod()

print("\nCumulative Trajectory from March 27 base (1.0000):")
print(f"Cumulative Turnover-Weighted Index Return: {(df_daily['cum_turnover_weighted'].iloc[-1] - 1) * 100:.2f}%")
print(f"Cumulative Equal-Weighted Return: {(df_daily['cum_equal_weighted'].iloc[-1] - 1) * 100:.2f}%")
print(f"Peak Turnover-Weighted (Bull Peak): {df_daily['cum_turnover_weighted'].max():.4f} on {df_daily.loc[df_daily['cum_turnover_weighted'].idxmax(), 'date']}")
print(f"Trough Turnover-Weighted: {df_daily['cum_turnover_weighted'].min():.4f} on {df_daily.loc[df_daily['cum_turnover_weighted'].idxmin(), 'date']}")
