"""
apex_engine/config.py

Global Configuration Settings for ApexMarketEngine Runtime.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Network & Host Binding
APEX_HOST = os.environ.get("APEX_HOST", "127.0.0.1")
APEX_PORT = int(os.environ.get("APEX_PORT", 8000))
APEX_BASE_URL = f"http://{APEX_HOST}:{APEX_PORT}"
APEX_WS_PULSE = f"{APEX_BASE_URL}/ws/pulse"

# Storage Directories
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
FEATURE_DIR = BASE_DIR / "03_feature_store"
STATIC_DIR = BASE_DIR / "static_data"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
FEATURE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# File Paths
DUCKDB_PATH = PROCESSED_DIR / "market_analytics.duckdb"
MASTER_PARQUET = PROCESSED_DIR / "market_master_union.parquet"
MERKLE_CHAIN = DATA_DIR / "merkle_provenance.chain"
OUTPUT_JSON_PATH = BASE_DIR / "NEPSE_MASTER_INTEGRATED_OUTPUT.json"
