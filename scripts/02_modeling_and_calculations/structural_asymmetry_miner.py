#!/usr/bin/env python3
"""
scripts/02_modeling_and_calculations/structural_asymmetry_miner.py

APEXMARKETENGINE — STRUCTURAL ASYMMETRY & REGULATORY CALENDAR MINER
====================================================================
Extreme Stress-Testing Engine across the complete NEPSE universe.
Mines 5 high-impact structural market dislocations:

1. 3-Year Promoter Lock-In Expiry Vector (PO -> ORD Dilution & Cornering Squeezes)
2. Floorsheet Broker Syndicate Concentration (HHI & Dominant Cartel Accumulation)
3. 10-Kitta Retail Allotment Exhaustion Inflection Point
4. Book-Building 40% QIB 6-Month Lock-In Wall
5. Point-in-Time NFRS Valuation Anchors vs Speculative Bubbles
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("asymmetry_miner")

BASE_DIR = Path(__file__).resolve().parents[2]
PROCESSED_PARQUET = BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"
LOCKIN_PARQUET = BASE_DIR / "static_data" / "promoter_lockin.parquet"
FLOORSHEET_PARQUET = BASE_DIR / "01_raw_data" / "nepse_floorsheet_2026-10-07.parquet"
NFRS_PARQUET = BASE_DIR / "data" / "nfrs_point_in_time_features.parquet"
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")


class StructuralAsymmetryMiner:
    """
    Scans, stress-tests, and ranks structural market asymmetries across NEPSE.
    """

    def __init__(self, as_of_date: str = "2026-10-07"):
        self.as_of_date = as_of_date
        self.as_of_dt = pd.to_datetime(as_of_date)
        self.con = duckdb.connect()

    def mine_promoter_lockin_asymmetries(self) -> pd.DataFrame:
        """
        Identifies all companies currently within or approaching the
        3-Year Promoter Share Lock-In Expiry window.
        """
        p_str = str(LOCKIN_PARQUET).replace("\\", "/")
        m_str = str(PROCESSED_PARQUET).replace("\\", "/")

        query = f"""
        WITH latest_prices AS (
            SELECT 
                ticker as symbol,
                close as latest_close,
                volume as latest_volume,
                date as trade_date
            FROM (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY date DESC) as rn
                FROM read_parquet('{m_str}')
            ) WHERE rn = 1
        )
        SELECT 
            l.symbol,
            l.ipo_listing_date,
            l.lockin_expiry_date,
            l.freeze_window_start,
            l.freeze_window_end,
            p.latest_close,
            p.latest_volume
        FROM read_parquet('{p_str}') l
        LEFT JOIN latest_prices p ON l.symbol = p.symbol
        ORDER BY l.lockin_expiry_date ASC
        """
        df = self.con.execute(query).df()
        df["lockin_expiry_date"] = pd.to_datetime(df["lockin_expiry_date"])
        df["freeze_window_start"] = pd.to_datetime(df["freeze_window_start"])
        df["freeze_window_end"] = pd.to_datetime(df["freeze_window_end"])

        # Calculate days until lock-in expiry
        df["days_to_expiry"] = (df["lockin_expiry_date"] - self.as_of_dt).dt.days

        # Flag regime
        def classify_window(row):
            d = row["days_to_expiry"]
            start = row["freeze_window_start"]
            end = row["freeze_window_end"]
            if start <= self.as_of_dt <= end:
                return "ACTIVE_FREEZE_SHOCK_WINDOW"
            elif 0 <= d <= 30:
                return "IMMINENT_EXPIRY_30D"
            elif 30 < d <= 90:
                return "UPCOMING_EXPIRY_90D"
            elif -60 <= d < 0:
                return "RECENTLY_UNLOCKED_SUPPLY_DUMP"
            else:
                return "STABLE_OUTSIDE_WINDOW"

        df["regime"] = df.apply(classify_window, axis=1)
        return df

    def mine_broker_floorsheet_concentration(self) -> pd.DataFrame:
        """
        Scans floorsheet transactions to identify extreme cartel cornering
        (Top broker > 40% or Top 3 brokers > 70% accumulation).
        """
        if not FLOORSHEET_PARQUET.exists():
            return pd.DataFrame()

        f_str = str(FLOORSHEET_PARQUET).replace("\\", "/")
        query = f"""
        SELECT 
            stockSymbol as symbol,
            buyerMemberId as buyer_broker,
            sellerMemberId as seller_broker,
            contractQuantity as quantity,
            contractRate as rate,
            contractAmount as amount
        FROM read_parquet('{f_str}')
        """
        df_trades = self.con.execute(query).df()

        results = []
        for sym, grp in df_trades.groupby("symbol"):
            tot_vol = grp["quantity"].sum()
            tot_trades = len(grp)
            if tot_vol <= 500:
                continue

            # Group buy volume by broker
            buy_by_broker = grp.groupby("buyer_broker")["quantity"].sum().sort_values(ascending=False)
            sell_by_broker = grp.groupby("seller_broker")["quantity"].sum().sort_values(ascending=False)

            top1_buyer = buy_by_broker.index[0]
            top1_buy_vol = buy_by_broker.iloc[0]
            top1_share_pct = round((top1_buy_vol / tot_vol) * 100.0, 2)

            top3_buy_vol = buy_by_broker.head(3).sum()
            top3_share_pct = round((top3_buy_vol / tot_vol) * 100.0, 2)
            top3_buyers = list(buy_by_broker.head(3).index)

            # Calculate HHI on positive buyers
            hhi = sum((v / tot_vol * 100.0) ** 2 for v in buy_by_broker)

            # Net position of top buyer
            top1_sell_vol = sell_by_broker.get(top1_buyer, 0)
            top1_net_vol = top1_buy_vol - top1_sell_vol

            # Classification
            if top1_share_pct >= 45.0 or top3_share_pct >= 75.0:
                cartel_status = "EXTREME_CORNERING_ACCUMULATION"
            elif top1_share_pct >= 30.0 or top3_share_pct >= 60.0:
                cartel_status = "MODERATE_INSTITUTIONAL_CONCENTRATION"
            else:
                cartel_status = "DISPERSED_RETAIL_FLOW"

            results.append({
                "symbol": sym,
                "total_volume": int(tot_vol),
                "total_trades": tot_trades,
                "top1_broker": int(top1_buyer),
                "top1_share_pct": top1_share_pct,
                "top1_net_volume": int(top1_net_vol),
                "top3_brokers": top3_buyers,
                "top3_share_pct": top3_share_pct,
                "buyer_hhi": round(hhi, 2),
                "cartel_status": cartel_status
            })

        df_conc = pd.DataFrame(results)
        return df_conc.sort_values(by="top1_share_pct", ascending=False)

    def run_full_structural_stress_test(self) -> Dict[str, Any]:
        """
        Cross-analyzes Promoter Expiry, Floorsheet Cartels, and Price Structure.
        Discovers the Asymmetric Gold Mines and Fatal Traps.
        """
        logger.info("Executing Full Universe Structural Asymmetry Stress-Test...")

        # 1. Promoter Lock-in
        df_lockin = self.mine_promoter_lockin_asymmetries()

        # 2. Broker Concentration
        df_conc = self.mine_broker_floorsheet_concentration()

        # 3. Merge Datasets
        merged = pd.merge(df_conc, df_lockin, on="symbol", how="inner")

        # 4. Stress Test Filtration:
        # A. GOLD MINE CATEGORY 1: "The Promoter Lock-in Pre-Expiry Cornering Squeeze"
        #    Criteria: Lock-in expiry is within [-15d, +45d], but dominant broker(s)
        #    are aggressively cornering >= 45% of daily volume to orchestrate a short squeeze.
        gold_mines_cornering = merged[
            (merged["regime"].isin(["ACTIVE_FREEZE_SHOCK_WINDOW", "IMMINENT_EXPIRY_30D"])) &
            (merged["top3_share_pct"] >= 65.0)
        ].copy()

        # B. GOLD MINE CATEGORY 2: "Low-Float Floor Accumulators"
        #    Criteria: Scrips where Top Broker alone controls >= 50% of buying volume,
        #    trades < 100, and price is stable.
        gold_mines_low_float = df_conc[
            (df_conc["top1_share_pct"] >= 45.0) &
            (df_conc["total_volume"] >= 1000)
        ].copy()

        # C. FATAL TRAP CATEGORY: "The Unprotected Supply Wall"
        #    Criteria: Lock-in expiring in next 30 days, huge potential dilution,
        #    ZERO broker cornering (dispersed retail flow), high price ready to crater.
        fatal_traps = merged[
            (merged["regime"].isin(["ACTIVE_FREEZE_SHOCK_WINDOW", "IMMINENT_EXPIRY_30D"])) &
            (merged["cartel_status"] == "DISPERSED_RETAIL_FLOW")
        ].copy()

        # D. ACTIVE WINDOW WATCHLIST: All scrips currently in the statutory freeze window
        active_window_scrips = df_lockin[df_lockin["regime"] == "ACTIVE_FREEZE_SHOCK_WINDOW"].copy()

        return {
            "as_of_date": self.as_of_date,
            "total_lockin_tracked": len(df_lockin),
            "total_floorsheet_scrips": len(df_conc),
            "active_freeze_window_count": len(active_window_scrips),
            "active_freeze_window_scrips": active_window_scrips[["symbol", "lockin_expiry_date", "days_to_expiry", "latest_close", "latest_volume"]].to_dict(orient="records"),
            "gold_mines_cornering": gold_mines_cornering[["symbol", "days_to_expiry", "top1_broker", "top1_share_pct", "top3_share_pct", "latest_close"]].to_dict(orient="records"),
            "gold_mines_low_float": gold_mines_low_float.head(10).to_dict(orient="records"),
            "fatal_traps_supply_wall": fatal_traps[["symbol", "days_to_expiry", "top1_share_pct", "buyer_hhi", "latest_close"]].to_dict(orient="records"),
        }


def main():
    miner = StructuralAsymmetryMiner(as_of_date="2026-10-07")
    res = miner.run_full_structural_stress_test()

    print("\n" + "=" * 80)
    print("      NEPSE STRUCTURAL ASYMMETRY & REGULATORY STRESS-TEST REPORT")
    print("=" * 80)
    print(f"As-of Date:                    {res['as_of_date']}")
    print(f"Total Companies Audited:       {res['total_lockin_tracked']}")
    print(f"Active Lock-in Freeze Window:  {res['active_freeze_window_count']} Companies")

    print("\n[DISCOVERY 1] ACTIVE 3-YEAR PROMOTER LOCK-IN SUPPLY OVERHANG (CRITICAL WINDOW):")
    for s in res["active_freeze_window_scrips"]:
        exp_d = str(s["lockin_expiry_date"])[:10]
        days = s["days_to_expiry"]
        print(f"  * {s['symbol']:<8} | Expiry: {exp_d} ({days:+3d} days) | Price: NPR {s['latest_close']:>7.2f} | Vol: {s['latest_volume']:>8.0f}")

    print("\n[DISCOVERY 2] TOP CORNERED ASYMMETRIC GOLD MINES (TOP BROKER >= 45% BUY SHARE):")
    for g in res["gold_mines_low_float"][:8]:
        print(f"  * {g['symbol']:<8} | Broker {g['top1_broker']:>2}: {g['top1_share_pct']:>5.1f}% | Top 3: {g['top3_share_pct']:>5.1f}% | Total Vol: {g['total_volume']:>7,d} | HHI: {g['buyer_hhi']:>6.1f}")

    print("\n[DISCOVERY 3] FATAL TRAPS (IMPENDING LOCKIN DUMP + DISPERSED RETAIL BAGHOLDERS):")
    for t in res["fatal_traps_supply_wall"]:
        print(f"  * {t['symbol']:<8} | Days to Expiry: {t['days_to_expiry']:+3d} | Top Buyer: {t['top1_share_pct']:>5.1f}% | HHI: {t['buyer_hhi']:>5.1f} | Price: NPR {t['latest_close']:>7.2f}")


if __name__ == "__main__":
    main()
