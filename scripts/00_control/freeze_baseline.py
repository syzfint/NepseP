#!/usr/bin/env python3
"""
scripts/00_control/freeze_baseline.py

APEXMARKETENGINE — PHASE 0: BASELINE FREEZE
============================================
Freezes the verified production baseline state before any control-plane scaffolding:
1. code_manifest.json (SHA-256 hashes of all quant engine modules)
2. dependency_lock.txt (Complete pip environment lock)
3. dataset_manifest.json (Lakehouse parquets, row counts, dates, hashes)
4. model_manifest.json (Chronos, Kronos, Gate G4, HRP specifications)
5. environment.json (Python, OS, DuckDB, Torch, Polars, Git metadata)
6. benchmark_results.json (Execution metrics, returns, Sharpe, breadth, cash buffer)
7. baseline_output.json (Exact replica of NEPSE_MASTER_INTEGRATED_OUTPUT.json)
8. SHA256SUMS (Cryptographic manifest of the entire BASELINE directory)
"""

import os
import sys
import json
import hashlib
import platform
import subprocess
import datetime
from pathlib import Path
from typing import Dict, Any

import duckdb
import torch
import pandas as pd
import polars as pl

BASE_DIR = Path.cwd()
BASELINE_DIR = BASE_DIR / "BASELINE"
BASELINE_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_git_commit() -> str:
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else "UNKNOWN_COMMIT"
    except Exception:
        return "UNKNOWN_COMMIT"


def freeze_environment():
    print("[1/8] Freezing environment.json...")
    env_info = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "os_name": os.name,
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": {
            "duckdb": duckdb.__version__,
            "torch": torch.__version__,
            "pandas": pd.__version__,
            "polars": pl.__version__,
            "numpy": getattr(pd.np, "__version__", "numpy_installed") if hasattr(pd, "np") else "installed"
        }
    }
    with open(BASELINE_DIR / "environment.json", "w", encoding="utf-8") as f:
        json.dump(env_info, f, indent=2)


def freeze_dependencies():
    print("[2/8] Freezing dependency_lock.txt...")
    p = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True)
    with open(BASELINE_DIR / "dependency_lock.txt", "w", encoding="utf-8") as f:
        f.write(p.stdout)


def freeze_code_manifest():
    print("[3/8] Freezing code_manifest.json...")
    key_files = [
        "scripts/00_master_integrated_pipeline.py",
        "scripts/00_organize_workspace.py",
        "scripts/01_build_master_union.py",
        "scripts/01_etl_and_ingestion/update_today_eod_lakehouse.py",
        "scripts/01_etl_and_ingestion/duckdb_lakehouse_loader.py",
        "scripts/01_etl_and_ingestion/nepse_websocket_floorsheet.py",
        "scripts/01_etl_and_ingestion/08_compute_floorsheet_broker_features.py",
        "scripts/01_etl_and_ingestion/build_promoter_lockin_calendar.py",
        "scripts/02_feature_engineering.py",
        "scripts/02_modeling_and_calculations/chronos_bolt_engine.py",
        "scripts/02_modeling_and_calculations/kronos_kline_evaluator.py",
        "scripts/02_modeling_and_calculations/gate_g4_metalabeler.py",
        "scripts/02_modeling_and_calculations/hrp_portfolio_allocator.py",
        "scripts/34_full_market_chronos_engine.py",
    ]
    manifest = {}
    for rel in key_files:
        f_path = BASE_DIR / rel
        if f_path.exists():
            manifest[rel] = {
                "sha256": sha256_file(f_path),
                "bytes": f_path.stat().st_size,
                "modified": datetime.datetime.fromtimestamp(f_path.stat().st_mtime).isoformat()
            }
        else:
            manifest[rel] = {"status": "NOT_FOUND"}
    with open(BASELINE_DIR / "code_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def freeze_dataset_manifest():
    print("[4/8] Freezing dataset_manifest.json...")
    datasets = {
        "market_master_union": BASE_DIR / "02_processed_parquet" / "market_master_union.parquet",
        "technical_indicators": BASE_DIR / "03_feature_store" / "technical_indicators.parquet",
        "chronos_quantiles_5d": BASE_DIR / "03_feature_store" / "chronos_quantiles_5d.parquet",
        "floorsheet_broker_signals": BASE_DIR / "03_feature_store" / "floorsheet_broker_signals.parquet",
        "promoter_lockin": BASE_DIR / "static_data" / "promoter_lockin.parquet",
        "floorsheet_2026_10_07": BASE_DIR / "01_raw_data" / "nepse_floorsheet_2026-10-07.parquet",
    }
    con = duckdb.connect()
    d_manifest = {}
    for name, p in datasets.items():
        if p.exists():
            p_str = str(p).replace("\\", "/")
            stat = con.execute(f"SELECT COUNT(*) FROM read_parquet('{p_str}')").fetchone()[0]
            d_manifest[name] = {
                "file_path": str(p),
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "row_count": stat,
                "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat()
            }
        else:
            d_manifest[name] = {"status": "NOT_FOUND"}
    con.close()
    with open(BASELINE_DIR / "dataset_manifest.json", "w", encoding="utf-8") as f:
        json.dump(d_manifest, f, indent=2)


def freeze_model_manifest():
    print("[5/8] Freezing model_manifest.json...")
    models = {
        "chronos_bolt_small": {
            "model_id": "amazon/chronos-bolt-small",
            "parameters": 48_000_000,
            "architecture": "Non-Autoregressive Time-Series Patch Transformer",
            "prediction_length": 5,
            "quantiles": ["P10", "P50", "P90"],
            "uncertainty_metric": "(P90 - P10) / P50",
            "barrier_ratio_formula": "P(Price >= +2s) / P(Price <= -2s)"
        },
        "kronos_kline_tokenizer": {
            "model_family": "AAAI 2026 K-Line Sequence Foundation Model",
            "input_dimension": 5,
            "tuple_schema": "[Open, High, Low, Close, Volume]",
            "lookback_window": "5D to 20D",
            "detectors": ["bull_trap_gap_rejection", "confirmed_floor_bounce", "pv_volume_drain"]
        },
        "gate_g4_metalabeler": {
            "framework": "López de Prado Triple-Barrier Meta-Labeling",
            "certification_mode": "Bayesian Laplace Smoothed Prior",
            "prior_probability": 0.599,
            "threshold": 0.55,
            "filters": ["physical_t_plus_2_shield", "promoter_lockin_36m_freeze", "anti_wash_hhi_loop"]
        },
        "skfolio_hrp_allocator": {
            "algorithm": "Hierarchical Risk Parity (HRP)",
            "covariance_shrinkage": "Chronos Uncertainty Penalization (Var * max(1, Spread / 8.0))",
            "asset_bounds": [0.03, 0.18],
            "cash_buffer_rule": "25% cash buffer when market breadth < 40%"
        }
    }
    with open(BASELINE_DIR / "model_manifest.json", "w", encoding="utf-8") as f:
        json.dump(models, f, indent=2)


def freeze_benchmark_results():
    print("[6/8] Freezing benchmark_results.json & baseline_output.json...")
    master_output = BASE_DIR / "NEPSE_MASTER_INTEGRATED_OUTPUT.json"
    if not master_output.exists():
        raise FileNotFoundError(f"Missing master output at {master_output}")

    with open(master_output, "r", encoding="utf-8") as f:
        master_dict = json.load(f)

    # Copy baseline output verbatim
    with open(BASELINE_DIR / "baseline_output.json", "w", encoding="utf-8") as f:
        json.dump(master_dict, f, indent=2)

    bench = {
        "as_of_date": "2026-10-07",
        "live_nepse_index": master_dict.get("live_nepse_index"),
        "live_nepse_change": master_dict.get("live_nepse_change"),
        "market_breadth_pct": master_dict.get("market_breadth_pct"),
        "evaluated_tickers_count": master_dict.get("evaluated_tickers_count"),
        "certified_candidates_count": master_dict.get("certified_candidates_count"),
        "cash_allocation_pct": master_dict.get("cash_allocation_pct"),
        "active_regime": master_dict.get("active_regime"),
        "provenance_hash_h_master": master_dict.get("provenance_hash_h_master"),
        "top_5_allocations": [
            {
                "symbol": c["symbol"],
                "latest_close": c["latest_close"],
                "p50_5d": c["p50_5d"],
                "exp_return_5d_pct": c["exp_return_5d_pct"],
                "uncertainty_spread_pct": c["uncertainty_spread_pct"],
                "meta_label_probability": c.get("meta_label_probability"),
                "hrp_allocation_pct": c.get("hrp_allocation_pct"),
                "regime": c.get("kronos_regime")
            }
            for c in master_dict.get("top_candidates", [])[:5]
        ]
    }
    with open(BASELINE_DIR / "benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(bench, f, indent=2)


def generate_sha256sums():
    print("[7/8] Generating SHA256SUMS...")
    files = sorted([f for f in BASELINE_DIR.iterdir() if f.is_file() and f.name != "SHA256SUMS"])
    lines = []
    for f in files:
        h = sha256_file(f)
        lines.append(f"{h}  {f.name}")
    with open(BASELINE_DIR / "SHA256SUMS", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def verify_freeze():
    print("[8/8] Verifying baseline freeze completeness...")
    expected = [
        "code_manifest.json",
        "dependency_lock.txt",
        "dataset_manifest.json",
        "model_manifest.json",
        "environment.json",
        "benchmark_results.json",
        "baseline_output.json",
        "SHA256SUMS"
    ]
    for exp in expected:
        p = BASELINE_DIR / exp
        print(f"  [OK] {exp:<26} ({p.stat().st_size:,} bytes)")
    print("\n[SUCCESS] PHASE 0 BASELINE FREEZE IS COMPLETE AND CRYPTOGRAPHICALLY SEALED.")


def main():
    print("=" * 80)
    print("APEXMARKETENGINE — FREEZING PRODUCTION BASELINE (PHASE 0)")
    print("=" * 80)
    freeze_environment()
    freeze_dependencies()
    freeze_code_manifest()
    freeze_dataset_manifest()
    freeze_model_manifest()
    freeze_benchmark_results()
    generate_sha256sums()
    verify_freeze()


if __name__ == "__main__":
    main()
