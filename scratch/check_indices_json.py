import json

with open("01_raw_data/nepse_indices_2026-10-07.json", "r") as f:
    print("2026-10-07 indices:", f.read()[:200])

with open("01_raw_data/nepse_indices_2026-10-08.json", "r") as f:
    print("2026-10-08 indices:", f.read()[:200])
