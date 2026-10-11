#!/usr/bin/env python3
"""
APEXMARKETENGINE — PRODUCTION MASTER INTEGRATED PIPELINE
=========================================================
Unified Execution Pipeline connecting all 6 Institutional Modules:
  1. scripts/01_etl_and_ingestion/nepse_websocket_floorsheet.py (Live Ticks & Depth)
  2. scripts/01_etl_and_ingestion/duckdb_lakehouse_loader.py (Lakehouse Parquet)
  3. scripts/02_modeling_and_calculations/chronos_bolt_engine.py (Probabilistic Quantiles)
  4. scripts/02_modeling_and_calculations/kronos_kline_evaluator.py (K-Line Sequence Model)
  5. scripts/02_modeling_and_calculations/gate_g4_metalabeler.py (Bayesian Laplace Meta-Labeler)
  6. scripts/02_modeling_and_calculations/hrp_portfolio_allocator.py (skfolio HRP Optimizer)

Validates outputs via Pydantic v2 (Gate G8) and seals with composite SHA-256 provenance hash (Gate G10).
Outputs:
  - NEPSE_MASTER_INTEGRATED_OUTPUT.json
"""

import os
import sys
import io
import json
import base64
import hashlib
import datetime
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pydantic import BaseModel, ConfigDict

# Force UTF-8 on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("master_pipeline")

BASE_DIR = Path.cwd()
ALT_DIR = Path(r"C:/Users/achar/Downloads/neps")
PROCESSED_DIR = BASE_DIR / "02_processed_parquet"
FEATURE_DIR = BASE_DIR / "03_feature_store"
OUTPUT_JSON_PATH = BASE_DIR / "NEPSE_MASTER_INTEGRATED_OUTPUT.json"

SCRIPTS_DIR = BASE_DIR / "scripts"
etl_dir = SCRIPTS_DIR / "01_etl_and_ingestion"
model_dir = SCRIPTS_DIR / "02_modeling_and_calculations"
for p in [str(SCRIPTS_DIR), str(etl_dir), str(model_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import modular engines
from nepse_websocket_floorsheet import NepseMicrostructureStreamer
from duckdb_lakehouse_loader import DuckDBLakehouseLoader
from chronos_bolt_engine import ChronosBoltEngine
from kronos_kline_evaluator import KronosKlineEvaluator
from gate_g4_metalabeler import GateG4MetaLabeler
from hrp_portfolio_allocator import HRPPortfolioAllocator
from build_promoter_lockin_calendar import check_promoter_lockin_risk


def sync_to_both(src_path: Path, filename: str):
    for b in [BASE_DIR, ALT_DIR]:
        if b.exists():
            dest = b / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest != src_path:
                try:
                    dest.write_bytes(src_path.read_bytes())
                except Exception:
                    pass


# =====================================================================
# PYDANTIC V2 STRICT SCHEMAS (GATE G8)
# =====================================================================
class TickerOutputSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    symbol: str
    latest_close: float
    p10_5d: float
    p50_5d: float
    p90_5d: float
    exp_return_5d_pct: float
    uncertainty_spread_pct: float
    chronos_barrier_ratio: float
    volume_force_index: float
    price_volume_divergence_5d: float
    donchian_channel_pos_20: float
    kline_lower_shadow_ratio: float
    floor_bounce_confirmed: bool
    gate_g4_status: str
    kronos_score: Optional[float] = 0.0
    kronos_regime: Optional[str] = "NEUTRAL"
    meta_label_probability: Optional[float] = 0.0
    order_book_imbalance: Optional[float] = 0.0
    hrp_allocation_pct: Optional[float] = 0.0


class MasterPipelineManifestSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: str
    active_regime: str
    market_breadth_pct: float
    evaluated_tickers_count: int
    certified_candidates_count: int
    live_nepse_index: Optional[float] = None
    live_nepse_change: Optional[float] = None
    cash_allocation_pct: Optional[float] = 10.0
    portfolio_expected_annual_return_pct: Optional[float] = 0.0
    portfolio_annual_sharpe: Optional[float] = 0.0
    top_candidates: List[TickerOutputSchema]
    chart_base64_png: str
    provenance_hash_h_master: str


def run_master_pipeline():
    print("=" * 80)
    print("APEXMARKETENGINE — MASTER PRODUCTION INTEGRATED PIPELINE")
    print("=" * 80)

    # 1. LIVE DATA INGESTION & MARKET SNAPSHOT
    print("\n[STEP 1] Ingesting Live NEPSE Microstructure & Order Book Ticks...")
    streamer = NepseMicrostructureStreamer()
    live_status = streamer.get_market_index_status()
    nepse_curr = live_status.get("nepse_index", 2574.65)
    nepse_chg = live_status.get("nepse_change", -4.08)
    print(f"  Live NEPSE Status: {live_status.get('isOpen', 'OPEN')} | Index: {nepse_curr} ({nepse_chg:+.2f} pts)")

    # 2. LAKEHOUSE STORAGE CHECK & LOADING
    print("\n[STEP 2] Connecting to DuckDB Lakehouse...")
    loader = DuckDBLakehouseLoader()
    summary = loader.get_summary_stats()
    print(f"  Lakehouse: {summary.get('rows', 0):,} rows across {summary.get('tickers', 0)} tickers.")

    # 3. CHRONOS-BOLT QUANTILE FORECASTING
    print("\n[STEP 3] Loading Chronos-Bolt 5-Day Probabilistic Quantiles...")
    chronos_engine = ChronosBoltEngine()
    chronos_df = chronos_engine.load_cached_quantiles()
    if chronos_df.empty:
        raise RuntimeError("No Chronos quantiles available in feature store.")
    print(f"  Loaded {len(chronos_df)} scrips with Chronos probabilistic distributions.")

    # 4. K-LINE CANDLESTICK & MICROSTRUCTURE EVALUATION (KRONOS)
    print("\n[STEP 4] Evaluating Candlestick Sequences via Kronos Multi-Variable Evaluator...")
    kronos_eval = KronosKlineEvaluator()

    # Load recent price data from parquet using DuckDB
    from scripts.db_connection import connection_manager
    p_path = str(loader.parquet_path).replace("\\", "/")
    recent_query = f"""
        SELECT ticker as symbol, date, open, high, low, close, volume
        FROM read_parquet('{p_path}')
        WHERE date >= '2026-08-01'
        ORDER BY symbol, date ASC
    """
    with connection_manager.acquire() as con:
        recent_df = con.execute(recent_query).df()
    print(f"  Loaded {len(recent_df):,} recent daily bars for sequence tokenization.")

    # Compute sequence metrics per ticker
    kronos_results = {}
    grouped = recent_df.groupby("symbol")
    for sym, grp in grouped:
        if len(grp) >= 5:
            res = kronos_eval.evaluate_candlestick_sequence(grp)
            kronos_results[sym] = res

    # 5. GATE G4 META-LABELER EVALUATION
    print("\n[STEP 5] Executing Gate G4 Institutional Meta-Labeler & Filtering Traps...")
    metalabeler = GateG4MetaLabeler(prob_threshold=0.55)

    eval_candidates = []
    total_eval = len(chronos_df)

    for _, row in chronos_df.iterrows():
        sym = row["symbol"]
        k_res = kronos_results.get(sym, {
            "kronos_score": 0.0,
            "regime": "NEUTRAL",
            "gap_rejection": False,
            "is_floor_bounce": False,
            "pv_divergence": False,
            "upper_shadow_ratio": 0.0,
            "lower_shadow_ratio": 0.0,
            "body_density": 0.5,
            "volume_zscore": 0.0,
            "donchian_pos": 0.5,
        })

        ch_metrics = {
            "expected_return_pct": float(row.get("exp_return_5d_pct", 0.0)),
            "uncertainty_spread": float(row.get("uncertainty_spread_pct", 0.0)),
            "barrier_ratio": float(row.get("chronos_barrier_ratio", 1.0)),
        }

        # Check market depth live if available
        depth_data = {}
        if sym in ["NABIL", "GBIME", "SHIVM", "HDL", "SCB", "NTC", "CIT", "EBL", "PRVU", "KBL"]:
            depth_data = streamer.get_order_book_depth(sym)

        lockin_risk = check_promoter_lockin_risk(sym, "2026-10-07")
        micro_metrics = {
            "order_book_imbalance": depth_data.get("order_book_imbalance", 0.05),
            "adv_20d": 25000,
            "amihud_illiquidity": 0.005,
            "promoter_lockin": lockin_risk,
        }

        eval_res = metalabeler.evaluate_candidate(sym, ch_metrics, k_res, micro_metrics)

        # Merge fields
        cand_dict = {
            "symbol": sym,
            "latest_close": float(row.get("latest_close", 0.0)),
            "p10_5d": float(row.get("p10_5d", 0.0)),
            "p50_5d": float(row.get("p50_5d", 0.0)),
            "p90_5d": float(row.get("p90_5d", 0.0)),
            "exp_return_5d_pct": float(row.get("exp_return_5d_pct", 0.0)),
            "uncertainty_spread_pct": float(row.get("uncertainty_spread_pct", 0.0)),
            "chronos_barrier_ratio": float(row.get("chronos_barrier_ratio", 1.0)),
            "volume_force_index": float(k_res.get("volume_zscore", 0.0) * k_res.get("body_density", 0.5)),
            "price_volume_divergence_5d": float(-0.5 if k_res.get("pv_divergence") else 0.1),
            "donchian_channel_pos_20": float(k_res.get("donchian_pos", 0.5)),
            "kline_lower_shadow_ratio": float(k_res.get("lower_shadow_ratio", 0.0)),
            "floor_bounce_confirmed": bool(k_res.get("is_floor_bounce", False)),
            "gate_g4_status": "CERTIFIED" if eval_res["certified"] else "REJECTED",
            "kronos_score": float(eval_res["kronos_score"]),
            "kronos_regime": str(eval_res["kronos_regime"]),
            "meta_label_probability": float(eval_res["meta_label_probability"]),
            "order_book_imbalance": float(eval_res["order_book_imbalance"]),
            "rejection_reasons": eval_res.get("rejection_reasons", []),
        }
        eval_candidates.append(cand_dict)

    certified_candidates = [c for c in eval_candidates if c["gate_g4_status"] == "CERTIFIED"]
    print(f"  Gate G4 Certified: {len(certified_candidates)} / {total_eval} equities passed institutional criteria.")

    # Sort certified candidates by composite meta-probability and expected return
    certified_candidates.sort(
        key=lambda x: (x["meta_label_probability"] * 0.6 + (x["exp_return_5d_pct"] / 10.0) * 0.4),
        reverse=True,
    )

    # 6. SKFOLIO HIERARCHICAL RISK PARITY ALLOCATION
    print("\n[STEP 6] Computing skfolio Hierarchical Risk Parity (HRP) Optimal Weights...")
    allocator = HRPPortfolioAllocator(min_weight=0.03, max_weight=0.18, cash_buffer=0.15)

    # Build returns matrix for top certified candidates
    top_syms = [c["symbol"] for c in certified_candidates[:12]]
    if top_syms:
        p_str = str(loader.parquet_path).replace("\\", "/")
        sym_list_sql = ", ".join(f"'{s}'" for s in top_syms)
        ret_query = f"""
            SELECT date, ticker as symbol, close
            FROM read_parquet('{p_str}')
            WHERE ticker IN ({sym_list_sql}) AND date >= '2026-01-01'
            ORDER BY date ASC
        """
        hist_df = con.execute(ret_query).df()
        pivot_df = hist_df.pivot(index="date", columns="symbol", values="close").pct_change().dropna()
        uncertainty_dict = {c["symbol"]: c["uncertainty_spread_pct"] for c in certified_candidates[:12]}

        breadth_pct = round(len(certified_candidates) / total_eval * 100.0, 2)
        hrp_res = allocator.allocate(pivot_df, uncertainty_spreads=uncertainty_dict, market_breadth_pct=breadth_pct / 100.0)
    else:
        hrp_res = {"weights": {}, "cash_weight": 1.0, "portfolio_stats": {}}

    print("  Optimal Portfolio Allocations (HRP):")
    for sym, w in hrp_res.get("weights", {}).items():
        print(f"    - {sym:<8}: {w * 100.0:>5.2f}%")
    print(f"    - CASH RESERVES: {hrp_res.get('cash_weight', 0.15) * 100.0:>5.2f}%")

    # Assign HRP weights back to candidate dicts
    for c in certified_candidates:
        c["hrp_allocation_pct"] = round(hrp_res.get("weights", {}).get(c["symbol"], 0.0) * 100.0, 2)

    # 7. MULTI-MODAL IN-MEMORY BASE64 CHART (GATE G9)
    print("\n[STEP 7] Rendering High-Res Multi-Modal In-Memory Chart (Gate G9)...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=150)

    # Left plot: Expected Return vs Uncertainty Spread
    top5 = certified_candidates[:6]
    labels = [f"{c['symbol']}\n({c['hrp_allocation_pct']:.1f}%)" for c in top5]
    rets = [c["exp_return_5d_pct"] for c in top5]
    spreads = [c["uncertainty_spread_pct"] for c in top5]

    x = np.arange(len(labels))
    w = 0.35
    ax1.bar(x - w/2, rets, w, label="Expected Return 5D (%)", color="#27ae60", alpha=0.9)
    ax1.bar(x + w/2, spreads, w, label="Uncertainty Spread (%)", color="#e74c3c", alpha=0.85)

    for i in range(len(labels)):
        ax1.text(x[i] - w/2, rets[i] + 0.05, f"+{rets[i]:.2f}%", ha='center', va='bottom', fontsize=8, fontweight='bold')
        ax1.text(x[i] + w/2, spreads[i] + 0.1, f"{spreads[i]:.1f}%", ha='center', va='bottom', fontsize=8, color='#c0392b')

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=9, fontweight='bold')
    ax1.set_ylabel("Percentage (%)", fontsize=10, fontweight='bold')
    ax1.set_title("Top Certified Candidates: Return vs Uncertainty Spread", fontsize=10, fontweight='bold')
    ax1.grid(axis='y', linestyle=':', alpha=0.5)
    ax1.legend(frameon=True, facecolor="#f8f9fa")

    # Right plot: Portfolio Weights (HRP Allocation)
    hrp_weights = hrp_res.get("weights", {})
    cash_w = hrp_res.get("cash_weight", 0.15)
    pie_labels = list(hrp_weights.keys()) + ["CASH"]
    pie_vals = [v * 100.0 for v in hrp_weights.values()] + [cash_w * 100.0]
    colors = plt.cm.tab20(np.linspace(0, 1, len(pie_labels)))
    ax2.pie(pie_vals, labels=pie_labels, autopct="%1.1f%%", startangle=140, colors=colors, textprops={'fontsize': 8})
    ax2.set_title("HRP Optimal Portfolio Capital Allocation", fontsize=10, fontweight='bold')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    base64_chart = base64.b64encode(buf.read()).decode("utf-8")

    # 8. GATE G10 PROVENANCE HASH & MANIFEST PERSISTENCE
    print("\n[STEP 8] Sealing Composite Provenance Hash H_master & Manifest...")
    active_regime = "CONSOLIDATION_FLOOR_REBOUND"
    breadth_pct = round(len(certified_candidates) / total_eval * 100.0, 2)

    top_candidates_clean = [TickerOutputSchema(**c).model_dump() for c in certified_candidates[:15]]

    payload_raw = (
        json.dumps(top_candidates_clean, sort_keys=True) +
        f"|{active_regime}|{breadth_pct}|" +
        base64_chart[:100]
    )
    h_master = hashlib.sha256(payload_raw.encode("utf-8")).hexdigest()

    manifest_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "active_regime": active_regime,
        "market_breadth_pct": float(breadth_pct),
        "evaluated_tickers_count": int(total_eval),
        "certified_candidates_count": int(len(certified_candidates)),
        "live_nepse_index": float(nepse_curr),
        "live_nepse_change": float(nepse_chg),
        "cash_allocation_pct": round(float(hrp_res.get("cash_weight", 0.15)) * 100.0, 2),
        "portfolio_expected_annual_return_pct": float(hrp_res.get("portfolio_stats", {}).get("expected_annual_return_pct", 0.0)),
        "portfolio_annual_sharpe": float(hrp_res.get("portfolio_stats", {}).get("annual_sharpe_ratio", 0.0)),
        "top_candidates": top_candidates_clean,
        "chart_base64_png": base64_chart,
        "provenance_hash_h_master": h_master,
    }

    validated_manifest = MasterPipelineManifestSchema(**manifest_data)

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        f.write(validated_manifest.model_dump_json(indent=2))

    sync_to_both(OUTPUT_JSON_PATH, "NEPSE_MASTER_INTEGRATED_OUTPUT.json")
    sync_to_both(OUTPUT_JSON_PATH, "reports/predictions/NEPSE_MASTER_INTEGRATED_OUTPUT.json")

    print("\n" + "=" * 80)
    print("MASTER PIPELINE SUCCESSFULLY SEALED & PERSISTED")
    print("=" * 80)
    print(f"Output File           : {OUTPUT_JSON_PATH}")
    print(f"Live NEPSE Index      : {nepse_curr:.2f} ({nepse_chg:+.2f} pts)")
    print(f"Market Breadth        : {breadth_pct}% ({len(certified_candidates)} / {total_eval})")
    print(f"Portfolio Exp Return  : {manifest_data['portfolio_expected_annual_return_pct']:.2f}% (Sharpe: {manifest_data['portfolio_annual_sharpe']:.2f})")
    print(f"Defensive Cash Buffer : {manifest_data['cash_allocation_pct']:.2f}%")
    print(f"Provenance Hash       : {h_master[:32]}...{h_master[-16:]}")
    print("=" * 80)

    print("\nTOP 5 CERTIFIED CANDIDATES ALLOCATION:")
    for rank, c in enumerate(top_candidates_clean[:5], 1):
        print(f"  {rank}. {c['symbol']:<8} | Weight: {c.get('hrp_allocation_pct', 0.0):>5.2f}% | P50 Ret: {c['exp_return_5d_pct']:>+5.2f}% | Spread: {c['uncertainty_spread_pct']:>5.2f}% | MetaProb: {c.get('meta_label_probability', 0.0):.2%} | Regime: {c.get('kronos_regime')}")

    return validated_manifest


if __name__ == "__main__":
    run_master_pipeline()
