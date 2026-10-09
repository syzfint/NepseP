#!/usr/bin/env python3
"""
scripts/00_control/apex.py

APEXMARKETENGINE — PRODUCTION INSTITUTIONAL CLI TOOL
=====================================================
Usage:
  python -m scripts.00_control.apex run [--as_of YYYY-MM-DD] [--env production]
  python -m scripts.00_control.apex audit [RUN-ID|latest|baseline]
  python -m scripts.00_control.apex signals [--top 10]
  python -m scripts.00_control.apex stage [--cash 1000000] [--broker 58] [--dry-run]
  python -m scripts.00_control.apex train-clef [--epochs 3] [--lr 0.0002]
  python -m scripts.00_control.apex sync [--target auto|s3|minio|local] [--run-id ID]
  python -m scripts.00_control.apex release [--id ID]
"""

import sys
import json
import argparse
from pathlib import Path

BASE_DIR = Path.cwd()
SCRIPTS_DIR = BASE_DIR / "scripts"
CONTROL_DIR = SCRIPTS_DIR / "00_control"

for p in [str(BASE_DIR), str(SCRIPTS_DIR), str(CONTROL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from apex_engine import ApexEngine
from signal_service import SignalService
from audit import find_target_run, run_audit
from release_manager import ReleaseManager
from tms_order_staging import run_staging_pipeline
from clef_panic_cycle_trainer import run_clef_panic_training_pipeline
from s3_storage_sync import run_cloud_sync_cli


def cli():
    parser = argparse.ArgumentParser(description="ApexMarketEngine Institutional Control Plane CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. run command
    run_parser = subparsers.add_parser("run", help="Execute an institutional prediction run")
    run_parser.add_argument("--as_of", default="2026-10-07", help="As-of date (YYYY-MM-DD)")
    run_parser.add_argument("--env", default="production", help="Environment (production, staging, dev)")
    run_parser.add_argument("--universe", default="NEPSE", help="Market universe")

    # 2. audit command
    audit_parser = subparsers.add_parser("audit", help="Audit and verify a run against frozen baseline")
    audit_parser.add_argument("run_id", nargs="?", default="latest", help="Run ID, 'latest', or 'baseline'")

    # 3. signals command
    sig_parser = subparsers.add_parser("signals", help="Fetch institutional certified signals")
    sig_parser.add_argument("--as_of", default="2026-10-07", help="As-of date")
    sig_parser.add_argument("--top", type=int, default=10, help="Number of top signals to return")

    # 4. stage command (TMS Order-Staging)
    stage_parser = subparsers.add_parser("stage", help="Generate and stage sliced orders in TMS")
    stage_parser.add_argument("--cash", type=float, default=2_000_000.0, help="Available cash in NPR")
    stage_parser.add_argument("--broker", default="58", help="Broker ID (e.g. 58, 49)")
    stage_parser.add_argument("--client", default="CLI_APEX_5801", help="Client Demat / trading code")
    stage_parser.add_argument("--dry-run", action="store_true", default=True, help="Simulate staging")

    # 5. train-clef command (CLEF Panic Cycle fine-tuning)
    clef_parser = subparsers.add_parser("train-clef", help="Fine-tune CLEF model on NEPSE panic cycles")

    # 6. sync command (AWS S3 & MinIO cloud mirror)
    sync_parser = subparsers.add_parser("sync", help="Sync manifests & models to AWS S3 / MinIO")
    sync_parser.add_argument("--target", default="auto", choices=["auto", "s3", "minio", "local"], help="Sync target")
    sync_parser.add_argument("--run-id", default=None, help="Specific run ID to sync")

    # 7. release command
    rel_parser = subparsers.add_parser("release", help="Inspect release management status")
    rel_parser.add_argument("--id", default=None, help="Release ID")

    args = parser.parse_args()

    if args.command == "run":
        engine = ApexEngine(environment=args.env)
        res = engine.predict(as_of=args.as_of, universe=args.universe)
        print(f"\n[CLI SUCCESS] Generated Run: {res['run_id']} | Status: {res['overall_gate_status']}")

    elif args.command == "audit":
        target = find_target_run(args.run_id)
        run_audit(target)

    elif args.command == "signals":
        service = SignalService()
        sigs = service.get_signals_dict(as_of=args.as_of, top_n=args.top)
        print(json.dumps(sigs, indent=2))

    elif args.command == "stage":
        res = run_staging_pipeline(cash_npr=args.cash, broker_id=args.broker, client_code=args.client, dry_run=args.dry_run)
        print("\n" + "=" * 70)
        print("      TMS ORDER-STAGING CONNECTOR EXECUTION COMPLETE")
        print("=" * 70)
        print(f"Blotter ID:            {res['blotter']['blotter_id']}")
        print(f"Staged Orders Count:   {res['blotter']['total_staged_orders']}")
        print(f"Total Buy Value (NPR): Rs. {res['blotter']['total_buy_value_npr']:,.2f}")
        print(f"Remaining Cash (NPR):  Rs. {res['blotter']['remaining_cash_npr']:,.2f}")
        print(f"Compliance Passed:     {res['blotter']['compliance_passed']}")
        print("=" * 70)

    elif args.command == "train-clef":
        res = run_clef_panic_training_pipeline()
        print("\n" + "=" * 70)
        print("    CLEF NEPSE PANIC CYCLE FINE-TUNING COMPLETE & CERTIFIED")
        print("=" * 70)
        print(f"Model ID:              {res['model_id']}")
        print(f"Specialization:        {res['specialization']}")
        print(f"Final Validation Loss: {res['final_val_loss']:.4f}")
        print(f"Weights SHA-256:       {res['weights_sha256'][:16]}...")
        print("=" * 70)

    elif args.command == "sync":
        rep = run_cloud_sync_cli(target=args.target, run_id=args.run_id)
        print("\n" + "=" * 70)
        print("      REMOTE ARTIFACT & CHECKPOINT CLOUD SYNC COMPLETE")
        print("=" * 70)
        print(f"Backend Target:        {rep['backend'].upper()}")
        print(f"Bucket Name:           {rep['bucket_name']}")
        print(f"Total Files Synced:    {rep['total_files_synced']}")
        print(f"Total Transferred:     {rep['total_size_mb']} MB")
        print(f"Execution Latency:     {rep['execution_time_seconds']}s")
        print("=" * 70)

    elif args.command == "release":
        mgr = ReleaseManager(release_id=args.id)
        print(json.dumps(mgr.get_release_metadata(), indent=2))


if __name__ == "__main__":
    cli()
