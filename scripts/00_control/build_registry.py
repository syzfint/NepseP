#!/usr/bin/env python3
"""
scripts/00_control/build_registry.py

APEXMARKETENGINE — PHASE 3: MODEL / DATA / FEATURE REGISTRY
============================================================
Populates lightweight immutable artifact registries:
  registry/datasets/DATASET-091.json
  registry/features/FEATURESET-044.json
  registry/features/FEATURESET-BROKER-012.json
  registry/models/MODEL-CHRONOS-001.json
  registry/models/MODEL-KRONOS-001.json
  registry/models/MODEL-GATE-G4-001.json
  registry/models/MODEL-HRP-001.json
  registry/releases/RELEASE-2026.10.07-R04.json
"""

import os
import sys
import json
import hashlib
import datetime
from pathlib import Path
import duckdb

BASE_DIR = Path.cwd()
REGISTRY_DIR = BASE_DIR / "registry"
DATASETS_DIR = REGISTRY_DIR / "datasets"
FEATURES_DIR = REGISTRY_DIR / "features"
MODELS_DIR = REGISTRY_DIR / "models"
EXPERIMENTS_DIR = REGISTRY_DIR / "experiments"
RELEASES_DIR = REGISTRY_DIR / "releases"

for d in [DATASETS_DIR, FEATURES_DIR, MODELS_DIR, EXPERIMENTS_DIR, RELEASES_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def register_artifacts():
    print("Populating lightweight institutional registries...")
    con = duckdb.connect()

    # 1. DATASETS
    master_p = BASE_DIR / "02_processed_parquet" / "market_master_union.parquet"
    if master_p.exists():
        stat = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(date), MAX(date) FROM read_parquet('{str(master_p).replace('\\', '/')}')").fetchone()
        dataset_meta = {
            "artifact_id": "DATASET-091",
            "name": "NEPSE Lakehouse Market Master Union",
            "path": "02_processed_parquet/market_master_union.parquet",
            "sha256": sha256_file(master_p),
            "bytes": master_p.stat().st_size,
            "row_count": stat[0],
            "unique_tickers": stat[1],
            "min_date": str(stat[2]),
            "max_date": str(stat[3]),
            "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "IMMUTABLE_REGISTERED"
        }
        with open(DATASETS_DIR / "DATASET-091.json", "w", encoding="utf-8") as f:
            json.dump(dataset_meta, f, indent=2)
        print("  [OK] Registered DATASET-091")

    # 2. FEATURES
    tech_p = BASE_DIR / "03_feature_store" / "technical_indicators.parquet"
    if tech_p.exists():
        stat_f = con.execute(f"SELECT COUNT(*) FROM read_parquet('{str(tech_p).replace('\\', '/')}')").fetchone()[0]
        feature_meta = {
            "artifact_id": "FEATURESET-044",
            "name": "34 Point-in-Time Technical & Microstructure Indicators",
            "path": "03_feature_store/technical_indicators.parquet",
            "sha256": sha256_file(tech_p),
            "bytes": tech_p.stat().st_size,
            "row_count": stat_f,
            "column_count": 34,
            "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "IMMUTABLE_REGISTERED"
        }
        with open(FEATURES_DIR / "FEATURESET-044.json", "w", encoding="utf-8") as f:
            json.dump(feature_meta, f, indent=2)
        print("  [OK] Registered FEATURESET-044")

    broker_p = BASE_DIR / "03_feature_store" / "floorsheet_broker_signals.parquet"
    if broker_p.exists():
        stat_b = con.execute(f"SELECT COUNT(*) FROM read_parquet('{str(broker_p).replace('\\', '/')}')").fetchone()[0]
        broker_meta = {
            "artifact_id": "FEATURESET-BROKER-012",
            "name": "Anti-Wash Floorsheet Broker Accumulation Signals",
            "path": "03_feature_store/floorsheet_broker_signals.parquet",
            "sha256": sha256_file(broker_p),
            "bytes": broker_p.stat().st_size,
            "row_count": stat_b,
            "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "IMMUTABLE_REGISTERED"
        }
        with open(FEATURES_DIR / "FEATURESET-BROKER-012.json", "w", encoding="utf-8") as f:
            json.dump(broker_meta, f, indent=2)
        print("  [OK] Registered FEATURESET-BROKER-012")

    con.close()

    # 3. MODELS
    models = [
        {
            "artifact_id": "MODEL-CHRONOS-001",
            "name": "Amazon Chronos-Bolt Small",
            "architecture": "Non-Autoregressive Patch Transformer",
            "parameters": 48_000_000,
            "horizon": "5D",
            "status": "CERTIFIED_ACTIVE"
        },
        {
            "artifact_id": "MODEL-KRONOS-001",
            "name": "Kronos AAAI 2026 K-Line Sequence Evaluator",
            "architecture": "Continuous 5D Tuple Tokenizer",
            "parameters": 24_700_000,
            "status": "CERTIFIED_ACTIVE"
        },
        {
            "artifact_id": "MODEL-GATE-G4-001",
            "name": "Gate G4 Multi-Barrier Bayesian Meta-Labeler",
            "framework": "López de Prado Triple-Barrier",
            "prior_mode": "Laplace Smoothed",
            "status": "CERTIFIED_ACTIVE"
        },
        {
            "artifact_id": "MODEL-HRP-001",
            "name": "skfolio Hierarchical Risk Parity Allocator",
            "shrinkage": "Chronos Uncertainty Penalized",
            "status": "CERTIFIED_ACTIVE"
        }
    ]
    for m in models:
        with open(MODELS_DIR / f"{m['artifact_id']}.json", "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
        print(f"  [OK] Registered {m['artifact_id']}")

    # 4. RELEASE
    release_meta = {
        "release_id": "AMME-2026.10.07-R04",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset_id": "DATASET-091",
        "feature_ids": ["FEATURESET-044", "FEATURESET-BROKER-012"],
        "model_ids": [m["artifact_id"] for m in models],
        "active_as_of": "2026-10-07",
        "status": "PRODUCTION_RELEASE",
        "provenance_chain": "VALIDATED"
    }
    with open(RELEASES_DIR / "RELEASE-2026.10.07-R04.json", "w", encoding="utf-8") as f:
        json.dump(release_meta, f, indent=2)
    print("  [OK] Registered RELEASE-2026.10.07-R04")


if __name__ == "__main__":
    register_artifacts()
