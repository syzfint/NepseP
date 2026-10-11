"""
DuckDB Connection Manager
=========================
Centralized thread-safe connection pool for DuckDB.

Replaces the anti-pattern of calling duckdb.connect() independently in every
FastAPI route handler, ETL module, and training script (which creates 40+
simultaneous file handles, causing "database is locked" errors and resource
exhaustion under concurrent load).

Usage
-----
    from scripts.db_connection import (
        connection_manager,
    )

    with connection_manager.acquire() as conn:
        df = conn.execute("SELECT ...").fetchdf()

The singleton ``connection_manager`` is created at module import time and is
safe to use from multiple threads.

Bug_Condition: isBugCondition(input) where
    input.concurrent_requests > 3 AND duckdb_connections >= 40
Expected_Behavior: Connection pool reuses ≤10 connections with zero locking
    conflicts.
Preservation: Single-threaded batch jobs continue to execute queries
    successfully with existing SQL syntax.

Requirements: 2.1.1
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Generator, Optional

import duckdb

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pool entry
# ---------------------------------------------------------------------------

class _PooledConnection:
    """Wrapper around a raw duckdb connection kept in the pool."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, conn_id: int) -> None:
        self._conn = conn
        self.conn_id = conn_id
        self.in_use = False
        self.created_at = time.monotonic()
        self.last_used_at = time.monotonic()
        self.use_count = 0

    @property
    def raw(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    def mark_acquired(self) -> None:
        self.in_use = True
        self.last_used_at = time.monotonic()
        self.use_count += 1

    def mark_released(self) -> None:
        self.in_use = False
        self.last_used_at = time.monotonic()

    def is_healthy(self) -> bool:
        """Quick health-check: run a trivial query to confirm the connection works."""
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Connection Manager
# ---------------------------------------------------------------------------

class DuckDBConnectionManager:
    """Thread-safe DuckDB connection pool (singleton).

    Parameters
    ----------
    max_connections:
        Maximum number of pooled connections (default 10).
    acquire_timeout:
        Seconds to wait for a free connection before raising ``TimeoutError``
        (default 30).
    """

    def __init__(
        self,
        max_connections: int = 10,
        acquire_timeout: float = 30.0,
        database: str = ":memory:",
        read_only: bool = False,
    ) -> None:
        self._max_connections = max_connections
        self._acquire_timeout = acquire_timeout
        self._database = database
        self._read_only = read_only
        self._lock = threading.Lock()
        self._not_full = threading.Condition(self._lock)
        self._pool: list[_PooledConnection] = []
        self._next_id = 0
        self._closed = False
        logger.info(
            "DuckDBConnectionManager initialised (max_connections=%d, database=%s, read_only=%s)",
            max_connections,
            database,
            read_only,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @contextmanager
    def acquire(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Acquire a pooled connection and yield the raw DuckDB connection.

        The connection is automatically returned to the pool on exit, even
        if an exception is raised inside the ``with`` block.

        Example
        -------
            with connection_manager.acquire() as conn:
                df = conn.execute("SELECT * FROM market").fetchdf()
        """
        pooled = self._acquire_connection()
        try:
            yield pooled.raw
        finally:
            self._release_connection(pooled)

    def close_all(self) -> None:
        """Close every pooled connection and shut down the manager.

        Should be called once during application teardown.
        """
        with self._lock:
            self._closed = True
            for pc in self._pool:
                pc.close()
            self._pool.clear()
            logger.info("DuckDBConnectionManager: all connections closed")

    # ------------------------------------------------------------------
    # Metrics / monitoring
    # ------------------------------------------------------------------

    def get_metrics(self) -> dict:
        """Return a snapshot of pool health metrics."""
        with self._lock:
            active = sum(1 for pc in self._pool if pc.in_use)
            idle = sum(1 for pc in self._pool if not pc.in_use)
            return {
                "pool_size": len(self._pool),
                "max_connections": self._max_connections,
                "active_connections": active,
                "idle_connections": idle,
                "closed": self._closed,
            }

    @property
    def active_connections(self) -> int:
        """Number of connections currently checked out by callers."""
        with self._lock:
            return sum(1 for pc in self._pool if pc.in_use)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _acquire_connection(self) -> _PooledConnection:
        """Block until a pooled connection is available, then return it."""
        if self._closed:
            raise RuntimeError("DuckDBConnectionManager has been shut down")

        deadline = time.monotonic() + self._acquire_timeout

        with self._not_full:
            while True:
                # Try to find an idle, healthy connection
                for pc in self._pool:
                    if not pc.in_use:
                        if not pc.is_healthy():
                            logger.warning(
                                "Replacing unhealthy connection conn_id=%d", pc.conn_id
                            )
                            pc.close()
                            self._pool.remove(pc)
                            break  # fall through to create a new one
                        pc.mark_acquired()
                        logger.debug(
                            "Acquired existing conn_id=%d (pool_size=%d)",
                            pc.conn_id,
                            len(self._pool),
                        )
                        return pc

                # No idle connection — create one if under the cap
                if len(self._pool) < self._max_connections:
                    pc = self._create_connection()
                    pc.mark_acquired()
                    return pc

                # Pool is full and all connections are busy — wait
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"DuckDBConnectionManager: timed out waiting for a free "
                        f"connection after {self._acquire_timeout}s "
                        f"(pool_size={len(self._pool)}, all in use)"
                    )
                logger.debug(
                    "Pool exhausted; waiting %.1fs for a free connection", remaining
                )
                self._not_full.wait(timeout=min(remaining, 0.1))

    def _release_connection(self, pc: _PooledConnection) -> None:
        with self._not_full:
            pc.mark_released()
            self._not_full.notify_all()
            logger.debug(
                "Released conn_id=%d (active=%d)",
                pc.conn_id,
                sum(1 for p in self._pool if p.in_use),
            )

    def _create_connection(self) -> _PooledConnection:
        """Create a new DuckDB connection (in-memory or file-based) and add it to the pool."""
        try:
            conn = duckdb.connect(database=self._database, read_only=self._read_only)
        except Exception as e:
            # If access is blocked by another process holding a write lock, retry read-only
            if not self._read_only and self._database != ":memory:":
                logger.warning("Write connection failed (%s), falling back to read_only=True", e)
                conn = duckdb.connect(database=self._database, read_only=True)
                self._read_only = True
            else:
                raise
        self._next_id += 1
        pc = _PooledConnection(conn, self._next_id)
        self._pool.append(pc)
        logger.debug(
            "Created new connection conn_id=%d (pool_size=%d, read_only=%s)",
            self._next_id,
            len(self._pool),
            self._read_only,
        )
        return pc


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: Global singleton — import and use directly:
#:   ``from scripts.db_connection import connection_manager``
connection_manager = DuckDBConnectionManager(max_connections=10, acquire_timeout=30.0)


# ---------------------------------------------------------------------------
# Per-file connection manager factory
# ---------------------------------------------------------------------------

_file_managers: dict[str, "DuckDBConnectionManager"] = {}
_file_managers_lock = threading.Lock()


def get_connection_manager(database: str = ":memory:", read_only: bool = False) -> "DuckDBConnectionManager":
    """Return a ``DuckDBConnectionManager`` scoped to *database*.

    For the shared in-memory pool, use the module-level :data:`connection_manager`
    singleton instead.  This factory is intended for file-based DuckDB paths
    (e.g. ``news_and_events.duckdb``, ``market_analytics.duckdb``) where each
    file requires its own isolated connection pool.

    Each unique (database, read_only) pair maps to a manager; repeated calls with
    the same parameters return the cached manager.

    Parameters
    ----------
    database:
        Path to a ``.duckdb`` file or ``":memory:"``.
    read_only:
        Whether to open connections in read-only mode (default False).

    Returns
    -------
    :class:`DuckDBConnectionManager`
    """
    if database == ":memory:":
        return connection_manager

    cache_key = f"{database}__ro_{read_only}"
    with _file_managers_lock:
        if cache_key not in _file_managers or _file_managers[cache_key]._closed:
            _file_managers[cache_key] = DuckDBConnectionManager(
                max_connections=3,
                acquire_timeout=30.0,
                database=database,
                read_only=read_only,
            )
            logger.info("get_connection_manager: created manager for %s (read_only=%s)", database, read_only)
        return _file_managers[cache_key]


# ---------------------------------------------------------------------------
# Inline smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    print("=== DuckDBConnectionManager smoke-test ===")

    # Single acquire/release
    with connection_manager.acquire() as conn:
        row = conn.execute("SELECT 42 AS answer").fetchone()
        assert row[0] == 42, f"Expected 42, got {row[0]}"
    print("✓ Single acquire/release works")

    # Metrics
    m = connection_manager.get_metrics()
    print(f"✓ Metrics: {m}")
    assert m["active_connections"] == 0, "Should be 0 active after release"

    # Concurrent acquire from multiple threads
    import concurrent.futures

    errors: list[str] = []

    def _thread_query(i: int) -> int:
        with connection_manager.acquire() as conn:
            result = conn.execute(f"SELECT {i} * 2").fetchone()
            return result[0]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_thread_query, i) for i in range(20)]
        for i, fut in enumerate(concurrent.futures.as_completed(futures)):
            try:
                _ = fut.result()
            except Exception as exc:
                errors.append(str(exc))

    if errors:
        print(f"✗ Concurrent test failed: {errors}")
        sys.exit(1)
    print(f"✓ 20 concurrent queries completed, active_connections={connection_manager.active_connections}")

    m2 = connection_manager.get_metrics()
    assert m2["active_connections"] == 0, "All connections should be released"
    print(f"✓ Final metrics: {m2}")

    connection_manager.close_all()
    print("✓ All connections closed — smoke-test PASSED")
