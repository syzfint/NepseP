import duckdb
import glob

con = duckdb.connect()
files = glob.glob("nepse_lakehouse/year=2026/month=10/**/*.parquet", recursive=True)
for f in sorted(files):
    df = con.execute(f"SELECT COUNT(*), MIN(timestamp_npt), MAX(timestamp_npt), COUNT(DISTINCT symbol) FROM read_parquet('{f}')").fetchall()
    print(f, "->", df)

sample = con.execute("SELECT * FROM read_parquet('nepse_lakehouse/year=2026/month=10/day=06/*.parquet') LIMIT 5").df()
print("\nSample records from day=06:")
print(sample)
