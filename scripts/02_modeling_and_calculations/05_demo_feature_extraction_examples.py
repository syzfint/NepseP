# 1. Using HuggingFace datasets library
from datasets import load_dataset
print("Loading with datasets...")
ds_hf = load_dataset("thegauravgiri/nepali-news-dataset")
print(ds_hf)

# 2. Using Pandas
import pandas as pd
print("\nLoading with pandas...")
df_pd = pd.read_parquet("hf://datasets/thegauravgiri/nepali-news-dataset/data/train.parquet")
print(df_pd.head())

# 3. Using Polars
import polars as pl
print("\nLoading with polars...")
df_pl = pl.read_parquet("hf://datasets/thegauravgiri/nepali-news-dataset/data/train.parquet")
print(df_pl.head())

# 4. Using mlcroissant (requires mlcroissant library)
try:
    from mlcroissant import Dataset
    print("\nLoading with mlcroissant...")
    ds_croissant = Dataset(jsonld="https://huggingface.co/api/datasets/thegauravgiri/nepali-news-dataset/croissant")
    records = ds_croissant.records("default")
    print(next(iter(records)))
except ImportError:
    print("\nmlcroissant is not installed. To use it, install with: pip install mlcroissant")
