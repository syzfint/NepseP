#!/usr/bin/env python3
"""
ApexMarketEngine — Feature Engineering & Microstructure Store
=============================================================
Calculates:
  1. Scale-Invariant Multi-Period Moving Averages & Volatility (t-1 lag enforced)
  2. K-Line Pattern Semantics (Upper/Lower Shadow Ratios, Body Density, Gap Rejections)
  3. Price + Volume Coupling (Volume Z-Scores, Force Index, OBV Slope Divergence, Amihud)
  4. NEPSE Floor Sheet Broker Accumulation Concentration (when available)
"""

import os
import sys
import time
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

# Multi-workspace resolution
BASE_DIR = Path.cwd()
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")


def resolve_path(relative_path: str) -> Path:
    p = BASE_DIR / relative_path
    if p.exists():
        return p
    alt = ALT_DIR / relative_path
    if alt.exists():
        return alt
    return p


def sync_to_both(src_path: Path, filename: str):
    for b in [BASE_DIR, ALT_DIR]:
        if b.exists():
            dest = b / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest != src_path:
                try:
                    dest.write_bytes(src_path.read_bytes())
                except Exception:
                    pass


def add_price_volume_and_kline_semantics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates Price-Volume Coupling & Candlestick Geometry Features for

    LightGBM / Gate G4 Meta-Labeler.
    """
    eps = 1e-6
    # Ensure correct symbol column name
    sym_col = "symbol" if "symbol" in df.columns else "ticker"
    df = df.sort_values([sym_col, "date"]).copy()

    # --- 1. Candlestick Geometry (K-Line Semantics) ---
    range_high_low = df["high"] - df["low"] + eps
    body_size = (df["close"] - df["open"]).abs()

    df["kline_upper_shadow_ratio"] = (
        df["high"] - df[["open", "close"]].max(axis=1)
    ) / range_high_low
    df["kline_lower_shadow_ratio"] = (
        df[["open", "close"]].min(axis=1) - df["low"]
    ) / range_high_low
    df["kline_body_density"] = body_size / range_high_low

    # Gap-Up Rejection (Bull Trap Flag)
    prev_close = df.groupby(sym_col)["close"].shift(1)
    gap_pct = (df["open"] - prev_close) / (prev_close + eps)
    intraday_ret = (df["close"] - df["open"]) / (df["open"] + eps)
    df["kline_gap_rejection_flag"] = (
        (gap_pct > 0.02) & (intraday_ret < -0.015)
    ).astype(float)

    # Donchian Proximity (Channel Base / Ceiling Proximity)
    roll_high_20 = (
        df.groupby(sym_col)["high"]
        .transform(lambda x: x.rolling(20, min_periods=5).max())
    )
    roll_low_20 = (
        df.groupby(sym_col)["low"]
        .transform(lambda x: x.rolling(20, min_periods=5).min())
    )
    df["donchian_channel_pos_20"] = (df["close"] - roll_low_20) / (
        roll_high_20 - roll_low_20 + eps
    )

    # --- 2. Price + Volume Coupling ---
    vol_mean_20 = (
        df.groupby(sym_col)["volume"]
        .transform(lambda x: x.rolling(20, min_periods=5).mean())
    )
    vol_std_20 = (
        df.groupby(sym_col)["volume"]
        .transform(lambda x: x.rolling(20, min_periods=5).std())
    )
    df["volume_zscore_20"] = (df["volume"] - vol_mean_20) / (vol_std_20 + eps)

    # Price Return (1-session)
    ret_1d = df.groupby(sym_col)["close"].pct_change()

    # Force Index (Volume-Confirmed Return)
    df["volume_force_index"] = ret_1d * df["volume_zscore_20"]

    # OBV Trend Divergence (5-session slope)
    df["_obv_step"] = np.sign(ret_1d).fillna(0) * df["volume"]
    df["obv"] = df.groupby(sym_col)["_obv_step"].cumsum()

    obv_shift_5 = df.groupby(sym_col)["obv"].shift(5)
    obv_slope_5 = (df["obv"] - obv_shift_5) / (obv_shift_5.abs() + eps)

    price_shift_5 = df.groupby(sym_col)["close"].shift(5)
    price_slope_5 = (df["close"] - price_shift_5) / (price_shift_5 + eps)

    # Negative value = Bearish Volume Divergence
    df["price_volume_divergence_5d"] = obv_slope_5 - price_slope_5

    # Amihud Illiquidity Ratio
    turnover = df["close"] * df["volume"]
    df["amihud_illiquidity"] = ret_1d.abs() / (turnover + eps)

    # Cleanup temporary columns
    df.drop(columns=["_obv_step"], inplace=True)

    return df


def run_feature_engineering():
    print("=" * 80)
    print("STEP 2: SCALE-INVARIANT FEATURE STORE & K-LINE / PRICE-VOLUME SEMANTICS")
    print("=" * 80)

    t0 = time.time()
    target_parquet = resolve_path("02_processed_parquet/market_master_union.parquet")
    tech_out = BASE_DIR / "03_feature_store" / "technical_indicators.parquet"
    floorsheet_path = resolve_path("03_feature_store/floorsheet_broker_signals.parquet")

    if not target_parquet.exists():
        print(f"Error: {target_parquet} not found. Run Step 1 first!")
        return

    print(f"Reading from Lakehouse: {target_parquet}")
    con = duckdb.connect(database=":memory:")

    sql = f"""
    WITH base AS (
        SELECT 
            ticker,
            CAST(date AS DATE) as date,
            open, high, low, close, volume,
            security_type,
            close * volume AS turnover,
            LAG(close, 1) OVER w AS prev_close,
            LAG(volume, 1) OVER w AS prev_vol,
            AVG(volume) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS adv_20d,
            AVG(close * volume) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS turnover_20d,
            SUM(CASE WHEN volume > 0 THEN 1 ELSE 0 END) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS active_days_20d,
            AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS sma_20,
            AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 50 PRECEDING AND 1 PRECEDING) AS sma_50,
            STDDEV(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS std_20,
            LAG(close, 5) OVER w AS close_lag5,
            LAG(close, 10) OVER w AS close_lag10,
            LAG(close, 20) OVER w AS close_lag20
        FROM read_parquet('{str(target_parquet).replace('\\', '/')}')
        WHERE security_type IN ('ORDINARY_EQUITY', 'MICROFINANCE')
        WINDOW w AS (PARTITION BY ticker ORDER BY date)
    )
    SELECT 
        ticker, date, open, high, low, close, volume, security_type,
        adv_20d, turnover_20d, active_days_20d,
        sma_20, sma_50,
        ((prev_close / (sma_20 + 1e-6)) - 1.0) AS dist_sma20,
        ((prev_close / (sma_50 + 1e-6)) - 1.0) AS dist_sma50,
        (((prev_close - (sma_20 - 2.0 * std_20)) / (4.0 * std_20 + 1e-6))) AS bb_pct_b,
        ((prev_close / (close_lag5 + 1e-6)) - 1.0) AS ret_1w,
        ((prev_close / (close_lag10 + 1e-6)) - 1.0) AS ret_2w,
        ((prev_close / (close_lag20 + 1e-6)) - 1.0) AS ret_1m,
        (std_20 / (sma_20 + 1e-6)) AS volatility_20,
        ((prev_vol / (adv_20d + 1e-4)) - 1.0) AS vol_surge
    FROM base
    ORDER BY ticker ASC, date ASC
    """

    print("Computing DuckDB base window aggregations...")
    df_base = con.execute(sql).df()
    con.close()

    print(f"Base rows: {len(df_base):,}. Appending K-line & Price-Volume Semantics...")
    df_enriched = add_price_volume_and_kline_semantics(df_base)

    # Optional Floorsheet Broker Concentration Join
    if floorsheet_path.exists():
        print("Enriching with NEPSE Floor Sheet Top-Buyer Concentration signals...")
        con_fs = duckdb.connect(database=":memory:")
        con_fs.register("enriched", df_enriched)
        join_sql = f"""
            SELECT 
                e.*,
                COALESCE(f.top3_buyer_share, 0.0) AS top_buyer_concentration,
                COALESCE(f.buyer_hhi, 0.0) AS buyer_hhi,
                COALESCE(f.net_hhi_imbalance, 0.0) AS broker_net_imbalance
            FROM enriched e
            LEFT JOIN read_parquet('{str(floorsheet_path).replace('\\', '/')}') f
              ON e.ticker = f.ticker AND e.date = CAST(f.date AS DATE)
            ORDER BY e.ticker ASC, e.date ASC
        """
        df_final = con_fs.execute(join_sql).df()
        con_fs.close()
    else:
        df_final = df_enriched
        df_final["top_buyer_concentration"] = 0.0
        df_final["buyer_hhi"] = 0.0
        df_final["broker_net_imbalance"] = 0.0

    # Save to Parquet
    tech_out.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_parquet(tech_out, index=False)
    sync_to_both(tech_out, "03_feature_store/technical_indicators.parquet")

    # Register view in market_analytics.duckdb
    for b in [BASE_DIR, ALT_DIR]:
        duckdb_file = b / "02_processed_parquet" / "market_analytics.duckdb"
        if duckdb_file.exists():
            con_db = duckdb.connect(str(duckdb_file))
            con_db.execute(f"""
                CREATE OR REPLACE VIEW technical_indicators AS 
                SELECT * FROM read_parquet('{str(tech_out).replace('\\', '/')}')
            """)
            con_db.close()

    elapsed = time.time() - t0
    print(f"\nFeature Store updated successfully in {elapsed:.2f}s!")
    print(f"Output File : {tech_out}")
    print(f"Feature Rows: {len(df_final):,} | Total Columns: {len(df_final.columns)}")
    print("New Microstructure Features Appended:")
    print("  - kline_upper_shadow_ratio, kline_lower_shadow_ratio, kline_body_density")
    print("  - kline_gap_rejection_flag, donchian_channel_pos_20")
    print("  - volume_zscore_20, volume_force_index, price_volume_divergence_5d, amihud_illiquidity")
    print("  - top_buyer_concentration, buyer_hhi, broker_net_imbalance")
    print("=" * 80)


if __name__ == "__main__":
    run_feature_engineering()
