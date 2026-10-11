import duckdb
con = duckdb.connect()
print(con.execute("SELECT DISTINCT date FROM '02_processed_parquet/nepse_index.parquet' ORDER BY date DESC LIMIT 10").fetchall())
