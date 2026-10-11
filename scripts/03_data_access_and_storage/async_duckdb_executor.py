"""
Async DuckDB Executor
=====================
Offloads CPU-bound DuckDB queries and Pandas/Matplotlib operations from the
FastAPI async event loop into a dedicated ``ThreadPoolExecutor``, eliminating
the 8.42-second event-loop blocking observed under concurrent load.

Bug_Condition: isBugCondition(input) where
    Pandas/Matplotlib operations block the async event loop
Expected_Behavior: All CPU-bound operations run in thread pool;
    event loop stays responsive (sub-100 ms for lightweight routes).
Preservation: Lightweight synchronous routes continue to work with
    sub-100 ms latency.

Requirements: 2.1.2, 2.1.4
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bootstrap connection_manager regardless of how this module is loaded
# ---------------------------------------------------------------------------
# When used as part of the scripts package the relative import works.
# When run directly (python async_duckdb_executor.py) we fall back to
# importlib.util.spec_from_file_location so the parent __init__.py is
# bypassed (it imports optional sub-modules not present in all environments).

def _load_connection_manager():
    """Return the connection_manager singleton from duckdb_connection_manager."""
    try:
        from .duckdb_connection_manager import connection_manager as _cm
        return _cm
    except ImportError:
        pass

    # Direct-execution fallback
    _here = Path(__file__).resolve().parent
    _spec = importlib.util.spec_from_file_location(
        "_dcm_direct",
        _here / "duckdb_connection_manager.py",
    )
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    return _mod.connection_manager


connection_manager = _load_connection_manager()


# Default worker count — keeps DuckDB CPU usage bounded while still allowing
# four concurrent blocking operations before new requests queue.
_DEFAULT_MAX_WORKERS: int = int(os.getenv("ASYNC_DUCKDB_MAX_WORKERS", "4"))


class AsyncDuckDBExecutor:
    """Wraps the DuckDB connection pool in an async-friendly interface.

    All public ``async`` methods run blocking work in a ``ThreadPoolExecutor``
    via ``loop.run_in_executor``, keeping the asyncio event loop free for
    lightweight tasks.

    Parameters
    ----------
    max_workers:
        Thread-pool size.  Defaults to ``ASYNC_DUCKDB_MAX_WORKERS`` env var
        or 4.

    Example
    -------
        async with AsyncDuckDBExecutor() as executor:
            df = await executor.execute_df("SELECT 1 AS ok")
    """

    def __init__(self, max_workers: int = _DEFAULT_MAX_WORKERS) -> None:
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="duckdb_async",
        )
        logger.info(
            "AsyncDuckDBExecutor initialised (max_workers=%d)", max_workers
        )

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "AsyncDuckDBExecutor":
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.shutdown()

    # ------------------------------------------------------------------
    # Core query methods
    # ------------------------------------------------------------------

    async def execute_query(
        self,
        query: str,
        params: Optional[Any] = None,
    ) -> List[tuple]:
        """Execute *query* in the thread pool and return rows as a list of tuples.

        Parameters
        ----------
        query:
            SQL query string.
        params:
            Optional query parameters passed directly to ``conn.execute()``.

        Returns
        -------
        list of tuples — same as ``conn.execute(query).fetchall()``.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._run_query,
            query,
            params,
        )

    async def execute_df(
        self,
        query: str,
        params: Optional[Any] = None,
    ) -> pd.DataFrame:
        """Execute *query* in the thread pool and return a ``pd.DataFrame``.

        Parameters
        ----------
        query:
            SQL query string.
        params:
            Optional query parameters.

        Returns
        -------
        ``pd.DataFrame`` — same as ``conn.execute(query).fetchdf()``.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._run_query_df,
            query,
            params,
        )

    async def read_parquet_async(
        self,
        parquet_path: str,
        where: Optional[str] = None,
    ) -> pd.DataFrame:
        """Read a Parquet file in the thread pool, optionally filtered.

        Uses DuckDB for fast columnar reads — much faster than
        ``pd.read_parquet`` for large files with predicate push-down.

        Parameters
        ----------
        parquet_path:
            Absolute or relative path to the ``.parquet`` file.
        where:
            Optional SQL ``WHERE`` clause (without the ``WHERE`` keyword)
            applied as a DuckDB predicate, e.g.
            ``"ticker = 'NABIL' AND date >= '2024-01-01'"``.

        Returns
        -------
        ``pd.DataFrame``
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._read_parquet,
            parquet_path,
            where,
        )

    async def run_cpu_bound(
        self,
        func: Callable[..., Any],
        *args: Any,
    ) -> Any:
        """Run an arbitrary CPU-bound callable in the thread pool.

        Use this for Pandas transforms and Matplotlib chart generation that
        would otherwise block the event loop.

        Parameters
        ----------
        func:
            A regular (synchronous) callable.
        *args:
            Positional arguments forwarded to *func*.

        Returns
        -------
        Whatever *func* returns.

        Example
        -------
            chart_bytes = await executor.run_cpu_bound(generate_chart, df, "NABIL")
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the thread pool.

        Parameters
        ----------
        wait:
            If ``True`` (default), block until all pending futures complete.
        """
        self._executor.shutdown(wait=wait)
        logger.info("AsyncDuckDBExecutor thread pool shut down")

    # ------------------------------------------------------------------
    # Synchronous helpers (run inside the thread pool)
    # ------------------------------------------------------------------

    @staticmethod
    def _run_query(query: str, params: Optional[Any]) -> List[tuple]:
        with connection_manager.acquire() as conn:
            if params is not None:
                result = conn.execute(query, params)
            else:
                result = conn.execute(query)
            return result.fetchall()

    @staticmethod
    def _run_query_df(query: str, params: Optional[Any]) -> pd.DataFrame:
        with connection_manager.acquire() as conn:
            if params is not None:
                result = conn.execute(query, params)
            else:
                result = conn.execute(query)
            return result.fetchdf()

    @staticmethod
    def _read_parquet(parquet_path: str, where: Optional[str]) -> pd.DataFrame:
        with connection_manager.acquire() as conn:
            if where:
                sql = (
                    f"SELECT * FROM read_parquet('{parquet_path}') "
                    f"WHERE {where}"
                )
            else:
                sql = f"SELECT * FROM read_parquet('{parquet_path}')"
            return conn.execute(sql).fetchdf()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: Global singleton — import and use directly:
#:   ``from scripts.03_data_access_and_storage.async_duckdb_executor import async_executor``
async_executor = AsyncDuckDBExecutor()


# ---------------------------------------------------------------------------
# FastAPI convenience helper
# ---------------------------------------------------------------------------

async def run_in_threadpool(func: Callable[..., Any], *args: Any) -> Any:
    """Convenience wrapper for FastAPI route handlers.

    Runs *func* with *args* in the global :data:`async_executor` thread pool.
    Avoids the need to import ``async_executor`` directly in every route.

    Example
    -------
        @router.get("/chart/{symbol}")
        async def get_chart(symbol: str):
            chart_bytes = await run_in_threadpool(build_chart, symbol)
            return Response(content=chart_bytes, media_type="image/png")
    """
    return await async_executor.run_cpu_bound(func, *args)


# ---------------------------------------------------------------------------
# Inline smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import time

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    async def _main() -> None:
        print("=== AsyncDuckDBExecutor smoke-test ===\n")

        executor = AsyncDuckDBExecutor(max_workers=4)

        # ── 1. execute_query ──────────────────────────────────────────
        rows = await executor.execute_query("SELECT 42 AS answer")
        assert rows == [(42,)], f"Expected [(42,)], got {rows}"
        print("✓ execute_query works")

        # ── 2. execute_df ─────────────────────────────────────────────
        df = await executor.execute_df("SELECT 7 * 6 AS answer")
        assert int(df.iloc[0]["answer"]) == 42, f"Expected 42, got {df.iloc[0]['answer']}"
        print("✓ execute_df works")

        # ── 3. run_cpu_bound ──────────────────────────────────────────
        def _heavy(x: int) -> int:
            time.sleep(0.01)  # simulate CPU work
            return x * 2

        result = await executor.run_cpu_bound(_heavy, 21)
        assert result == 42, f"Expected 42, got {result}"
        print("✓ run_cpu_bound works")

        # ── 4. Concurrent execute_df (verifies thread pool) ───────────
        t0 = time.monotonic()
        tasks = [executor.execute_df(f"SELECT {i} AS val") for i in range(12)]
        results = await asyncio.gather(*tasks)
        elapsed = time.monotonic() - t0
        assert len(results) == 12
        assert all(int(r.iloc[0]["val"]) == i for i, r in enumerate(results))
        print(f"✓ 12 concurrent execute_df calls completed in {elapsed:.2f}s")

        # ── 5. run_in_threadpool convenience wrapper ──────────────────
        val = await run_in_threadpool(lambda: 99)
        assert val == 99
        print("✓ run_in_threadpool wrapper works")

        executor.shutdown()
        print("\n✓ AsyncDuckDBExecutor smoke-test PASSED")

    asyncio.run(_main())
