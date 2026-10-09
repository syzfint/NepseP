import duckdb
con = duckdb.connect()
res = con.execute("SELECT MAX(date) as max_date, MIN(date) as min_date, count(*) as total_rows FROM read_parquet('02_processed_parquet/market_master_union.parquet')").df()
print("PARQUET MASTER UNION:")
print(res)
