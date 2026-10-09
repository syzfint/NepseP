import duckdb

con = duckdb.connect()
res = con.execute("SELECT DISTINCT date FROM '02_processed_parquet/market_master_union.parquet' WHERE date >= '2026-09-20' ORDER BY date").fetchall()
print("Dates in parquet:")
for r in res:
    print(r[0], r[0].strftime("%A"))
