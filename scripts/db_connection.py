"""
db_connection.py — Thin proxy for the DuckDB connection manager.

The actual implementation lives in
  scripts/03_data_access_and_storage/duckdb_connection_manager.py

Python's import system cannot traverse dotted paths whose components begin with
a digit (e.g. ``scripts.03_data_access_and_storage``), so all callers should
import from this module instead:

    from scripts.db_connection import connection_manager, get_connection_manager

or, when called from within the ``scripts/`` tree as a standalone script:

    from db_connection import connection_manager, get_connection_manager
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CM_PATH = _HERE / "03_data_access_and_storage" / "duckdb_connection_manager.py"

_spec = importlib.util.spec_from_file_location("duckdb_connection_manager", _CM_PATH)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_module)  # type: ignore[union-attr]

connection_manager = _module.connection_manager
get_connection_manager = _module.get_connection_manager
DuckDBConnectionManager = _module.DuckDBConnectionManager

__all__ = ["connection_manager", "get_connection_manager", "DuckDBConnectionManager"]
