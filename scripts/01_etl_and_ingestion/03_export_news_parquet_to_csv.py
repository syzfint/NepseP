import os
import pandas as pd

print("Downloading dataset...")
# Load the dataset
df = pd.read_parquet("hf://datasets/thegauravgiri/nepali-news-dataset/data/train.parquet")

output_dir = "nepali_news_structured"
print(f"Structuring data into '{output_dir}' directory...")

# Clean up date column to create time-based partitions (year and month)
# This will handle dates properly and fallback to 'unknown' if the date is missing/invalid
df['parsed_date'] = pd.to_datetime(df['date'], errors='coerce')
df['year'] = df['parsed_date'].dt.year.fillna(0).astype(int).astype(str).replace('0', 'unknown')
df['month'] = df['parsed_date'].dt.month.fillna(0).astype(int).astype(str).str.zfill(2).replace('00', 'unknown')

# Drop the temporary parsed_date column as we don't need to store it
df = df.drop(columns=['parsed_date'])

# Handle missing sources to prevent folder creation errors
df['source'] = df['source'].fillna('unknown_source').astype(str)

# Ensure the output directory exists
os.makedirs(output_dir, exist_ok=True)

# Save the dataset to the folder partitioned by Source and Year
# This creates a structured schema like: nepali_news_structured/source=.../year=.../data.parquet
df.to_parquet(output_dir, partition_cols=['source', 'year'], index=False)

print("Done! All data has been successfully stored in the structured schema.")
