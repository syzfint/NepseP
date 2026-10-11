import duckdb
import json

con = duckdb.connect()
rows = con.execute("""
    SELECT DISTINCT
        TRY_CAST(buyerMemberId AS INT) as id_int,
        CAST(buyerMemberId AS VARCHAR) as broker_id,
        TRIM(buyerBrokerName) as broker_name
    FROM read_parquet('01_raw_data/nepse_floorsheet_*.parquet', union_by_name=true)
    WHERE buyerBrokerName IS NOT NULL
    ORDER BY id_int
""").fetchall()

broker_dict = {str(r[1]): r[2] for r in rows}
print(f"Extracted {len(broker_dict)} brokers from parquet.")

with open("scratch/broker_raw_list.json", "w", encoding="utf-8") as f:
    json.dump(broker_dict, f, indent=2)

print("Saved to scratch/broker_raw_list.json")
con.close()
