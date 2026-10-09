import os
import sys
import time
import glob
from pathlib import Path
import duckdb
import pandas as pd

BASE_DIR = Path(os.environ.get("NEPSE_BASE_DIR", r"C:/Users/achar/Downloads/neps"))
RAW_DIR = BASE_DIR / "01_raw"
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
DAILY_DIR = BASE_DIR / "nepse_data_all"
SCRAPER_REPO = RAW_DIR / "nepse-historical-scraper-repo"

def classify_security(ticker):
    t = str(ticker).upper().strip()
    if t.endswith("PO") or (t.endswith("P") and len(t) > 4 and not t.endswith("GROUP")):
        return "PROMOTER"
    elif "D8" in t or "D20" in t or t.startswith("GBD") or t.endswith("D83") or t.endswith("D86") or t.endswith("D85") or t.endswith("D88"):
        return "DEBENTURE"
    elif t.endswith("F1") or t.endswith("F2") or t.endswith("F3") or t.endswith("SF") or t.endswith("MF") or t in ["SEF", "SEOS", "SIGS2", "NIBLPF", "NICGF", "NICBF", "NICSF", "LEMF", "AMFI", "PSF"]:
        return "MUTUAL_FUND"
    elif t.endswith("BSL") or t.endswith("LBS") or t.endswith("BS") or t.endswith("BBL") or t in ["KMCDB", "DDBL", "SKBBL", "WOMI", "FMDBL", "CBBL"]:
        return "MICROFINANCE"
    else:
        return "ORDINARY_EQUITY"

def build_market_master_union():
    print("=" * 70)
    print("STEP 1: DUCKDB OUT-OF-CORE DEDUPLICATION & MULTI-REPO UNION")
    print("=" * 70)

    t0 = time.time()
    con = duckdb.connect(database=":memory:")

    q_daily = f"""
    SELECT 
        UPPER(TRIM(COALESCE(Symbol, ticker, symbol))) as ticker,
        COALESCE(date, businessDate, TRY_CAST(REPLACE(REGEXP_EXTRACT(filename, '([0-9]{{4}}_[0-9]{{2}}_[0-9]{{2}})', 1), '_', '-') AS DATE)) as date,
        COALESCE(TRY_CAST(REPLACE(CAST(Open AS VARCHAR), ',', '') AS DOUBLE), openPrice, TRY_CAST(REPLACE(CAST(open AS VARCHAR), ',', '') AS DOUBLE)) as open,
        COALESCE(TRY_CAST(REPLACE(CAST(High AS VARCHAR), ',', '') AS DOUBLE), highPrice, TRY_CAST(REPLACE(CAST(high AS VARCHAR), ',', '') AS DOUBLE)) as high,
        COALESCE(TRY_CAST(REPLACE(CAST(Low AS VARCHAR), ',', '') AS DOUBLE), lowPrice, TRY_CAST(REPLACE(CAST(low AS VARCHAR), ',', '') AS DOUBLE)) as low,
        COALESCE(TRY_CAST(REPLACE(CAST(Close AS VARCHAR), ',', '') AS DOUBLE), closePrice, TRY_CAST(REPLACE(CAST(close AS VARCHAR), ',', '') AS DOUBLE), TRY_CAST(REPLACE(CAST(LTP AS VARCHAR), ',', '') AS DOUBLE)) as close,
        COALESCE(TRY_CAST(REPLACE(CAST(Vol AS VARCHAR), ',', '') AS DOUBLE), TRY_CAST(totalTradedQuantity AS DOUBLE), TRY_CAST(REPLACE(CAST(volume AS VARCHAR), ',', '') AS DOUBLE), 0.0) as volume,
        1 as priority
    FROM read_csv_auto('{str(DAILY_DIR / "*.csv").replace('\\', '/')}', filename=True, union_by_name=True, ignore_errors=True)
    WHERE COALESCE(Symbol, ticker, symbol) IS NOT NULL
    """

    q_scraper = f"""
    SELECT 
        UPPER(TRIM(symbol)) as ticker,
        CAST(time AS DATE) as date,
        CAST(open AS DOUBLE) as open,
        CAST(high AS DOUBLE) as high,
        CAST(low AS DOUBLE) as low,
        CAST(close AS DOUBLE) as close,
        CAST(COALESCE(volume, 0.0) AS DOUBLE) as volume,
        2 as priority
    FROM read_csv_auto('{str(SCRAPER_REPO / "data" / "stock" / "unadjusted" / "*.csv").replace('\\', '/')}', filename=True, union_by_name=True, ignore_errors=True)
    WHERE symbol IS NOT NULL
    """

    q_ticker = f"""
    SELECT 
        UPPER(TRIM(COALESCE(symbol, REGEXP_EXTRACT(filename, '([^\\\\/]+?)(?:_[0-9]{{4}}|\\.)', 1)))) as ticker,
        COALESCE(Date, published_date, trade_date) as date,
        COALESCE(open, TRY_CAST(REPLACE(CAST(open_price AS VARCHAR), ',', '') AS DOUBLE), "Close Price", close) as open,
        COALESCE(high, "Max. Price", TRY_CAST(REPLACE(CAST(high_price AS VARCHAR), ',', '') AS DOUBLE), close, "Close Price") as high,
        COALESCE(low, "Min. Price", TRY_CAST(REPLACE(CAST(low_price AS VARCHAR), ',', '') AS DOUBLE), close, "Close Price") as low,
        COALESCE(close, "Close Price", TRY_CAST(REPLACE(CAST(close_price AS VARCHAR), ',', '') AS DOUBLE), TRY_CAST(REPLACE(CAST(ltp AS VARCHAR), ',', '') AS DOUBLE)) as close,
        COALESCE("Total Traded Shares", traded_quantity, TRY_CAST(REPLACE(CAST(volume AS VARCHAR), ',', '') AS DOUBLE), 0.0) as volume,
        3 as priority
    FROM read_csv_auto('{str(RAW_DIR / "ticker_csvs" / "*.csv").replace('\\', '/')}', filename=True, union_by_name=True, ignore_errors=True)
    """

    con.execute(f"""
    CREATE TABLE all_sources AS 
    SELECT * FROM ({q_daily}) WHERE close > 0 AND date IS NOT NULL
    UNION ALL
    SELECT * FROM ({q_scraper}) WHERE close > 0 AND date IS NOT NULL
    UNION ALL
    SELECT * FROM ({q_ticker}) WHERE close > 0 AND date IS NOT NULL
    """)

    raw_cnt = con.execute("SELECT count(*) FROM all_sources").fetchone()[0]
    print(f"Loaded {raw_cnt:,} total raw rows in {time.time() - t0:.2f}s.")

    dedup_sql = """
    WITH ranked AS (
        SELECT ticker, date, open, high, low, close, volume,
               ROW_NUMBER() OVER (
                   PARTITION BY ticker, date 
                   ORDER BY priority ASC, volume DESC, close DESC
               ) as rn
        FROM all_sources
        WHERE ticker NOT IN ('RAW', 'NEPSE', 'MARKET', 'INDEX', 'SYMBOL')
    )
    SELECT ticker, date, open, high, low, close, volume
    FROM ranked
    WHERE rn = 1
    ORDER BY ticker ASC, date ASC
    """
    
    con.execute(f"CREATE TABLE master_union AS {dedup_sql}")
    df_m = con.execute("SELECT * FROM master_union").df()
    df_m['security_type'] = df_m['ticker'].apply(classify_security)
    
    target_parquet = PROCESSED_DIR / "market_master_union.parquet"
    df_m.to_parquet(target_parquet, compression="zstd", index=False)
    
    by_sec_dir = PROCESSED_DIR / "by_security_type"
    con.register("df_m_view", df_m)
    con.execute(f"""
        COPY df_m_view TO '{str(by_sec_dir).replace('\\', '/')}' 
        (FORMAT PARQUET, PARTITION_BY (security_type), COMPRESSION ZSTD, OVERWRITE_OR_IGNORE TRUE)
    """)
    
    elapsed = time.time() - t0
    min_date = df_m['date'].min()
    max_date = df_m['date'].max()
    print(f"Master Union Parquet built successfully in {elapsed:.2f}s!")
    print(f"Total Rows:     {len(df_m):,}")
    print(f"Unique Tickers: {df_m['ticker'].nunique()}")
    print(f"Date Range:     {min_date} to {max_date}")
    print(f"Output File:    {target_parquet}")

if __name__ == "__main__":
    build_market_master_union()
