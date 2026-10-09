#!/usr/bin/env python3
"""
scripts/00_control/provenance.py

APEXMARKETENGINE — CRYPTOGRAPHIC PROVENANCE & LINEAGE ENGINE
============================================================
Computes deterministic SHA-256 hashes linking:
  - Code modules
  - Dataset parquets
  - Feature stores
  - Model configs
  - Runtime environment
  - Final prediction outputs
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path.cwd()


def sha256_file(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    if not filepath.exists():
        return "FILE_NOT_FOUND"
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_payload(payload: Any) -> str:
    """Computes deterministic SHA-256 hash of a dictionary or string."""
    if isinstance(payload, (dict, list)):
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    else:
        raw = str(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_provenance_chain(
    dataset_path: Path,
    feature_path: Path,
    config_dict: Dict[str, Any],
    environment_dict: Dict[str, Any],
    output_dict: Dict[str, Any]
) -> Dict[str, str]:
    """Generates a complete institutional cryptographic provenance chain."""
    dataset_h = sha256_file(dataset_path)
    feature_h = sha256_file(feature_path)
    config_h = sha256_payload(config_dict)
    env_h = sha256_payload(environment_dict)
    output_h = sha256_payload(output_dict)

    composite_raw = f"{dataset_h}|{feature_h}|{config_h}|{env_h}|{output_h}"
    master_provenance_h = hashlib.sha256(composite_raw.encode("utf-8")).hexdigest()

    return {
        "dataset_hash": dataset_h,
        "feature_hash": feature_h,
        "config_hash": config_h,
        "environment_hash": env_h,
        "output_hash": output_h,
        "composite_provenance_hash": master_provenance_h
    }
