#!/usr/bin/env python3
"""
scripts/01_etl_and_ingestion/schema_canonicalization.py

NEPSE Trade Schema Canonicalization & Anti-Wash Gate
=====================================================
Fixes Bug Condition 2: Ingestion & Anti-Wash Filter Bypass

Root causes addressed:
  - Legacy CSV columns (Buyer/Seller) vs API columns (buyerMemberId/sellerMemberId)
    caused NULL != NULL comparisons, letting 100% of wash trades through.
  - Missing broker IDs triggered synthetic ID generation: (contract_id % 50) + 1
    making wash detection impossible.
  - Missing timestamps were replaced with wallclock time, destroying ordering.

This module implements:
  1. canonicalize_trade_schema()  — universal column rename to canonical names
  2. validate_trade_payload()     — fail-fast: reject rows with missing broker IDs
                                   or timestamps; NEVER generates synthetic data
  3. apply_anti_wash_filter()     — strict buyer_broker_id == seller_broker_id check
  4. log_rejected_to_dead_letter() — forensic audit trail for all rejections
  5. process_floorsheet_df()      — convenience pipeline: canonicalize → validate → filter
"""

import logging
from datetime import date
from pathlib import Path
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical column mapping
# ---------------------------------------------------------------------------
# Maps every known legacy/API column variant to a single canonical name.
# All downstream code operates exclusively on canonical names.
CANONICAL_SCHEMA: dict = {
    # Broker IDs — API payload style (NEPSE JSON)
    "buyerMemberId": "buyer_broker_id",
    "sellerMemberId": "seller_broker_id",
    # Broker IDs — legacy CSV style
    "Buyer": "buyer_broker_id",
    "Seller": "seller_broker_id",
    # Quantity variants
    "Quantity": "quantity",
    "contractQuantity": "quantity",
    # Price/rate variants
    "Rate": "price",
    "contractRate": "price",
    # Amount variants
    "Amount": "amount",
    "contractAmount": "amount",
    # Symbol/ticker variants
    "Symbol": "ticker",
    "stockSymbol": "ticker",
    # Date/timestamp variants
    "Date": "date",
    "tradeDate": "date",
    # Contract ID variant (kept for audit; not used for IDs)
    "ContractNo": "contract_id",
    "contractId": "contract_id",
}

# Fields that MUST be present and non-null for a trade to be accepted.
# Rejecting incomplete records rather than synthesising values.
_REQUIRED_FIELDS = ["buyer_broker_id", "seller_broker_id", "date"]


# ---------------------------------------------------------------------------
# 1. Schema canonicalization
# ---------------------------------------------------------------------------

def canonicalize_trade_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename all known column variants to canonical names.

    Does NOT drop or modify any records — pure column rename only.
    Columns not present in CANONICAL_SCHEMA are left unchanged.

    Parameters
    ----------
    df : pd.DataFrame
        Raw trade DataFrame with any mix of legacy/API column names.

    Returns
    -------
    pd.DataFrame
        Same data with columns renamed to canonical names where mappings exist.
    """
    # Only rename columns that actually exist in the DataFrame
    rename_map = {
        col: canonical
        for col, canonical in CANONICAL_SCHEMA.items()
        if col in df.columns
    }
    if rename_map:
        logger.debug("Canonicalizing columns: %s", rename_map)
        df = df.rename(columns=rename_map)

    return df


# ---------------------------------------------------------------------------
# 2. Fail-fast payload validation
# ---------------------------------------------------------------------------

def validate_trade_payload(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split a canonicalized DataFrame into accepted and rejected rows.

    A row is REJECTED when any of the following are missing/null:
      - buyer_broker_id
      - seller_broker_id
      - date (or timestamp)

    IMPORTANT: This function NEVER generates synthetic broker IDs or
    substitutes wallclock timestamps.  Missing data = rejected record.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame that has already been passed through
        ``canonicalize_trade_schema()``.

    Returns
    -------
    accepted : pd.DataFrame   — rows with all required fields present
    rejected : pd.DataFrame   — rows that failed validation, with an extra
                                ``rejection_reason`` column
    """
    assert "buyer_broker_id" in df.columns, (
        "buyer_broker_id column missing — run canonicalize_trade_schema() first"
    )
    assert "seller_broker_id" in df.columns, (
        "seller_broker_id column missing — run canonicalize_trade_schema() first"
    )

    rejection_reasons = []
    reject_mask = pd.Series(False, index=df.index)

    for field in _REQUIRED_FIELDS:
        if field not in df.columns:
            # Entire column absent → all rows rejected for this field
            field_mask = pd.Series(True, index=df.index)
        else:
            # Null, NaN, empty string, or the literal string "None"/"nan"
            col = df[field].astype(str).str.strip()
            field_mask = (
                df[field].isna()
                | col.isin({"", "None", "nan", "NaN", "null", "NULL"})
            )
        reject_mask |= field_mask

    if reject_mask.any():
        # Build per-row rejection reasons
        reasons = []
        for idx in df[reject_mask].index:
            missing = []
            for field in _REQUIRED_FIELDS:
                if field not in df.columns:
                    missing.append(f"{field}_column_absent")
                else:
                    val = df.at[idx, field]
                    val_str = str(val).strip()
                    if pd.isna(val) or val_str in {"", "None", "nan", "NaN", "null", "NULL"}:
                        missing.append(f"{field}_missing")
            reasons.append(", ".join(missing) if missing else "unknown")

        rejected = df[reject_mask].copy()
        rejected["rejection_reason"] = reasons

        n_rejected = reject_mask.sum()
        logger.warning(
            "VALIDATION: Rejected %d/%d trades due to missing required fields. "
            "No synthetic IDs or wallclock timestamps were generated.",
            n_rejected,
            len(df),
        )
        # Log a sample of rejections for diagnosis
        for _, row in rejected.head(5).iterrows():
            logger.warning(
                "  REJECTED trade — reason: %s | buyer_broker_id=%s | seller_broker_id=%s",
                row.get("rejection_reason"),
                row.get("buyer_broker_id", "<absent>"),
                row.get("seller_broker_id", "<absent>"),
            )
    else:
        rejected = df.iloc[0:0].copy()
        rejected["rejection_reason"] = pd.Series(dtype=str)

    accepted = df[~reject_mask].copy()
    logger.info(
        "VALIDATION: %d accepted, %d rejected (missing fields).",
        len(accepted),
        len(rejected),
    )
    return accepted, rejected


# ---------------------------------------------------------------------------
# 3. Anti-wash filter
# ---------------------------------------------------------------------------

def apply_anti_wash_filter(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Reject trades where buyer_broker_id == seller_broker_id (self-matched / wash trades).

    Operates on canonicalized column names only.  If the column is missing,
    raises AssertionError rather than silently passing all trades through.

    Parameters
    ----------
    df : pd.DataFrame
        Canonicalized, validated DataFrame (output of ``validate_trade_payload``
        accepted side).

    Returns
    -------
    clean_trades : pd.DataFrame  — legitimate cross-broker trades
    wash_trades  : pd.DataFrame  — self-matched (wash) trades, for audit
    """
    assert "buyer_broker_id" in df.columns, (
        "buyer_broker_id missing — run canonicalize_trade_schema() before apply_anti_wash_filter()"
    )
    assert "seller_broker_id" in df.columns, (
        "seller_broker_id missing — run canonicalize_trade_schema() before apply_anti_wash_filter()"
    )

    # Compare as strings to avoid type-mismatch NULL evaluations
    buyer_str = df["buyer_broker_id"].astype(str).str.strip()
    seller_str = df["seller_broker_id"].astype(str).str.strip()
    wash_mask = buyer_str == seller_str

    wash_trades = df[wash_mask].copy()
    clean_trades = df[~wash_mask].copy()

    n_wash = wash_mask.sum()
    n_total = len(df)
    if n_wash > 0:
        wash_amount = (
            wash_trades["amount"].sum()
            if "amount" in wash_trades.columns
            else float("nan")
        )
        logger.warning(
            "ANTI-WASH: Rejected %d/%d wash trades (buyer_broker_id == seller_broker_id). "
            "Total wash amount: %.2f",
            n_wash,
            n_total,
            wash_amount,
        )
        # Log representative samples
        for _, row in wash_trades.head(3).iterrows():
            logger.warning(
                "  WASH TRADE — buyer_broker_id=%s | seller_broker_id=%s | amount=%s",
                row.get("buyer_broker_id"),
                row.get("seller_broker_id"),
                row.get("amount", "?"),
            )
    else:
        logger.info("ANTI-WASH: No wash trades detected in %d records.", n_total)

    logger.info(
        "ANTI-WASH: %d clean cross-broker trades, %d wash trades filtered.",
        len(clean_trades),
        len(wash_trades),
    )
    return clean_trades, wash_trades


# ---------------------------------------------------------------------------
# 4. Dead-letter queue logging
# ---------------------------------------------------------------------------

def log_rejected_to_dead_letter(
    rejected_df: pd.DataFrame,
    reason: str,
    output_dir: Path,
) -> None:
    """
    Append rejected trade records to a daily dead-letter Parquet file.

    Rejected records are written to:
        {output_dir}/rejected_trades/{today}_rejected.parquet

    The file is appended if it already exists, enabling forensic analysis
    without any data loss.

    Parameters
    ----------
    rejected_df : pd.DataFrame
        Rows that were rejected (output of validate_trade_payload or
        apply_anti_wash_filter).
    reason : str
        Human-readable rejection category, e.g. ``"missing_broker_ids"``
        or ``"wash_trade"``.
    output_dir : Path
        Root directory (typically ``01_raw_data/`` or ``01_raw/``).
        The function creates ``rejected_trades/`` beneath it.
    """
    if rejected_df.empty:
        return

    rejected_dir = output_dir / "rejected_trades"
    rejected_dir.mkdir(parents=True, exist_ok=True)

    today_str = date.today().isoformat()
    out_path = rejected_dir / f"{today_str}_rejected.parquet"

    # Stamp each row with rejection metadata
    write_df = rejected_df.copy()
    write_df["_rejection_reason"] = reason
    write_df["_rejected_at"] = pd.Timestamp.now(tz="UTC").isoformat()

    if out_path.exists():
        existing = pd.read_parquet(out_path)
        write_df = pd.concat([existing, write_df], ignore_index=True)

    write_df.to_parquet(out_path, index=False)
    logger.info(
        "DEAD-LETTER: Wrote %d rejected records to %s (reason=%s).",
        len(rejected_df),
        out_path,
        reason,
    )


# ---------------------------------------------------------------------------
# 5. Convenience pipeline
# ---------------------------------------------------------------------------

def process_floorsheet_df(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Complete ingestion pipeline for a raw floorsheet DataFrame.

    Steps (in order):
      1. ``canonicalize_trade_schema`` — rename columns to canonical names
      2. ``validate_trade_payload``    — reject rows with missing IDs/date
      3. ``apply_anti_wash_filter``    — reject wash (self-matched) trades

    Parameters
    ----------
    df : pd.DataFrame
        Raw floorsheet data with any mix of legacy/API column names.

    Returns
    -------
    clean : pd.DataFrame             — valid, cross-broker trades ready for
                                       downstream feature computation
    rejected_incomplete : pd.DataFrame — rows rejected due to missing fields
    wash_trades : pd.DataFrame       — rows rejected because buyer == seller
    """
    # Step 1: Canonicalize column names
    df_canon = canonicalize_trade_schema(df)

    # Step 2: Validate required fields (fail-fast, no synthetic data)
    accepted, rejected_incomplete = validate_trade_payload(df_canon)

    # Step 3: Anti-wash filter on validated records
    clean, wash_trades = apply_anti_wash_filter(accepted)

    logger.info(
        "process_floorsheet_df summary — total=%d | clean=%d | "
        "rejected_incomplete=%d | wash_trades=%d",
        len(df),
        len(clean),
        len(rejected_incomplete),
        len(wash_trades),
    )
    return clean, rejected_incomplete, wash_trades
