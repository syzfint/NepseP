import os
import shutil

BASE_DIR = r"c:\Users\achar\Downloads\neps"
RAW_DIR = os.path.join(BASE_DIR, "01_raw")
SCRATCH_DIR = os.path.join(BASE_DIR, "scratch")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(SCRATCH_DIR, exist_ok=True)

# Files to move into 01_raw
raw_items = [
    "companies_with_details.csv",
    "NEPSE Data.csv",
    "NEPSE INDEX APR 2004 TO APR 2024.xlsx",
    "nepsealpha_export_price_NEPSE_2021-10-14_2026-10-03_adjusted.xlsx",
    "nepse_index_history.csv",
    "nepse-data-main",
    "nepse-historical-market-data-csv-master"
]

# Files to move into scratch
scratch_items = [
    "STH STH.md",
    "scratch_inventory.json"
]

print("Organizing Workspace Directory Structure...")

for item in raw_items:
    src = os.path.join(BASE_DIR, item)
    dst = os.path.join(RAW_DIR, item)
    if os.path.exists(src):
        if not os.path.exists(dst):
            shutil.move(src, dst)
            print(f"Moved -> 01_raw/{item}")
        else:
            print(f"Already in 01_raw/ -> {item}")

for item in scratch_items:
    src = os.path.join(BASE_DIR, item)
    dst = os.path.join(SCRATCH_DIR, item)
    if os.path.exists(src):
        if not os.path.exists(dst):
            shutil.move(src, dst)
            print(f"Moved -> scratch/{item}")
        else:
            print(f"Already in scratch/ -> {item}")

print("\nWorkspace Organization Complete!")
