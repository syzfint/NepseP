#!/usr/bin/env python3
"""
scripts/01_etl_and_ingestion/eod_lakehouse_sync.py

APEXMARKETENGINE — PRODUCTION END-OF-DAY (EOD) LAKEHOUSE SYNCHRONIZATION ENGINE
================================================================================
Implements Tier 2 Post-Market Lakehouse Archival & Synchronization:
1. Connects to local DuckDB database (POSIX / NVMe storage).
2. Extracts daily market tick data and exports to Hive-partitioned Parquet (ZSTD codec).
   Partition layout: year=YYYY/month=MM/ticks_YYYY-MM-DD.parquet
3. Prunes archived records from local DuckDB and executes CHECKPOINT to reclaim space.
4. Uploads Parquet artifacts to Google Drive Cold Storage via resumable upload with
   exponential backoff + jitter handling for HTTP 429 / 403 quota ceilings.
5. Cleans up local staging files post-verification.
"""

import os
import sys
import time
import random
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("EODLakehouseSync")

# Configuration defaults with environment variable overrides
DEFAULT_DUCKDB_PATH = os.getenv("TRADING_DB_PATH", "nepse_lakehouse/live_execution.duckdb")
DEFAULT_STAGING_DIR = os.getenv("EXPORT_STAGING_DIR", "data/staging/parquet")
DEFAULT_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "YOUR_TARGET_GOOGLE_DRIVE_FOLDER_ID")
DEFAULT_CREDENTIALS_FILE = os.getenv("GCP_CREDENTIALS_FILE", "configs/gcp_credentials.json")


def export_duckdb_to_parquet(
    db_path: str,
    staging_dir: str,
    target_date: Optional[str] = None,
    dry_run: bool = False
) -> Tuple[Path, str]:
    """
    Exports daily tick data from DuckDB to Hive-partitioned Parquet with ZSTD compression,
    then prunes the exported records and checkpoints DuckDB.
    """
    if not os.path.exists(db_path):
        logger.warning(f"Local database file not found at: {db_path}. Checking fallback...")
        fallback_path = "data/live_execution.duckdb"
        if os.path.exists(fallback_path):
            db_path = fallback_path
            logger.info(f"Using fallback DuckDB at: {db_path}")
        else:
            raise FileNotFoundError(f"DuckDB database does not exist at {db_path} or {fallback_path}")

    now = datetime.now()
    today_str = target_date or now.strftime("%Y-%m-%d")
    date_dt = datetime.strptime(today_str, "%Y-%m-%d")
    year_str = date_dt.strftime("%Y")
    month_str = date_dt.strftime("%m")

    target_partition_dir = Path(staging_dir) / f"year={year_str}" / f"month={month_str}"
    target_partition_dir.mkdir(parents=True, exist_ok=True)
    parquet_filename = f"ticks_{today_str}.parquet"
    full_parquet_path = target_partition_dir / parquet_filename

    logger.info(f"Connecting to local DuckDB at: {db_path}")
    try:
        import duckdb
    except ImportError:
        logger.error("duckdb package is required. Install via: pip install duckdb")
        raise
    con = duckdb.connect(database=db_path, read_only=False)

    try:
        # Check if table exists
        table_check = con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'market_ticks'"
        ).fetchone()[0]

        if table_check == 0:
            logger.warning("Table 'market_ticks' does not exist in database. Checking 'floorsheet'...")
            floorsheet_check = con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_name = 'floorsheet'"
            ).fetchone()[0]
            table_name = "floorsheet" if floorsheet_check > 0 else "market_ticks"
        else:
            table_name = "market_ticks"

        export_query = f"""
            COPY (
                SELECT * 
                FROM {table_name} 
                WHERE CAST(timestamp AS DATE) = '{today_str}'
            ) TO '{full_parquet_path.as_posix()}' (FORMAT PARQUET, CODEC 'ZSTD');
        """

        logger.info(f"Exporting '{table_name}' for date {today_str} to: {full_parquet_path}")
        if not dry_run:
            con.execute(export_query)
            logger.info("Parquet export completed successfully.")

            prune_query = f"DELETE FROM {table_name} WHERE CAST(timestamp AS DATE) <= '{today_str}';"
            logger.info(f"Pruning records on or before {today_str}...")
            con.execute(prune_query)
            con.execute("CHECKPOINT;")
            logger.info("Local DuckDB pruned and checkpointed.")
        else:
            logger.info("[DRY-RUN] Skipped DuckDB execution and prune.")
    finally:
        con.close()

    return full_parquet_path, parquet_filename


def upload_file_with_exponential_backoff(
    local_file_path: Path,
    remote_filename: str,
    drive_folder_id: str,
    credentials_file: str,
    max_retries: int = 8,
    dry_run: bool = False
) -> Optional[str]:
    """
    Safely uploads the Parquet file to Google Drive using resumable chunk upload
    with exponential backoff and randomized jitter to handle HTTP 429/403 rate limits.
    """
    if dry_run:
        logger.info(f"[DRY-RUN] Simulating upload of {remote_filename} to Google Drive folder {drive_folder_id}")
        return "mock_drive_file_id_dry_run"

    if not os.path.exists(credentials_file):
        logger.warning(
            f"Service account file '{credentials_file}' not found. "
            "Please configure GCP_CREDENTIALS_FILE or place credentials at configs/gcp_credentials.json. "
            "Skipping Google Drive upload stage."
        )
        return None

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.service_account import Credentials
    except ImportError:
        logger.error(
            "Missing Google Drive API dependencies. Run: pip install google-api-python-client google-auth"
        )
        return None

    scopes = ["https://www.googleapis.com/auth/drive.file"]
    creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
    drive_service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name": remote_filename,
        "parents": [drive_folder_id]
    }

    media = MediaFileUpload(
        str(local_file_path),
        mimetype="application/octet-stream",
        resumable=True
    )
    request = drive_service.files().create(body=file_metadata, media_body=media, fields="id")

    response = None
    retry = 0

    while response is None:
        try:
            logger.info(f"Uploading {remote_filename} to Google Drive (Attempt {retry + 1})...")
            status, response = request.next_chunk()
            if response:
                file_id = response.get("id")
                logger.info(f"Upload complete. Google Drive File ID: {file_id}")
                return file_id
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "403" in err_msg:
                retry += 1
                if retry > max_retries:
                    logger.error(f"Exceeded maximum retries ({max_retries}). Terminating upload.")
                    raise
                # T_wait = min(2^retry + jitter, T_max)
                jitter = random.uniform(0.1, 1.0)
                sleep_time = min((2 ** retry) + jitter, 64.0)
                logger.warning(
                    f"Rate limit encountered (HTTP 429/403). Retrying in {sleep_time:.2f}s..."
                )
                time.sleep(sleep_time)
            else:
                logger.error(f"Fatal error during Google Drive upload: {err_msg}")
                raise


def run_pipeline(
    db_path: str = DEFAULT_DUCKDB_PATH,
    staging_dir: str = DEFAULT_STAGING_DIR,
    drive_folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
    credentials_file: str = DEFAULT_CREDENTIALS_FILE,
    target_date: Optional[str] = None,
    dry_run: bool = False,
    keep_staging: bool = False
) -> None:
    """Executes the complete End-of-Day Lakehouse Synchronization pipeline."""
    logger.info("=" * 70)
    logger.info("STARTING END-OF-DAY LAKEHOUSE SYNCHRONIZATION PIPELINE")
    logger.info("=" * 70)

    try:
        parquet_path, filename = export_duckdb_to_parquet(
            db_path=db_path,
            staging_dir=staging_dir,
            target_date=target_date,
            dry_run=dry_run
        )

        file_id = upload_file_with_exponential_backoff(
            local_file_path=parquet_path,
            remote_filename=filename,
            drive_folder_id=drive_folder_id,
            credentials_file=credentials_file,
            dry_run=dry_run
        )

        if not keep_staging and not dry_run and file_id:
            if parquet_path.exists():
                parquet_path.unlink()
                logger.info(f"Cleaned up local staging file: {parquet_path}")

        logger.info("EOD Lakehouse Synchronization completed successfully.")
    except Exception as exc:
        logger.error(f"Pipeline failed: {exc}", exc_info=True)
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="ApexMarketEngine EOD Lakehouse Synchronization to Google Drive Cold Storage."
    )
    parser.add_argument("--db-path", default=DEFAULT_DUCKDB_PATH, help="Path to local DuckDB database")
    parser.add_argument("--staging-dir", default=DEFAULT_STAGING_DIR, help="Directory for Parquet staging")
    parser.add_argument("--target-folder-id", default=DEFAULT_DRIVE_FOLDER_ID, help="Google Drive target folder ID")
    parser.add_argument("--credentials-file", default=DEFAULT_CREDENTIALS_FILE, help="Path to GCP service account JSON")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (defaults to today)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate export and upload without modifying DB")
    parser.add_argument("--keep-staging", action="store_true", help="Keep local Parquet file in staging after upload")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        db_path=args.db_path,
        staging_dir=args.staging_dir,
        drive_folder_id=args.target_folder_id,
        credentials_file=args.credentials_file,
        target_date=args.date,
        dry_run=args.dry_run,
        keep_staging=args.keep_staging
    )
