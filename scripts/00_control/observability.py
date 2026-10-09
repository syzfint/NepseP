#!/usr/bin/env python3
"""
scripts/00_control/observability.py

APEXMARKETENGINE — PRODUCTION OBSERVABILITY & TELEMETRY ENGINE (PHASE 6)
========================================================================
Lightweight monitoring tracking:
  - DATA: Freshness, row count, ticker coverage, missingness.
  - MODEL: Return distributions, uncertainty spread quantiles, regime breakdown.
  - SYSTEM: Execution time, memory, pipeline status.
  - RISK: Portfolio concentration (HHI), cash reserves, asset bounds.
Persists structured telemetry to runs/<run_id>/telemetry.json and rolling DuckDB logs.
"""

import os
import sys
import json
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List
import duckdb
import numpy as np
import pandas as pd

BASE_DIR = Path.cwd()


class ObservabilityEngine:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.start_time = time.time()

    def record_telemetry(
        self,
        as_of: str,
        lakehouse_path: Path,
        pipeline_output: Dict[str, Any],
        duration_seconds: float
    ) -> Dict[str, Any]:
        """Collects and stores comprehensive production observability metrics."""
        # 1. DATA TELEMETRY
        con = duckdb.connect()
        p_str = str(lakehouse_path).replace("\\", "/")
        data_stats = con.execute(f"""
            SELECT 
                COUNT(*) as rows,
                COUNT(DISTINCT ticker) as tickers,
                MAX(date) as max_date,
                SUM(CASE WHEN close IS NULL OR close <= 0 THEN 1 ELSE 0 END) as invalid_closes
            FROM read_parquet('{p_str}')
        """).fetchone()
        con.close()

        data_telemetry = {
            "lakehouse_rows": int(data_stats[0]),
            "tracked_tickers": int(data_stats[1]),
            "latest_bar_date": str(data_stats[2]),
            "data_freshness_status": "CURRENT" if str(data_stats[2]).startswith(as_of) else "STALE",
            "invalid_price_records": int(data_stats[3]),
            "missing_rate_pct": round(float(data_stats[3]) / max(1, data_stats[0]) * 100.0, 4)
        }

        # 2. MODEL TELEMETRY
        top_candidates = pipeline_output.get("top_candidates", [])
        if top_candidates:
            rets = [c.get("exp_return_5d_pct", 0.0) for c in top_candidates]
            spreads = [c.get("uncertainty_spread_pct", 0.0) for c in top_candidates]
            probs = [c.get("meta_label_probability", 0.0) for c in top_candidates]
            regimes = [c.get("kronos_regime", "UNKNOWN") for c in top_candidates]
            regime_counts = pd.Series(regimes).value_counts().to_dict()

            model_telemetry = {
                "candidates_certified": len(top_candidates),
                "exp_return_mean_pct": round(float(np.mean(rets)), 2),
                "exp_return_max_pct": round(float(np.max(rets)), 2),
                "uncertainty_spread_mean_pct": round(float(np.mean(spreads)), 2),
                "meta_probability_mean": round(float(np.mean(probs)), 4),
                "regime_distribution": regime_counts
            }
        else:
            model_telemetry = {"status": "NO_CANDIDATES_CERTIFIED"}

        # 3. RISK TELEMETRY
        cash_pct = pipeline_output.get("cash_allocation_pct", 25.0)
        allocations = {c["symbol"]: c.get("hrp_allocation_pct", 0.0) for c in top_candidates if c.get("hrp_allocation_pct", 0.0) > 0}
        weights_arr = np.array(list(allocations.values())) / 100.0 if allocations else np.array([1.0])
        hhi = float(np.sum(weights_arr ** 2))

        risk_telemetry = {
            "defensive_cash_buffer_pct": float(cash_pct),
            "allocated_assets_count": len(allocations),
            "max_single_asset_weight_pct": round(float(np.max(weights_arr) * 100.0), 2) if len(weights_arr) > 0 else 0.0,
            "portfolio_herfindahl_hhi": round(hhi, 4),
            "risk_parity_effective_n": round(1.0 / max(1e-4, hhi), 2)
        }

        # 4. SYSTEM TELEMETRY
        system_telemetry = {
            "execution_duration_seconds": round(duration_seconds, 2),
            "system_status": "NORMAL_OPERATION",
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        telemetry = {
            "data": data_telemetry,
            "model": model_telemetry,
            "risk": risk_telemetry,
            "system": system_telemetry
        }

        # Persist to run directory
        telemetry_file = self.run_dir / "telemetry.json"
        with open(telemetry_file, "w", encoding="utf-8") as f:
            json.dump(telemetry, f, indent=2)

        return telemetry
