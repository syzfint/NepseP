#!/usr/bin/env python3
"""
scripts/00_control/run_manager.py

APEXMARKETENGINE — PRODUCTION RUN MANAGER (PHASE 1 & 2)
========================================================
Orchestrates immutable execution runs:
  1. Generates unique run ID: RUN-YYYYMMDD-HHMMSS
  2. Creates isolated run directory: runs/RUN-YYYYMMDD-HHMMSS/
  3. Gathers SHA-256 provenance chain across Code, Data, Config, and Environment.
  4. Seals immutable RunManifest (manifest.json).
  5. Records operational telemetry (telemetry.json).
"""

import os
import sys
import json
import time
import subprocess
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path.cwd()
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

SCRIPTS_DIR = BASE_DIR / "scripts"
CONTROL_DIR = SCRIPTS_DIR / "00_control"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from manifest import RunManifest
from provenance import compute_provenance_chain, sha256_file, sha256_payload
from governance import GovernanceEngine
from observability import ObservabilityEngine


class RunManager:
    def __init__(self, release_id: str = "AMME-2026.10.07-R04", universe: str = "NEPSE"):
        self.release_id = release_id
        self.universe = universe
        self.start_dt = datetime.datetime.now(datetime.timezone.utc)
        self.run_id = f"RUN-{self.start_dt.strftime('%Y%m%d-%H%M%S')}"
        self.run_dir = RUNS_DIR / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        self.governance = GovernanceEngine()
        self.observability = ObservabilityEngine(self.run_dir)

    def get_git_commit(self) -> str:
        try:
            p = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
            return p.stdout.strip() if p.returncode == 0 else "UNKNOWN_COMMIT"
        except Exception:
            return "UNKNOWN_COMMIT"

    def finalize_run(
        self,
        as_of: str,
        config_dict: Dict[str, Any],
        pipeline_output: Dict[str, Any],
        dataset_path: Path,
        feature_path: Path
    ) -> RunManifest:
        """Finalizes run execution, seals manifest and saves telemetry."""
        duration = time.time() - self.t0
        end_dt = datetime.datetime.now(datetime.timezone.utc)

        # 1. Environment metadata
        env_dict = {
            "python": sys.version,
            "platform": sys.platform,
            "git_commit": self.get_git_commit()
        }

        # 2. Cryptographic Provenance Chain
        chain = compute_provenance_chain(
            dataset_path=dataset_path,
            feature_path=feature_path,
            config_dict=config_dict,
            environment_dict=env_dict,
            output_dict=pipeline_output
        )

        # 3. Governance Evaluation
        model_gates = self.governance.verify_model_release()
        runtime_gates = self.governance.evaluate_runtime_safety(
            gate_g4_certified_count=pipeline_output.get("certified_candidates_count", 0),
            market_breadth_pct=pipeline_output.get("market_breadth_pct", 0.0),
            pydantic_valid=True,
            chart_base64_present=bool(pipeline_output.get("chart_base64_png")),
            sha256_hash_sealed=bool(pipeline_output.get("provenance_hash_h_master"))
        )

        gate_status = {
            "model_release_gates": model_gates,
            "runtime_safety_gates": runtime_gates,
            "overall_status": "CERTIFIED_PASS" if (model_gates["status"] == "CERTIFIED" and runtime_gates["all_passed"]) else "FAILED"
        }

        # 4. Construct Immutable Manifest
        manifest = RunManifest(
            run_id=self.run_id,
            release_id=self.release_id,
            git_commit=self.get_git_commit(),
            dataset_hash=chain["dataset_hash"],
            feature_hash=chain["feature_hash"],
            model_versions={
                "chronos": "amazon/chronos-bolt-small",
                "kronos": "AAAI-2026-v1.0",
                "gate_g4": "Bayesian-Laplace-v1.0",
                "hrp": "skfolio-HRP-v1.0"
            },
            config_hash=chain["config_hash"],
            environment_hash=chain["environment_hash"],
            start_time=self.start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            universe=self.universe,
            as_of=as_of,
            gate_status=gate_status,
            output_hash=chain["output_hash"]
        )

        # Save manifest and output
        manifest.save_json(self.run_dir)
        manifest.save_yaml(self.run_dir)

        output_file = self.run_dir / "output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(pipeline_output, f, indent=2)

        # 5. Record Observability Telemetry
        self.observability.record_telemetry(
            as_of=as_of,
            lakehouse_path=dataset_path,
            pipeline_output=pipeline_output,
            duration_seconds=duration
        )

        print(f"\n[RUN FINALIZED] {self.run_id} sealed successfully.")
        print(f"  Directory: {self.run_dir}")
        print(f"  Manifest : {self.run_dir / 'manifest.json'}")
        print(f"  Status   : {gate_status['overall_status']}")

        return manifest
