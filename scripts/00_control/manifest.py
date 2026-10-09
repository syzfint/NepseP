#!/usr/bin/env python3
"""
scripts/00_control/manifest.py

APEXMARKETENGINE — IMMUTABLE RUN MANIFEST ENGINE (PHASE 2)
==========================================================
Generates cryptographically sealed, immutable run manifests:
  RUN-YYYYMMDD-HHMMSS
Answers with mathematical certainty: "Exactly what produced this prediction?"
"""

import os
import sys
import json
import yaml
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

BASE_DIR = Path.cwd()


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str = Field(description="Unique run execution identifier (RUN-YYYYMMDD-HHMMSS)")
    release_id: str = Field(description="Production release tag (e.g. AMME-2026.10.07-R04)")
    git_commit: str = Field(description="Exact git commit hash")
    dataset_hash: str = Field(description="SHA-256 hash of market_master_union.parquet")
    feature_hash: str = Field(description="SHA-256 hash of technical_indicators.parquet")
    model_versions: Dict[str, str] = Field(description="Versions of Chronos, Kronos, G4, and HRP")
    config_hash: str = Field(description="SHA-256 hash of execution configuration")
    environment_hash: str = Field(description="SHA-256 hash of OS, Python, and package environment")
    start_time: str = Field(description="UTC ISO start timestamp")
    end_time: str = Field(description="UTC ISO completion timestamp")
    universe: str = Field(default="NEPSE", description="Target market universe")
    as_of: str = Field(description="Market date evaluated (YYYY-MM-DD)")
    gate_status: Dict[str, Any] = Field(description="Model release gates & runtime safety gate evaluations")
    output_hash: str = Field(description="SHA-256 hash of prediction payload")

    def save_json(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "manifest.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
        return path

    def save_yaml(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "manifest.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, sort_keys=False)
        return path
