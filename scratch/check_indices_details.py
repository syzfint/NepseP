import json

for dt in ["2026-10-07", "2026-10-08"]:
    with open(f"01_raw_data/nepse_indices_{dt}.json") as f:
        data = json.load(f)
        nepse = [x for x in data if x.get("index") == "NEPSE Index"][0]
        print(dt, "NEPSE Index:", nepse)
    with open(f"01_raw_data/nepse_summary_{dt}.json") as f:
        sdata = json.load(f)
        turnover = [x["value"] for x in sdata if "Turnover" in x.get("detail", "")][0]
        print(dt, "Turnover:", turnover)
