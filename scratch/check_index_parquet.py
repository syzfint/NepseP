import duckdb
con = duckdb.connect()
print(con.execute("DESCRIBE SELECT * FROM '02_processed_parquet/nepse_index.parquet'").df())
print("\nRecent index records:")
print(con.execute("SELECT * FROM '02_processed_parquet/nepse_index.parquet' ORDER BY date DESC LIMIT 5").df())
