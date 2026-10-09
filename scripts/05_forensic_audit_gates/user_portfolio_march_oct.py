import duckdb
import pandas as pd

path = "02_processed_parquet/market_master_union.parquet"
conn = duckdb.connect(":memory:")

query = f"""
WITH p_start AS (
    SELECT ticker, close as p_mar27
    FROM "{path}"
    WHERE date = '2026-03-27'
),
p_end AS (
    SELECT ticker, close as p_oct7, volume, close * volume as turnover_oct7
    FROM "{path}"
    WHERE date = '2026-10-07'
),
tot_turnover AS (
    SELECT ticker, sum(close * volume) as total_turnover
    FROM "{path}"
    WHERE date >= '2026-03-27'
    GROUP BY ticker
)
SELECT 
    s.ticker,
    s.p_mar27,
    e.p_oct7,
    round((e.p_oct7 - s.p_mar27) / s.p_mar27 * 100, 2) as return_pct,
    round(t.total_turnover / 1e9, 2) as total_turnover_bn
FROM p_start s
JOIN p_end e ON s.ticker = e.ticker
JOIN tot_turnover t ON s.ticker = t.ticker
ORDER BY return_pct DESC;
"""

df_perf = conn.execute(query).df()
print("Top 10 Performers (March 27 to Oct 7, 2026):")
print(df_perf.head(10).to_string())

print("\nWorst 10 Performers (March 27 to Oct 7, 2026):")
print(df_perf.tail(10).to_string())

user_portfolio = ['AHPC', 'API', 'CHCL', 'CIT', 'LBBL', 'NABIL', 'NGPL', 'SAHAS']
print("\nYour Portfolio Stocks Performance (March 27 to Oct 7, 2026):")
print(df_perf[df_perf['ticker'].isin(user_portfolio)].to_string())
