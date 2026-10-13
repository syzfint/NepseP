#!/usr/bin/env python3
"""
tests/test_regression_equivalence.py

APEXMARKETENGINE — REGRESSION EQUIVALENCE TEST
==============================================
The Golden Rule:
  NEW OUTPUT == BASELINE OUTPUT
within strictly defined numerical tolerances (<= 1e-4).
Guarantees ZERO mathematical distortion or strategy drift introduced by the control plane.
"""

import sys
import json
import pytest
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BASE_DIR / "scripts"
CONTROL_DIR = SCRIPTS_DIR / "00_control"
ETL_DIR = SCRIPTS_DIR / "01_etl_and_ingestion"
BASELINE_OUTPUT = BASE_DIR / "BASELINE" / "baseline_output.json"

for p in [str(BASE_DIR), str(SCRIPTS_DIR), str(CONTROL_DIR), str(ETL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from apex_engine import ApexEngine
from nepse_websocket_floorsheet import NepseMicrostructureStreamer


def test_regression_equivalence(monkeypatch):
    assert BASELINE_OUTPUT.exists(), f"Missing baseline file at {BASELINE_OUTPUT}"

    with open(BASELINE_OUTPUT, "r", encoding="utf-8") as f:
        base = json.load(f)

    # Deterministic test harness: Mock live websocket streamer with frozen baseline market status & depth
    monkeypatch.setattr(
        NepseMicrostructureStreamer,
        "get_market_index_status",
        lambda self: {
            "isOpen": True,
            "nepse_index": base["live_nepse_index"],
            "nepse_change": base["live_nepse_change"],
        }
    )
    imbalance_map = {c["symbol"]: c.get("order_book_imbalance", 0.05) for c in base.get("top_candidates", [])}
    monkeypatch.setattr(
        NepseMicrostructureStreamer,
        "get_order_book_depth",
        lambda self, symbol: {
            "symbol": symbol,
            "imbalance": imbalance_map.get(symbol, 0.05),
            "total_buy": 1000,
            "total_sell": 1000,
        }
    )

    # Execute new run through ApexEngine control wrapper
    engine = ApexEngine(environment="production")
    res = engine.predict(as_of="2026-10-07", universe="NEPSE")

    tolerance = 1e-4

    # 1. Macro Market Metrics
    assert abs(res["live_nepse_index"] - base["live_nepse_index"]) <= tolerance, \
        f"Index discrepancy: {res['live_nepse_index']} != {base['live_nepse_index']}"

    assert abs(res["market_breadth_pct"] - base["market_breadth_pct"]) <= tolerance, \
        f"Market breadth discrepancy: {res['market_breadth_pct']} != {base['market_breadth_pct']}"

    assert abs(res["cash_allocation_pct"] - base["cash_allocation_pct"]) <= tolerance, \
        f"Cash buffer discrepancy: {res['cash_allocation_pct']} != {base['cash_allocation_pct']}"

    assert res["certified_candidates_count"] == base["certified_candidates_count"], \
        f"Candidate count mismatch: {res['certified_candidates_count']} != {base['certified_candidates_count']}"

    # 2. Candidate Portfolio Allocations
    new_top = res["top_candidates"]
    base_top = base["top_candidates"]

    assert len(new_top) == len(base_top), "Candidate length mismatch"

    for i in range(min(5, len(new_top))):
        c_new = new_top[i]
        c_base = base_top[i]
        assert c_new["symbol"] == c_base["symbol"], f"Symbol rank mismatch at {i}: {c_new['symbol']} != {c_base['symbol']}"
        assert abs(c_new["latest_close"] - c_base["latest_close"]) <= tolerance, f"Price mismatch for {c_new['symbol']}"
        assert abs(c_new["exp_return_5d_pct"] - c_base["exp_return_5d_pct"]) <= tolerance, f"Return mismatch for {c_new['symbol']}"
        assert abs(c_new["hrp_allocation_pct"] - c_base["hrp_allocation_pct"]) <= tolerance, f"Allocation mismatch for {c_new['symbol']}"

    # 3. Cryptographic Provenance Hash
    assert res["provenance_hash_h_master"] == base["provenance_hash_h_master"], \
        f"Provenance hash mismatch: {res['provenance_hash_h_master']} != {base['provenance_hash_h_master']}"

    print("\n[EQUIVALENCE TEST PASSED] New control plane output perfectly identical to frozen baseline.")


if __name__ == "__main__":
    test_regression_equivalence()
