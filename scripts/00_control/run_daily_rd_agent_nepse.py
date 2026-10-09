#!/usr/bin/env python3
"""
scripts/00_control/run_daily_rd_agent_nepse.py

APEXMARKETENGINE — DAILY RD-AGENT & QLIB STRATEGY RUNNER (POST-MARKET EOD)
==========================================================================
Executes the autonomous factor mining, adaptive forecaster, HRP risk allocation,
and TMS order staging pipeline post-market close (3:30 PM NPT).

Synchronizes artifacts across active worktree and mirror directory:
  - RD_AGENT_NEPSE_STRATEGY_REPORT.md
  - static_data/alphanepse_zoo.json
  - static_data/rd_memory_graph.json
  - static_data/live_staged_orders.json
"""

import os
import sys
import shutil
import logging
from pathlib import Path
import importlib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [DailyRDAgent] %(message)s")
logger = logging.getLogger("DailyRDAgent")

BASE_DIR = Path(__file__).resolve().parents[2]
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")

# Add paths to sys.path
for p in [str(BASE_DIR), str(BASE_DIR / "scripts"), str(BASE_DIR / "scripts" / "02_modeling_and_calculations")]:
    if p not in sys.path:
        sys.path.insert(0, p)


def sync_file_to_mirror(rel_path: str):
    """Synchronizes file to secondary workspace mirror."""
    src = BASE_DIR / rel_path
    if not src.exists():
        return
    if ALT_DIR.exists():
        dest = ALT_DIR / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dest)
            logger.info(f"Mirrored {rel_path} -> {dest}")
        except Exception as e:
            logger.warning(f"Failed to mirror {rel_path}: {e}")


def main():
    logger.info("=" * 80)
    logger.info("STARTING DAILY RD-AGENT & QLIB STRATEGY RUN (NEPSE POST-MARKET)")
    logger.info("=" * 80)

    pipeline_mod = importlib.import_module("scripts.02_modeling_and_calculations.run_rd_agent_nepse_pipeline")
    results = pipeline_mod.run_pipeline()

    logger.info("=" * 80)
    logger.info("SYNCHRONIZING OUTPUT ARTIFACTS TO MIRROR DIRECTORY...")
    logger.info("=" * 80)

    sync_file_to_mirror("RD_AGENT_NEPSE_STRATEGY_REPORT.md")
    sync_file_to_mirror("static_data/alphanepse_zoo.json")
    sync_file_to_mirror("static_data/rd_memory_graph.json")
    sync_file_to_mirror("static_data/live_staged_orders.json")

    blotter = results.get("execution_blotter", {})
    logger.info(f"Execution Completed Successfully.")
    logger.info(f"Total Staged Orders: {blotter.get('total_staged_orders', 0)}")
    logger.info(f"Integrity Hash: {blotter.get('integrity_hash', 'N/A')}")
    logger.info(f"Compliance Passed: {blotter.get('compliance_passed', False)}")


if __name__ == "__main__":
    main()
