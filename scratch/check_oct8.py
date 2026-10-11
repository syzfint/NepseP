import json
import duckdb

with open("01_raw_data/nepse_market_status_2026-10-08.json", "r") as f:
    print("Market status 2026-10-08:", f.read())

with open("01_raw_data/nepse_summary_2026-10-08.json", "r") as f:
    print("Summary 2026-10-08:", f.read())

con = duckdb.connect()
fs_info = con.execute("SELECT COUNT(*), COUNT(DISTINCT stockSymbol), MIN(contractRate), MAX(contractRate), SUM(contractAmount) FROM '01_raw_data/nepse_floorsheet_2026-10-08.parquet'").df()
print("Floorsheet 2026-10-08 info:")
print(fs_info)
