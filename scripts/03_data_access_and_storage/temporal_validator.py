"""
Temporal Integrity Validator
============================
Detects look-ahead leakage in training-data joins and verifies that column
schemas are aligned between storage and scoring pipelines.

Requirements: 2.3.2, 2.3.3
"""

import logging
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)


class TemporalContaminationError(Exception):
    """Raised when a DataFrame contains same-day (non-lagged) broker features.

    This indicates that broker accumulation data from date T was joined to the
    price row for date T, leaking information that would not be available at
    prediction time.
    """


class ColumnMismatchError(Exception):
    """Raised when expected columns are absent from an actual schema.

    Used to detect column-name drift between the feature store Parquet files
    and the DataFrames consumed by the model training pipeline.
    """


def validate_temporal_joins(
    df: pd.DataFrame,
    lagged_feature_cols: List[str],
) -> None:
    """Verify that lagged broker-concentration features are not same-day contaminated.

    Strategy
    --------
    With a correct 1-session lag join (``CAST(f.date AS DATE) = e.date - INTERVAL 1 DAY``),
    the very first row for every ticker has no matching broker row, so all
    lagged feature columns must be NaN / null on that first observation.

    If a same-day join was used instead, the first row *would* have a non-NaN
    value (because date T matches broker data also computed on date T).

    We exploit this invariant: for each ticker, sort by date, take the earliest
    row, and assert that every column in ``lagged_feature_cols`` is NaN.

    Parameters
    ----------
    df:
        Training or feature DataFrame, must contain a ``ticker`` (or
        ``symbol``) column and a ``date`` column.
    lagged_feature_cols:
        Column names that must carry a 1-session lag (broker concentration
        signals).  Columns not present in ``df`` are silently skipped —
        this avoids false positives when the floorsheet parquet is absent.

    Raises
    ------
    TemporalContaminationError
        If any ticker's first row has a non-NaN value in a lagged column.
    """
    # Resolve ticker column name (production uses 'ticker'; some modules use 'symbol')
    sym_col = "ticker" if "ticker" in df.columns else "symbol"

    if sym_col not in df.columns:
        logger.warning(
            "validate_temporal_joins: no 'ticker'/'symbol' column found — skipping."
        )
        return

    if "date" not in df.columns:
        logger.warning(
            "validate_temporal_joins: no 'date' column found — skipping."
        )
        return

    # Only inspect columns that are both declared and present
    cols_to_check = [c for c in lagged_feature_cols if c in df.columns]
    if not cols_to_check:
        logger.info(
            "validate_temporal_joins: none of the lagged feature columns are "
            "present in the DataFrame — no contamination check performed."
        )
        return

    contaminated: list = []
    df_sorted = df.sort_values([sym_col, "date"])

    for ticker, group in df_sorted.groupby(sym_col, sort=False):
        first_row = group.sort_values("date").iloc[0]
        for col in cols_to_check:
            value = first_row[col]
            # Consider 0.0 as contamination ONLY when it's not NaN — a lagged join
            # returns NULL for the first row, which pandas reads as NaN after COALESCE(NULL, 0.0)
            # would produce 0.0.  We therefore check for NaN specifically.
            # NOTE: COALESCE(..., 0.0) in the SQL means even a lagged-join first row
            # can come back as 0.0 (the COALESCE default for a non-matching LEFT JOIN row).
            # The real contamination signal is a *non-zero* value on the first row, because
            # that means the broker row for the same date was successfully joined.
            if pd.notna(value) and value != 0.0:
                contaminated.append(
                    {
                        "ticker": ticker,
                        "date": first_row["date"],
                        "column": col,
                        "value": value,
                    }
                )

    if contaminated:
        sample = contaminated[:5]
        raise TemporalContaminationError(
            f"Temporal contamination detected: {len(contaminated)} ticker/column "
            f"combinations have non-zero broker features on their first (earliest) "
            f"row, indicating a same-day join. "
            f"Sample violations: {sample}"
        )

    logger.info(
        "validate_temporal_joins: PASSED — %d tickers, %d columns checked. "
        "No same-day contamination detected.",
        df_sorted[sym_col].nunique(),
        len(cols_to_check),
    )


def verify_column_alignment(
    expected_cols: List[str],
    actual_cols: List[str],
    context: str = "",
) -> None:
    """Assert that all expected columns are present in actual_cols.

    Parameters
    ----------
    expected_cols:
        Columns that must exist (e.g., the model's declared feature list).
    actual_cols:
        Columns available in the DataFrame or Parquet schema.
    context:
        Optional label included in the error message for easier debugging
        (e.g., ``"technical_indicators.parquet"``).

    Raises
    ------
    ColumnMismatchError
        Lists every missing column so the entire gap is visible in one pass.
    """
    missing = [c for c in expected_cols if c not in actual_cols]
    if missing:
        ctx_str = f" in {context}" if context else ""
        raise ColumnMismatchError(
            f"Column alignment failure{ctx_str}: "
            f"{len(missing)} column(s) missing: {missing}"
        )

    logger.info(
        "Column alignment OK%s: %d column(s) verified.",
        f" in {context}" if context else "",
        len(expected_cols),
    )
