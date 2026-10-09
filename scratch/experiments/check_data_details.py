import duckdb

con = duckdb.connect()
df_types = con.execute("SELECT security_type, count(*) as count FROM '02_processed_parquet/market_master_union.parquet' GROUP BY security_type").df()
print(df_types)
