#!/usr/bin/env python3
"""
scripts/00_control/apex_engine.py

APEXMARKETENGINE — PRODUCTION INSTITUTIONAL CONTROL WRAPPER (PHASE 1)
=====================================================================
The unified institutional entrypoint:
  engine = ApexEngine()
  result = engine.predict(as_of="2026-10-07", universe="NEPSE")

CORE PRINCIPLE:
  ZERO MATHEMATICAL REWRITE. ZERO STRATEGY CHANGE. ZERO DATA REPROCESSING.
  Internally invokes the verified production pipeline (scripts/00_master_integrated_pipeline.py),
  seals an immutable RunManifest (RUN-YYYYMMDD-HHMMSS), and enforces regression equivalence.
"""

import os
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path.cwd()
SCRIPTS_DIR = BASE_DIR / "scripts"
CONTROL_DIR = SCRIPTS_DIR / "00_control"

for p in [str(BASE_DIR), str(SCRIPTS_DIR), str(CONTROL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from run_manager import RunManager
from release_manager import ReleaseManager
from manifest import RunManifest


class ApexEngine:
    def __init__(self, config_path: Optional[Path] = None, environment: str = "production"):
        self.environment = environment
        self.config_path = config_path or (BASE_DIR / "configs" / f"{environment}.yaml")
        if not self.config_path.exists():
            self.config_path = BASE_DIR / "configs" / "production.yaml"

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.release_manager = ReleaseManager(
            release_id=self.config.get("system", {}).get("release_id", "AMME-2026.10.07-R04")
        )

    def predict(
        self,
        as_of: str = "2026-10-07",
        universe: str = "NEPSE"
    ) -> Dict[str, Any]:
        """
        Executes institutional prediction pipeline under full control-plane governance.
        Calls verified mathematical pipeline verbatim.
        """
        print("=" * 80)
        print(f"APEXMARKETENGINE — CONTROL PLANE EXECUTION [as_of: {as_of} | universe: {universe}]")
        print(f"Release: {self.release_manager.release_id} | Config: {self.config_path.name}")
        print("=" * 80)

        # 1. Initialize Run Manager
        run_mgr = RunManager(
            release_id=self.release_manager.release_id,
            universe=universe
        )

        # 2. Execute existing verified production pipeline
        import importlib
        master_mod = importlib.import_module("scripts.00_master_integrated_pipeline")
        exec_pipeline = master_mod.run_master_pipeline

        # Run pipeline verbatim (ZERO mathematical changes)
        validated_manifest = exec_pipeline()
        pipeline_output = validated_manifest.model_dump()

        # 3. Finalize Run Manifest & Telemetry
        dataset_path = BASE_DIR / self.config.get("data", {}).get("master_parquet", "02_processed_parquet/market_master_union.parquet")
        feature_path = BASE_DIR / self.config.get("data", {}).get("feature_parquet", "03_feature_store/technical_indicators.parquet")

        manifest = run_mgr.finalize_run(
            as_of=as_of,
            config_dict=self.config,
            pipeline_output=pipeline_output,
            dataset_path=dataset_path,
            feature_path=feature_path
        )

        # Return standardized institutional prediction payload
        return {
            "run_id": manifest.run_id,
            "release_id": manifest.release_id,
            "as_of": manifest.as_of,
            "universe": manifest.universe,
            "overall_gate_status": manifest.gate_status.get("overall_status"),
            "live_nepse_index": pipeline_output.get("live_nepse_index"),
            "live_nepse_change": pipeline_output.get("live_nepse_change"),
            "market_breadth_pct": pipeline_output.get("market_breadth_pct"),
            "cash_allocation_pct": pipeline_output.get("cash_allocation_pct"),
            "certified_candidates_count": pipeline_output.get("certified_candidates_count"),
            "provenance_hash_h_master": pipeline_output.get("provenance_hash_h_master"),
            "top_candidates": pipeline_output.get("top_candidates", []),
            "manifest_path": str(run_mgr.run_dir / "manifest.json")
        }


def main():
    engine = ApexEngine()
    result = engine.predict(as_of="2026-10-07", universe="NEPSE")
    print(f"\nExecution successful. Run ID: {result['run_id']}")


if __name__ == "__main__":
    main()
