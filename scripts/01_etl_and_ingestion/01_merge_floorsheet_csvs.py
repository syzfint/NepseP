import os
import glob
import pandas as pd

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
base_dir = str(BASE_DIR / "archive (3)" / "NEPSE_data")
output_file = str(BASE_DIR / "archive (3)" / "NEPSE_all_data.csv")

all_files = glob.glob(os.path.join(base_dir, "**", "*.csv"), recursive=True)

df_list = []
for file in all_files:
    try:
        df = pd.read_csv(file)
        # Add a column for the filename or date if needed, but not strictly necessary unless requested
        # df['source_file'] = os.path.basename(file)
        df_list.append(df)
    except Exception as e:
        print(f"Error reading {file}: {e}")

if df_list:
    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.to_csv(output_file, index=False)
    print(f"Successfully combined {len(df_list)} files into {output_file}")
else:
    print("No CSV files found.")
