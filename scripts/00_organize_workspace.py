#!/usr/bin/env python3
"""
ApexMarketEngine Workspace Organizer & Restructuring Engine
============================================================
Consolidates and maintains institutional directory layout across:
  - Active Worktree: Path.cwd()
  - Mirror Repository: C:/Users/achar/Downloads/neps

Organizes:
  - reports/predictions/ -> Output manifests & daily forecasts
  - reports/backtests/   -> Multi-year backtest audits & equity curves
  - reports/charts/      -> All generated high-res visual PNG charts
  - reports/audits/      -> Gate reconciliation audits & IC matrices
  - reports/certification/ -> Sovereign G9/G10 certification reports
  - scratch/             -> Ad-hoc test scripts and scratch analysis
  - 01_raw/              -> Raw ticker CSVs and historical scraper drops
"""

import os
import shutil
from pathlib import Path

BASE_DIR = Path.cwd()
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")

DIRECTORIES = [
    "01_raw",
    "01_raw_data",
    "02_processed_parquet",
    "03_feature_store",
    "reports/predictions",
    "reports/backtests",
    "reports/charts",
    "reports/audits",
    "reports/certification",
    "reports/final_oos",
    "reports/gates",
    "reports/pbo_dsr",
    "scripts/01_etl_and_ingestion",
    "scripts/02_modeling_and_calculations",
    "scripts/03_data_access_and_storage",
    "scripts/04_scrapers_and_harness",
    "scratch",
    "static_data",
    "tests",
    "docs",
]

PREDICTION_FILES = [
    "NEPSE_MASTER_INTEGRATED_OUTPUT.json",
    "NEPSE_OCT7_PREDICTION.json",
    "NEPSE_OCT5_PREDICTION.json",
]

BACKTEST_FILES = [
    "NEPSE_CHRONOS_GATE_G4_BACKTEST_REPORT.json",
    "NEPSE_INSTITUTIONAL_BACKTEST_REPORT.json",
    "SOVEREIGN_NEPSE_BACKTEST_AUDIT.json",
    "SOVEREIGN_NEPSE_EQUITY_CURVE.csv",
    "FINAL_CONFIG_HASH.json",
    "FINAL_MODEL_HASH.json",
]

CHART_FILES = [
    "nepse_chronos_vs_lightgbm_drawdown_chart.png",
    "nepse_institutional_backtest_chart.png",
    "nepse_oct7_prediction_chart.png",
    "nepse_oct5_prediction_chart.png",
    "nepse_oct5_nepali_layman_chart.png",
]

RAW_ITEMS = [
    "companies_with_details.csv",
    "NEPSE Data.csv",
    "NEPSE INDEX APR 2004 TO APR 2024.xlsx",
    "nepsealpha_export_price_NEPSE_2021-10-14_2026-10-03_adjusted.xlsx",
    "nepse_index_history.csv",
    "nepse-data-main",
    "nepse-historical-market-data-csv-master",
    "nepse-historical-scraper-repo",
]

SCRATCH_FILES = [
    "scratch_test_live.py",
    "STH STH.md",
    "scratch_inventory.json",
]

STRAY_FILES = [
    "=",
]


def ensure_directories(root: Path):
    for rel_d in DIRECTORIES:
        d = root / rel_d
        d.mkdir(parents=True, exist_ok=True)


def organize_root(root: Path):
    if not root.exists():
        return

    print(f"\n[ORGANIZING] Root: {root}")
    ensure_directories(root)

    # Clean stray files
    for stray in STRAY_FILES:
        p = root / stray
        if p.exists():
            try:
                p.unlink()
                print(f"  Removed stray: {stray}")
            except Exception as e:
                print(f"  Warning removing {stray}: {e}")

    # Move scratch files
    for item in SCRATCH_FILES:
        src = root / item
        dst = root / "scratch" / item
        if src.exists() and src != dst:
            shutil.move(str(src), str(dst))
            print(f"  Moved -> scratch/{item}")

    # Move raw items
    for item in RAW_ITEMS:
        src = root / item
        dst = root / "01_raw" / item
        if src.exists() and src != dst:
            if not dst.exists():
                shutil.move(str(src), str(dst))
                print(f"  Moved -> 01_raw/{item}")

    # Copy / Mirror prediction files to reports/predictions
    for item in PREDICTION_FILES:
        src = root / item
        if src.exists():
            dst = root / "reports" / "predictions" / item
            shutil.copy2(str(src), str(dst))
            print(f"  Mirrored -> reports/predictions/{item}")

    # Copy / Mirror backtest files to reports/backtests
    for item in BACKTEST_FILES:
        src = root / item
        if src.exists():
            dst = root / "reports" / "backtests" / item
            shutil.copy2(str(src), str(dst))
            print(f"  Mirrored -> reports/backtests/{item}")

    # Copy / Mirror charts to reports/charts
    for item in CHART_FILES:
        src = root / item
        if src.exists():
            dst = root / "reports" / "charts" / item
            shutil.copy2(str(src), str(dst))
            print(f"  Mirrored -> reports/charts/{item}")


def sync_folders(src_root: Path, dst_root: Path, subfolder: str):
    src = src_root / subfolder
    dst = dst_root / subfolder
    if src.exists() and dst_root.exists():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(src)
                target = dst / rel_path
                if not target.exists() or target.stat().st_mtime < item.stat().st_mtime:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(str(item), str(target))
                    except Exception:
                        pass


def main():
    print("=" * 80)
    print("APEXMARKETENGINE WORKSPACE RESTRUCTURING & RE-ALIGNMENT")
    print("=" * 80)

    for r in [BASE_DIR, ALT_DIR]:
        if r.exists():
            organize_root(r)

    # Bidirectional synchronization of critical components
    if BASE_DIR.exists() and ALT_DIR.exists():
        print("\n[SYNCHRONIZING] Bidirectional sync between Worktree and Downloads/neps...")
        for sub in [
            "reports",
            "02_processed_parquet",
            "03_feature_store",
            "scripts",
        ]:
            sync_folders(BASE_DIR, ALT_DIR, sub)
            sync_folders(ALT_DIR, BASE_DIR, sub)

        # Sync key root manifests
        for f in [
            "NEPSE_MASTER_INTEGRATED_OUTPUT.json",
            "NEPSE_CHRONOS_GATE_G4_BACKTEST_REPORT.json",
            "nepse_chronos_vs_lightgbm_drawdown_chart.png",
        ]:
            s = BASE_DIR / f
            d = ALT_DIR / f
            if s.exists():
                shutil.copy2(str(s), str(d))

    print("\n" + "=" * 80)
    print("WORKSPACE RESTRUCTURING & SYNCHRONIZATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
