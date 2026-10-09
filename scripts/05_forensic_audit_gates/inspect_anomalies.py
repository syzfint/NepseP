import duckdb

p = "02_processed_parquet/market_master_union.parquet"
c = duckdb.connect(":memory:")

hl = c.execute(f'SELECT ticker, date, open, high, low, close FROM "{p}" WHERE high < low').fetchall()
print("High < Low rows:", hl)

op = c.execute(f'SELECT min(date), max(date), count(*) FROM "{p}" WHERE open <= 0').fetchall()
print("Open <= 0 dates:", op)

op_sample = c.execute(f'SELECT ticker, date, open, high, low, close, volume FROM "{p}" WHERE open <= 0 LIMIT 5').fetchall()
print("Open <= 0 sample:", op_sample)
