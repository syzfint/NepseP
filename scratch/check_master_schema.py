import duckdb
con = duckdb.connect()
print(con.execute("DESCRIBE SELECT * FROM '02_processed_parquet/market_master_union.parquet'").df())
print("\nSample 2026-10-08 rows:")
print(con.execute("SELECT * FROM '02_processed_parquet/market_master_union.parquet' WHERE date = '2026-10-08' LIMIT 5").df())
print("\nRow count on 2026-10-08:")
print(con.execute("SELECT COUNT(*), COUNT(DISTINCT ticker) FROM '02_processed_parquet/market_master_union.parquet' WHERE date = '2026-10-08'").df())
