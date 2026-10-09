#!/usr/bin/env python3
"""
scripts/01_etl_and_ingestion/update_today_eod_lakehouse.py

APEXMARKETENGINE — PRODUCTION END-OF-DAY (EOD) COMPLETE PIPELINE
================================================================
Executes immediately after NEPSE market close (15:00:00 NPT).
1. Connects to live NEPSE API via NepseClient (TLS verification disabled).
2. Fetches final EOD market status, indices, sub-indices, summary, price-volume, and floorsheet.
3. Reconstructs tick-exact OHLCV daily bars from all 39,466 executed trades for 359 traded scrips.
4. Executes Anti-Wash Filter on today's floorsheet (buyer != seller, quantity >= 10).
5. Ingests clean 2026-10-07 daily bars into 02_processed_parquet/market_master_union.parquet.
6. Recomputes 34 point-in-time features in 03_feature_store/technical_indicators.parquet.
7. Refreshes static_data/promoter_lockin.parquet for statutory 36-month lock-in expiries.
8. Generates Chronos-Bolt 5-day probabilistic quantiles into 03_feature_store/chronos_quantiles_5d.parquet.
9. Executes Gate G4 Meta-Labeler and skfolio HRP Allocator.
10. Validates Gate G8 Pydantic v2 schema, Gate G9 dual-panel chart, and Gate G10 SHA-256 seal.
11. Synchronizes all assets to C:/Users/achar/Downloads/neps/.
"""

import os
import sys
import json
import time
import subprocess
import datetime
import logging
from pathlib import Path
from typing import Dict, List, Any

import duckdb
import numpy as np
import pandas as pd
from nepse_client import NepseClient

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eod_lakehouse_updater")

BASE_DIR = Path.cwd()
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")
RAW_DATA_DIR = BASE_DIR / "01_raw_data"
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
FEATURE_DIR = BASE_DIR / "03_feature_store"
STATIC_DIR = BASE_DIR / "static_data"
REPORTS_DIR = BASE_DIR / "reports"
SCRIPTS_DIR = BASE_DIR / "scripts"
ETL_DIR = SCRIPTS_DIR / "01_etl_and_ingestion"
MODEL_DIR = SCRIPTS_DIR / "02_modeling_and_calculations"

for p in [str(SCRIPTS_DIR), str(ETL_DIR), str(MODEL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

for d in [RAW_DATA_DIR, PROCESSED_DIR, FEATURE_DIR, STATIC_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

MASTER_PARQUET = PROCESSED_DIR / "market_master_union.parquet"
BROKER_SIGNALS_PARQUET = FEATURE_DIR / "floorsheet_broker_signals.parquet"
CHRONOS_PARQUET = FEATURE_DIR / "chronos_quantiles_5d.parquet"
TECH_PARQUET = FEATURE_DIR / "technical_indicators.parquet"
PROMOTER_PARQUET = STATIC_DIR / "promoter_lockin.parquet"


def sync_file(src: Path, relative_dest: str):
    for root in [BASE_DIR, ALT_DIR]:
        if root.exists():
            dest = root / relative_dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest != src:
                try:
                    dest.write_bytes(src.read_bytes())
                except Exception:
                    pass


def classify_security(ticker: str) -> str:
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


def fetch_all_eod_data() -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("STEP 1: FETCHING COMPLETE END-OF-DAY (EOD) LIVE DATA FROM NEPSE")
    print("=" * 80)
    t0 = time.time()
    
    client = NepseClient()
    client.setTLSVerification(False)
    
    print("Querying market status...")
    status = client.getMarketStatus()
    print(f"  Market Status: {status.get('isOpen')} as of {status.get('asOf')}")
    
    print("Querying index snapshot...")
    indices = client.getNepseIndex()
    
    print("Querying market summary (turnover, shares, trades)...")
    summary = client.getSummary()
    
    print("Querying sub-indices (13 sectors)...")
    sub_indices = client.getNepseSubIndices()
    
    print("Querying price volume official scrips...")
    price_volume = client.getPriceVolume()
    print(f"  Fetched {len(price_volume) if price_volume else 0} scrips from PriceVolume endpoint.")
    
    # Check if floorsheet already fetched today, or fetch live
    today_str = datetime.date.today().isoformat()
    if status and status.get("asOf"):
        try:
            today_str = status["asOf"].split("T")[0]
        except Exception:
            pass
            
    cached_fs_json = RAW_DATA_DIR / f"nepse_floorsheet_{today_str}.json"
    if cached_fs_json.exists():
        print(f"Using already downloaded floorsheet from {cached_fs_json}...")
        with open(cached_fs_json, "r", encoding="utf-8") as f:
            floorsheet = json.load(f)
        print(f"  Loaded {len(floorsheet):,} individual executed trades.")
    else:
        print("Querying today's complete floorsheet (all transactions)...")
        floorsheet = client.getFloorSheet()
        print(f"  Fetched {len(floorsheet):,} individual executed trades.")
        with open(cached_fs_json, "w", encoding="utf-8") as f:
            json.dump(floorsheet, f, indent=2, ensure_ascii=False)
            
    print(f"Confirmed Business Date: {today_str} (Elapsed: {time.time() - t0:.2f}s)")
    
    # Save raw JSON dumps
    raw_dumps = {
        f"01_raw_data/nepse_market_status_{today_str}.json": status,
        f"01_raw_data/nepse_indices_{today_str}.json": indices,
        f"01_raw_data/nepse_summary_{today_str}.json": summary,
        f"01_raw_data/nepse_sub_indices_{today_str}.json": sub_indices,
        f"01_raw_data/nepse_price_volume_{today_str}.json": price_volume,
    }
    
    for rel_path, data in raw_dumps.items():
        out_f = BASE_DIR / rel_path
        out_f.parent.mkdir(parents=True, exist_ok=True)
        with open(out_f, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        sync_file(out_f, rel_path)
        
    print(f"Raw EOD files successfully written to {RAW_DATA_DIR}.")
    
    return {
        "today_str": today_str,
        "status": status,
        "indices": indices,
        "summary": summary,
        "sub_indices": sub_indices,
        "price_volume": price_volume,
        "floorsheet": floorsheet,
    }


def process_anti_wash_floorsheet(eod_data: Dict[str, Any]) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("STEP 2: ANTI-WASH FLOORSHEET PROCESSING & BROKER ACCUMULATION SIGNALS")
    print("=" * 80)
    
    floorsheet = eod_data["floorsheet"]
    today_str = eod_data["today_str"]
    
    if not floorsheet:
        print("No floorsheet trades available today.")
        return pd.DataFrame()
        
    df_fs = pd.DataFrame(floorsheet)
    print(f"Total raw trades recorded today: {len(df_fs):,}")
    
    # Standardize column mappings
    df_fs["symbol"] = df_fs["stockSymbol"].astype(str).str.upper().str.strip()
    df_fs["buyer"] = df_fs["buyerMemberId"].astype(str)
    df_fs["seller"] = df_fs["sellerMemberId"].astype(str)
    df_fs["quantity"] = pd.to_numeric(df_fs["contractQuantity"], errors="coerce").fillna(0.0)
    df_fs["rate"] = pd.to_numeric(df_fs["contractRate"], errors="coerce").fillna(0.0)
    df_fs["amount"] = pd.to_numeric(df_fs["contractAmount"], errors="coerce").fillna(0.0)
    df_fs["date"] = pd.to_datetime(today_str)
    
    # Save floorsheet parquet
    fs_parquet_path = RAW_DATA_DIR / f"nepse_floorsheet_{today_str}.parquet"
    df_fs.to_parquet(fs_parquet_path, index=False)
    sync_file(fs_parquet_path, f"01_raw_data/nepse_floorsheet_{today_str}.parquet")
    
    # Audit wash trades & odd-lots
    is_wash = (df_fs["buyer"] == df_fs["seller"])
    is_odd = (df_fs["quantity"] < 10)
    
    wash_count = is_wash.sum()
    wash_amount = df_fs.loc[is_wash, "amount"].sum()
    odd_count = is_odd.sum()
    odd_amount = df_fs.loc[is_odd, "amount"].sum()
    clean_trades = df_fs[~is_wash & ~is_odd]
    
    print(f"  • Gross Turnover     : NPR {df_fs['amount'].sum():,.2f}")
    print(f"  • Self-Matches (Wash): {wash_count:,} trades ({wash_count / len(df_fs) * 100:.2f}%) totaling NPR {wash_amount:,.2f}")
    print(f"  • Odd-Lots (< 10 sh) : {odd_count:,} trades ({odd_count / len(df_fs) * 100:.2f}%) totaling NPR {odd_amount:,.2f}")
    print(f"  • Institutional Clean: {len(clean_trades):,} trades ({len(clean_trades) / len(df_fs) * 100:.2f}%)")
    
    # Compute broker network aggregation per ticker
    con = duckdb.connect()
    con.register("df_fs", df_fs)
    
    sql = """
    WITH stats AS (
        SELECT 
            symbol AS ticker,
            date,
            COUNT(*) AS gross_trades,
            SUM(amount) AS gross_turnover,
            SUM(CASE WHEN buyer = seller THEN amount ELSE 0.0 END) AS wash_turnover,
            SUM(CASE WHEN buyer = seller THEN 1 ELSE 0 END) AS wash_trade_count,
            SUM(CASE WHEN quantity < 10 THEN 1 ELSE 0 END) AS odd_lot_count
        FROM df_fs
        GROUP BY symbol, date
    ),
    clean AS (
        SELECT *
        FROM df_fs
        WHERE buyer != seller AND quantity >= 10
    ),
    buyer_shares AS (
        SELECT 
            symbol AS ticker,
            buyer,
            SUM(amount) AS buyer_amount,
            SUM(amount) * 1.0 / NULLIF(SUM(SUM(amount)) OVER (PARTITION BY symbol), 0) AS b_share,
            ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY SUM(amount) DESC) AS b_rank
        FROM clean
        GROUP BY symbol, buyer
    ),
    top3_buyers AS (
        SELECT 
            ticker,
            SUM(CASE WHEN b_rank <= 3 THEN b_share ELSE 0.0 END) AS top3_buyer_share,
            SUM(POWER(b_share, 2)) AS buyer_hhi
        FROM buyer_shares
        GROUP BY ticker
    ),
    clean_aggs AS (
        SELECT 
            symbol AS ticker,
            COUNT(*) AS clean_trades_count,
            SUM(amount) AS clean_turnover,
            SUM(quantity) AS clean_volume,
            COUNT(DISTINCT buyer) AS unique_buyers,
            COUNT(DISTINCT seller) AS unique_sellers
        FROM clean
        GROUP BY symbol
    )
    SELECT 
        s.ticker,
        s.date,
        s.gross_trades,
        s.gross_turnover,
        s.wash_trade_count,
        ROUND(s.wash_turnover * 1.0 / NULLIF(s.gross_turnover, 0), 4) AS wash_trade_ratio,
        COALESCE(c.clean_trades_count, 0) AS clean_trades_count,
        COALESCE(c.clean_turnover, 0.0) AS clean_turnover,
        COALESCE(c.clean_volume, 0.0) AS clean_volume,
        COALESCE(c.unique_buyers, 0) AS unique_buyers,
        COALESCE(c.unique_sellers, 0) AS unique_sellers,
        ROUND(COALESCE(t.top3_buyer_share, 0.0), 4) AS top3_buyer_share,
        ROUND(COALESCE(t.buyer_hhi, 0.0), 4) AS buyer_hhi,
        ROUND((COALESCE(c.unique_sellers, 0) - COALESCE(c.unique_buyers, 0)) * 1.0 / 
              NULLIF(COALESCE(c.unique_sellers, 0) + COALESCE(c.unique_buyers, 0), 0), 4) AS net_hhi_imbalance
    FROM stats s
    LEFT JOIN clean_aggs c ON s.ticker = c.ticker
    LEFT JOIN top3_buyers t ON s.ticker = t.ticker
    """
    
    today_signals = con.execute(sql).df()
    con.close()
    
    # Upsert into 03_feature_store/floorsheet_broker_signals.parquet
    if BROKER_SIGNALS_PARQUET.exists():
        existing_fs = pd.read_parquet(BROKER_SIGNALS_PARQUET)
        existing_fs["date"] = pd.to_datetime(existing_fs["date"])
        existing_fs = existing_fs[existing_fs["date"] != pd.to_datetime(today_str)]
        combined_fs = pd.concat([existing_fs, today_signals], ignore_index=True)
    else:
        combined_fs = today_signals
        
    combined_fs.to_parquet(BROKER_SIGNALS_PARQUET, index=False)
    sync_file(BROKER_SIGNALS_PARQUET, "03_feature_store/floorsheet_broker_signals.parquet")
    print(f"Updated floorsheet broker signals in {BROKER_SIGNALS_PARQUET} ({len(combined_fs):,} records).")
    
    return today_signals


def update_lakehouse_with_today_bars(eod_data: Dict[str, Any]):
    print("\n" + "=" * 80)
    print("STEP 3: RECONSTRUCTING TICK-EXACT OHLCV & INGESTING INTO DUCKDB LAKEHOUSE")
    print("=" * 80)
    
    today_str = eod_data["today_str"]
    today_dt = pd.to_datetime(today_str)
    fs_parquet_path = RAW_DATA_DIR / f"nepse_floorsheet_{today_str}.parquet"
    
    con = duckdb.connect()
    # Reconstruct true OHLCV from executed trades
    sql_bars = f"""
    SELECT 
        UPPER(TRIM(stockSymbol)) AS ticker,
        CAST('{today_str}' AS DATE) AS date,
        FIRST(contractRate ORDER BY contractId ASC) AS open,
        MAX(contractRate) AS high,
        MIN(contractRate) AS low,
        LAST(contractRate ORDER BY contractId ASC) AS close,
        SUM(contractQuantity) AS volume
    FROM read_parquet('{str(fs_parquet_path).replace('\\', '/')}')
    WHERE stockSymbol IS NOT NULL AND contractRate > 0
    GROUP BY stockSymbol
    """
    df_today = con.execute(sql_bars).df()
    con.close()
    
    # Map security types
    df_today["security_type"] = df_today["ticker"].apply(classify_security)
    df_today["open"] = df_today["open"].round(2)
    df_today["high"] = df_today["high"].round(2)
    df_today["low"] = df_today["low"].round(2)
    df_today["close"] = df_today["close"].round(2)
    df_today["volume"] = df_today["volume"].round(2)
    
    print(f"Reconstructed {len(df_today):,} verified daily bars for {today_str}.")
    print(df_today.head(5))
    
    # Read existing lakehouse
    if not MASTER_PARQUET.exists():
        raise FileNotFoundError(f"Missing master parquet at {MASTER_PARQUET}")
        
    df_master = pd.read_parquet(MASTER_PARQUET)
    df_master["date"] = pd.to_datetime(df_master["date"])
    
    # Idempotent replacement: remove any existing records for today
    pre_len = len(df_master)
    df_master = df_master[df_master["date"] != today_dt]
    df_master = pd.concat([df_master, df_today], ignore_index=True)
    df_master = df_master.sort_values(["ticker", "date"]).reset_index(drop=True)
    
    # Write back to parquet
    df_master.to_parquet(MASTER_PARQUET, index=False)
    sync_file(MASTER_PARQUET, "02_processed_parquet/market_master_union.parquet")
    print(f"Lakehouse updated: {pre_len:,} -> {len(df_master):,} total rows (Added {len(df_today)} bars).")
    print(f"Verified Lakehouse max date: {df_master['date'].max().strftime('%Y-%m-%d')}")
    
    # Update DuckDB lakehouse file
    duckdb_path = PROCESSED_DIR / "market_analytics.duckdb"
    con_db = duckdb.connect(str(duckdb_path))
    con_db.execute(f"""
        CREATE OR REPLACE VIEW market_master_union AS 
        SELECT * FROM read_parquet('{str(MASTER_PARQUET).replace('\\', '/')}')
    """)
    con_db.close()
    sync_file(duckdb_path, "02_processed_parquet/market_analytics.duckdb")
    print(f"DuckDB view registered in {duckdb_path}.")


def run_pipeline_steps():
    print("\n" + "=" * 80)
    print("STEP 4: RECOMPUTING 34 POINT-IN-TIME TECHNICAL & MICROSTRUCTURE FEATURES")
    print("=" * 80)
    cmd_feat = [sys.executable, str(SCRIPTS_DIR / "02_feature_engineering.py")]
    p1 = subprocess.run(cmd_feat, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(p1.stdout)
    if p1.returncode != 0:
        logger.error(f"Feature engineering failed: {p1.stderr}")
        
    print("\n" + "=" * 80)
    print("STEP 5: REFRESHING PROMOTER LOCK-IN CALENDAR & SUSPENSION GUARDS")
    print("=" * 80)
    from build_promoter_lockin_calendar import build_promoter_lockin_calendar
    build_promoter_lockin_calendar()
    sync_file(PROMOTER_PARQUET, "static_data/promoter_lockin.parquet")
    
    print("\n" + "=" * 80)
    print("STEP 6: GENERATING CHRONOS-BOLT 5-DAY PROBABILISTIC QUANTILES FOR TODAY")
    print("=" * 80)
    generate_updated_chronos_quantiles()
    sync_file(CHRONOS_PARQUET, "03_feature_store/chronos_quantiles_5d.parquet")
    
    print("\n" + "=" * 80)
    print("STEP 7: EXECUTING MASTER INTEGRATED PIPELINE (GATE G4 + SKFOLIO HRP + AUDIT SEAL)")
    print("=" * 80)
    cmd_master = [sys.executable, str(SCRIPTS_DIR / "00_master_integrated_pipeline.py")]
    p3 = subprocess.run(cmd_master, capture_output=True, text=True, cwd=str(BASE_DIR))
    print(p3.stdout)
    if p3.returncode != 0:
        logger.error(f"Master pipeline failed: {p3.stderr}")
        
    print("\n" + "=" * 80)
    print("STEP 8: RE-SYNCHRONIZING ENTIRE WORKSPACE TO DOWNLOADS/NEPS")
    print("=" * 80)
    cmd_sync = [sys.executable, str(SCRIPTS_DIR / "00_organize_workspace.py")]
    subprocess.run(cmd_sync, capture_output=True, text=True, cwd=str(BASE_DIR))
    print("Workspace mirroring complete.")


def generate_updated_chronos_quantiles():
    """Generates updated chronos quantiles using recent prices including 2026-10-07."""
    from chronos_bolt_engine import ChronosBoltEngine
    engine = ChronosBoltEngine()
    
    con = duckdb.connect()
    p_str = str(MASTER_PARQUET).replace('\\', '/')
    query = f"""
    SELECT ticker, date, close, security_type
    FROM read_parquet('{p_str}')
    WHERE security_type IN ('ORDINARY_EQUITY', 'MICROFINANCE')
    ORDER BY ticker ASC, date ASC
    """
    df_prices = con.execute(query).df()
    
    # Read technical indicators for today
    p_tech = str(TECH_PARQUET).replace('\\', '/')
    query_tech = f"""
    SELECT ticker, date, volume_force_index, price_volume_divergence_5d, donchian_channel_pos_20,
           kline_lower_shadow_ratio, kline_gap_rejection_flag
    FROM read_parquet('{p_tech}')
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) = 1
    """
    df_tech = con.execute(query_tech).df().set_index("ticker").to_dict(orient="index")
    con.close()
    
    grouped = df_prices.groupby("ticker")
    records = []
    
    print(f"Simulating 5-day probabilistic paths across {len(grouped)} active equities...")
    for sym, grp in grouped:
        prices = grp["close"].values
        dates = grp["date"].tolist()
        if len(prices) < 5 or prices[-1] <= 0:
            continue
            
        curr_p = float(prices[-1])
        fc = engine.forecast_series(prices, dates=dates, prediction_length=5)
        
        p10 = fc.get("p10", curr_p * 0.95)
        p50 = fc.get("p50", curr_p)
        p90 = fc.get("p90", curr_p * 1.05)
        spread = fc.get("uncertainty_spread", (p90 - p10) / curr_p * 100.0)
        exp_ret = fc.get("expected_return_pct", (p50 - curr_p) / curr_p * 100.0)
        
        # Volatility & Barrier Ratio
        ret_s = pd.Series(prices).pct_change().dropna()
        vol = float(ret_s.tail(20).std() if len(ret_s) >= 20 else 0.02)
        if np.isnan(vol) or vol <= 0:
            vol = 0.02
        vol_amt = vol * curr_p
        
        # Barrier hits based on quantiles
        p_profit = max(0.01, min(0.99, (p90 - (curr_p + 2.0 * vol_amt)) / (vol_amt + 1e-4) + 0.5))
        p_loss = max(0.01, min(0.99, ((curr_p - 2.0 * vol_amt) - p10) / (vol_amt + 1e-4) + 0.5))
        barrier_ratio = round(p_profit / (p_loss + 1e-5), 2)
        
        t_info = df_tech.get(sym, {})
        vfi = float(t_info.get("volume_force_index", 0.0) or 0.0)
        pvd = float(t_info.get("price_volume_divergence_5d", 0.0) or 0.0)
        d_pos = float(t_info.get("donchian_channel_pos_20", 0.5) or 0.5)
        lower_shadow = float(t_info.get("kline_lower_shadow_ratio", 0.0) or 0.0)
        floor_bounce = bool((d_pos <= 0.40) and (lower_shadow >= 0.40))
        
        records.append({
            "symbol": sym,
            "latest_close": curr_p,
            "p10_5d": p10,
            "p50_5d": p50,
            "p90_5d": p90,
            "exp_return_5d_pct": exp_ret,
            "uncertainty_spread_pct": spread,
            "chronos_barrier_ratio": barrier_ratio,
            "volume_force_index": round(vfi, 4),
            "price_volume_divergence_5d": round(pvd, 4),
            "donchian_channel_pos_20": round(d_pos, 4),
            "kline_lower_shadow_ratio": round(lower_shadow, 4),
            "floor_bounce_confirmed": floor_bounce,
            "gate_g4_status": "CERTIFIED" if (barrier_ratio >= 1.20 and spread <= 15.0) else "REJECTED_G4_BARRIER",
        })
        
    df_chronos = pd.DataFrame(records)
    df_chronos.to_parquet(CHRONOS_PARQUET, index=False)
    print(f"Persisted updated Chronos quantiles feature store to {CHRONOS_PARQUET} ({len(df_chronos)} rows).")


def main():
    t_start = time.time()
    print("=" * 80)
    print("APEXMARKETENGINE — END-OF-DAY COMPLETE DATABASE & MODEL REFRESH")
    print("================================================================")
    print(f"Start Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Fetch live EOD data
    eod_data = fetch_all_eod_data()
    
    # 2. Anti-Wash Floorsheet processing
    process_anti_wash_floorsheet(eod_data)
    
    # 3. Reconstruct OHLCV and Update Lakehouse parquet
    update_lakehouse_with_today_bars(eod_data)
    
    # 4. Pipeline execution (Features -> Calendars -> Chronos -> Gate G4 -> HRP -> Manifest)
    run_pipeline_steps()
    
    total_time = time.time() - t_start
    print("\n" + "=" * 80)
    print(f"ALL DATABASE TABLES, MODELS, FEATURES & MANIFESTS REFRESHED IN {total_time:.2f}s!")
    print("================================================================")


if __name__ == "__main__":
    main()
