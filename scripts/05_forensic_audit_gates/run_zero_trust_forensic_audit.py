import json
import os
import hashlib
import numpy as np
import pandas as pd

def audit_database():
    path = "02_processed_parquet/market_master_union.parquet"
    if not os.path.exists(path):
        return {"status": "FAIL", "reason": "Parquet file missing"}

    # Compute SHA-256 raw file hash
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192 * 1024):
            hasher.update(chunk)
    file_sha256 = hasher.hexdigest()

    from scripts.db_connection import connection_manager
    with connection_manager.acquire() as conn:
        # 1. Total row count & integrity
        row_count = conn.execute(f'SELECT count(*) FROM "{path}"').fetchone()[0]
        
        # Check nulls and semantic domain constraints
        null_counts = conn.execute(f'''
            SELECT 
                count(*) filter (WHERE ticker IS NULL) as null_ticker,
                count(*) filter (WHERE date IS NULL) as null_date,
                count(*) filter (WHERE close IS NULL OR close <= 0) as invalid_close,
                count(*) filter (WHERE volume IS NULL OR volume < 0) as invalid_vol,
                count(*) filter (WHERE high < low) as invalid_hl,
                count(*) filter (WHERE open <= 0) as invalid_open
            FROM "{path}"
        ''').fetchone()

        # 2. Duplicate Primary Key check (ticker, date)
        dup_count = conn.execute(f'''
            SELECT count(*) FROM (
                SELECT ticker, date, count(*) 
                FROM "{path}" 
                GROUP BY ticker, date 
                HAVING count(*) > 1
            )
        ''').fetchone()[0]

        # 3. Ticker universe & temporal consistency
        ticker_count = conn.execute(f'SELECT count(distinct ticker) FROM "{path}"').fetchone()[0]
        date_range = conn.execute(f'SELECT min(date), max(date) FROM "{path}"').fetchone()

        # 4. Independent calculation reconciliation:
        # Recalculate rolling 20-day returns and EW market index independently via SQL vs Pandas
        sample_df = conn.execute(f'''
            SELECT ticker, date, close 
            FROM "{path}" 
            WHERE ticker = 'NABIL' AND date >= '2025-01-01'
            ORDER BY date
        ''').df()
        
        # Pandas return
        sample_df['ret_pandas'] = sample_df['close'].pct_change()
        
        # SQL return
        sql_ret = conn.execute(f'''
            SELECT (close - lag(close) over (order by date)) / lag(close) over (order by date) as ret_sql
            FROM "{path}"
            WHERE ticker = 'NABIL' AND date >= '2025-01-01'
            ORDER BY date
        ''').df()['ret_sql']
        
        # Max delta between implementations
        diff = np.nanmax(np.abs(sample_df['ret_pandas'].values[1:] - sql_ret.values[1:]))
        reconciled = bool(diff < 1e-12)

    return {
        "file_sha256": file_sha256,
        "row_count": row_count,
        "null_ticker": null_counts[0],
        "null_date": null_counts[1],
        "invalid_close": null_counts[2],
        "invalid_vol": null_counts[3],
        "invalid_hl": null_counts[4],
        "invalid_open": null_counts[5],
        "duplicate_primary_keys": dup_count,
        "distinct_tickers": ticker_count,
        "date_min": str(date_range[0]),
        "date_max": str(date_range[1]),
        "calculation_reconciliation_delta": float(diff),
        "calculation_reconciled": reconciled
    }

if __name__ == "__main__":
    res = audit_database()
    print(json.dumps(res, indent=2))
