"""
Atomic File Operations
======================
Prevents file corruption when the ETL daemon and FastAPI read-path access the
same Parquet files concurrently.  Without atomic writes a reader can observe a
partially-written file and crash with an ArrowInvalidFile exception.

Strategy
--------
1. Write to a randomly-named ``.tmp`` file in the *same directory* as the
   target (guarantees same filesystem / same NTFS volume for the rename).
2. Call ``os.replace(tmp, target)`` — which is atomic on POSIX (rename(2))
   and "as close to atomic as NTFS allows" on Windows (MoveFileEx with
   MOVEFILE_REPLACE_EXISTING).  On Windows a concurrent reader holding the
   target open will cause ERROR_ACCESS_DENIED; we retry up to
   ``_REPLACE_RETRIES`` times with a short backoff before giving up.
3. On any failure, clean up the tmp file and re-raise.

Bug_Condition: isBugCondition(input) where
    parquet_write_in_progress AND concurrent_read_attempted
Expected_Behavior: Atomic rename prevents file corruption; readers see either
    the old complete file or the new complete file, never a partial write.
Preservation: Sequential Parquet writes continue to produce valid files.

Requirements: 2.1.3
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd

# On Windows, os.replace() raises PermissionError if the destination is held
# open by a reader.  We retry briefly — readers call pd.read_parquet() which
# closes the file handle almost immediately.
_REPLACE_RETRIES: int = 5
_REPLACE_RETRY_DELAY: float = 0.05  # 50 ms between attempts

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AtomicParquetWriter
# ---------------------------------------------------------------------------

class AtomicParquetWriter:
    """Write a DataFrame to Parquet atomically.

    Parameters
    ----------
    target_path:
        Final destination for the Parquet file.  The parent directory must
        already exist (or will be created on the first :meth:`write` call).

    Example
    -------
        writer = AtomicParquetWriter("/data/feature_store/signals.parquet")
        writer.write(df)
    """

    def __init__(self, target_path: str | Path) -> None:
        self.target_path = Path(target_path)

    def write(
        self,
        df: pd.DataFrame,
        engine: str = "pyarrow",
        **kwargs,
    ) -> None:
        """Write *df* to :attr:`target_path` using a tmp-then-rename strategy.

        Parameters
        ----------
        df:
            DataFrame to serialise.
        engine:
            Parquet engine forwarded to ``pd.DataFrame.to_parquet``.
            Defaults to ``"pyarrow"``.
        **kwargs:
            Additional keyword arguments forwarded to ``to_parquet``
            (e.g. ``compression="snappy"``, ``index=False``).

        Raises
        ------
        Any exception raised by ``to_parquet`` or ``Path.replace`` is
        re-raised after the temporary file has been cleaned up.
        """
        # Ensure parent directory exists
        self.target_path.parent.mkdir(parents=True, exist_ok=True)

        # Unique tmp path in the same directory to guarantee same-filesystem rename
        tmp_suffix = f".{uuid.uuid4().hex[:8]}.tmp"
        tmp_path = self.target_path.with_suffix(tmp_suffix)

        try:
            df.to_parquet(tmp_path, engine=engine, **kwargs)
            logger.debug(
                "atomic_write: staged %d rows → %s", len(df), tmp_path.name
            )

            # Atomic rename (replaces existing target if present).
            # On Windows a concurrent reader holding the target open raises
            # PermissionError.  Retry briefly — the reader closes the handle
            # after pd.read_parquet() returns (typically < 50 ms).
            last_exc: Optional[Exception] = None
            for attempt in range(1, _REPLACE_RETRIES + 1):
                try:
                    os.replace(str(tmp_path), str(self.target_path))
                    last_exc = None
                    break
                except PermissionError as exc:
                    last_exc = exc
                    if attempt < _REPLACE_RETRIES:
                        logger.debug(
                            "atomic_write: replace attempt %d/%d blocked (target locked), "
                            "retrying in %.0f ms",
                            attempt,
                            _REPLACE_RETRIES,
                            _REPLACE_RETRY_DELAY * 1000,
                        )
                        time.sleep(_REPLACE_RETRY_DELAY)

            if last_exc is not None:
                raise last_exc

            logger.info(
                "atomic_write: committed %s (%d rows, %.1f KB)",
                self.target_path,
                len(df),
                self.target_path.stat().st_size / 1024,
            )

        except Exception as exc:
            # Best-effort cleanup — don't mask the original exception
            try:
                tmp_path.unlink(missing_ok=True)
                logger.warning(
                    "atomic_write: cleaned up tmp file %s after failure: %s",
                    tmp_path.name,
                    exc,
                )
            except Exception:
                pass
            raise


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def atomic_parquet_write(
    df: pd.DataFrame,
    target_path: str | Path,
    engine: str = "pyarrow",
    **kwargs,
) -> None:
    """Write *df* to *target_path* atomically.

    Convenience wrapper around :class:`AtomicParquetWriter`.

    Parameters
    ----------
    df:
        DataFrame to write.
    target_path:
        Destination Parquet file path.
    engine:
        Parquet engine (default ``"pyarrow"``).
    **kwargs:
        Extra arguments forwarded to ``pd.DataFrame.to_parquet``.

    Example
    -------
        atomic_parquet_write(df_features, "03_feature_store/signals.parquet")
    """
    AtomicParquetWriter(target_path).write(df, engine=engine, **kwargs)


# ---------------------------------------------------------------------------
# Safe reader with retry logic
# ---------------------------------------------------------------------------

def safe_read_parquet(
    path: str | Path,
    retries: int = 3,
    retry_delay: float = 0.1,
    **kwargs,
) -> pd.DataFrame:
    """Read a Parquet file with automatic retry on transient I/O errors.

    During the brief window between a ``.tmp`` write and the rename a race
    condition can theoretically still cause a read to fail (e.g. the target
    was deleted before being replaced).  This reader retries up to *retries*
    times with *retry_delay* seconds between attempts.

    Parameters
    ----------
    path:
        Path to the Parquet file.
    retries:
        Number of retry attempts after the first failure (default 3).
    retry_delay:
        Seconds to wait between retries (default 0.1).
    **kwargs:
        Extra keyword arguments forwarded to ``pd.read_parquet``.

    Returns
    -------
    ``pd.DataFrame``

    Raises
    ------
    The last exception encountered if all attempts are exhausted.
    """
    path = Path(path)
    last_exc: Optional[Exception] = None

    for attempt in range(1, retries + 2):  # +2 → initial try + retries
        try:
            df = pd.read_parquet(path, **kwargs)
            if attempt > 1:
                logger.info(
                    "safe_read_parquet: succeeded on attempt %d for %s",
                    attempt,
                    path,
                )
            return df
        except Exception as exc:
            last_exc = exc
            if attempt <= retries:
                logger.warning(
                    "safe_read_parquet: attempt %d failed for %s: %s — retrying in %.2fs",
                    attempt,
                    path,
                    exc,
                    retry_delay,
                )
                time.sleep(retry_delay)
            else:
                logger.error(
                    "safe_read_parquet: all %d attempts failed for %s: %s",
                    retries + 1,
                    path,
                    exc,
                )

    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Inline smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import tempfile
    import threading

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    print("=== atomic_file_operations smoke-test ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "test_output.parquet"

        sample_df = pd.DataFrame(
            {
                "ticker": ["NABIL", "NICA", "NLIC"] * 4,
                "close": [1200.0, 450.0, 3200.0] * 4,
                "volume": [15000, 8000, 4500] * 4,
            }
        )

        # ── 1. Basic write + read-back ────────────────────────────────
        atomic_parquet_write(sample_df, target)
        assert target.exists(), "Target file not created"
        df_back = safe_read_parquet(target)
        assert list(df_back.columns) == ["ticker", "close", "volume"]
        assert len(df_back) == len(sample_df)
        print("✓ Basic atomic write + read-back OK")

        # ── 2. Overwrite (replace) existing file ──────────────────────
        df2 = sample_df.copy()
        df2["close"] = df2["close"] * 2
        atomic_parquet_write(df2, target)
        df_back2 = safe_read_parquet(target)
        assert df_back2["close"].iloc[0] == df2["close"].iloc[0]
        print("✓ Overwrite of existing file OK")

        # ── 3. No orphaned tmp files after successful write ───────────
        tmp_files = list(Path(tmpdir).glob("*.tmp"))
        assert len(tmp_files) == 0, f"Orphaned tmp files: {tmp_files}"
        print("✓ No orphaned tmp files")

        # ── 4. Concurrent writer + reader don't corrupt data ──────────
        # Use a separate file so the earlier tests don't pollute the schema check.
        concurrent_target = Path(tmpdir) / "concurrent_test.parquet"

        # Prime the file so readers don't hit FileNotFoundError immediately
        atomic_parquet_write(pd.DataFrame({"val": [0]}), concurrent_target)

        # Writers race to replace the same file; on Windows some may lose
        # the rename race even after retries.  The important guarantee is
        # that *successful* reads always return a valid, complete DataFrame —
        # never a truncated or partially-written file.
        write_errors: list[str] = []
        read_errors: list[str] = []

        def _writer(i: int) -> None:
            df_w = pd.DataFrame({"val": list(range(i, i + 100))})
            try:
                atomic_parquet_write(df_w, concurrent_target)
            except PermissionError:
                # Acceptable on Windows when all retry attempts are exhausted
                # under extreme contention; logged, not a corruption event.
                write_errors.append(f"writer {i} lost rename race (Windows lock)")
            except Exception as exc:
                write_errors.append(f"write error: {exc}")

        def _reader() -> None:
            for _ in range(5):
                try:
                    df_r = safe_read_parquet(concurrent_target)
                    # Any successfully read file must have the expected schema
                    assert "val" in df_r.columns, "Corrupted read: 'val' column missing"
                    assert len(df_r) > 0, "Corrupted read: empty DataFrame"
                except FileNotFoundError:
                    pass  # File not yet written on first iteration
                except Exception as exc:
                    read_errors.append(f"read error: {exc}")
                time.sleep(0.01)

        threads = [threading.Thread(target=_writer, args=(i * 100,)) for i in range(4)]
        threads += [threading.Thread(target=_reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if read_errors:
            print(f"✗ Data corruption detected in concurrent reads: {read_errors}")
            sys.exit(1)
        if write_errors:
            print(f"  (note: {len(write_errors)} write(s) lost rename race on Windows — expected)")
        print("✓ Concurrent writers/readers completed without data corruption")

        # ── 5. AtomicParquetWriter class interface ────────────────────
        writer = AtomicParquetWriter(target)
        writer.write(sample_df, index=False)
        df_back3 = safe_read_parquet(target)
        assert len(df_back3) == len(sample_df)
        print("✓ AtomicParquetWriter.write() OK")

    print("\n✓ atomic_file_operations smoke-test PASSED")
