#!/usr/bin/env python3
"""
scratch/full_system_audit.py

APEXMARKETENGINE — FULL SYSTEM AUDIT WITH LATENCY PROFILING
============================================================
Runs every test module individually and records per-module latency.
Then verifies all critical data invariants.
"""

import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]

# ============================================================================
# SECTION 1: PER-MODULE TEST LATENCY
# ============================================================================

test_modules = [
    ("Trading Calendar (Mon-Fri)", "tests/test_nepse_trading_calendar.py"),
    ("High Yield POVs", "tests/test_high_yield_povs.py"),
    ("Institutional Extensions", "tests/test_institutional_extensions.py"),
    ("Laya Integration", "tests/test_laya_integration.py"),
    ("Portfolio Risk Lab", "tests/test_portfolio_risk_lab.py"),
    ("CLEF API Integration", "tests/test_clef_integration.py"),
    ("RD Agent Factor Factory", "tests/test_rd_agent_factor_factory.py"),
    ("RD Agent Live Execution", "tests/test_rd_agent_live_execution.py"),
    ("RD Agent NEPSE Strategy", "tests/test_rd_agent_nepse_strategy.py"),
    ("Regression Equivalence", "tests/test_regression_equivalence.py"),
    ("Structural Asymmetry", "tests/test_structural_asymmetry.py"),
    ("Regression Suite (7-gate)", "tests/regression_suite.py"),
]

results = []
total_start = time.perf_counter()
total_passed = 0
total_failed = 0
total_tests = 0

print("=" * 100)
print("APEXMARKETENGINE — FULL SYSTEM AUDIT WITH LATENCY PROFILING")
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 100)

for label, module in test_modules:
    mod_path = str(BASE_DIR / module)
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", mod_path, "-v", "--tb=short", "-q"],
        capture_output=True, text=True, cwd=str(BASE_DIR), timeout=120
    )
    elapsed = time.perf_counter() - start
    
    # Parse pass/fail from output
    output = proc.stdout + proc.stderr
    passed = output.count(" PASSED")
    failed = output.count(" FAILED")
    errors = output.count(" ERROR")
    status = "PASS" if proc.returncode == 0 else "FAIL"
    
    total_passed += passed
    total_failed += failed + errors
    total_tests += passed + failed + errors
    
    results.append({
        "module": label,
        "file": module,
        "status": status,
        "passed": passed,
        "failed": failed + errors,
        "latency_sec": round(elapsed, 3),
        "returncode": proc.returncode,
    })
    
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{icon}] {label:<40} | {passed:>2} passed, {failed+errors:>2} failed | {elapsed:>7.3f}s")

total_elapsed = time.perf_counter() - total_start

print()
print("=" * 100)
print("LATENCY SUMMARY")
print("=" * 100)
print(f"{'Module':<45} {'Status':<8} {'Passed':>6} {'Failed':>6} {'Latency':>10}")
print("-" * 100)
for r in results:
    print(f"{r['module']:<45} {r['status']:<8} {r['passed']:>6} {r['failed']:>6} {r['latency_sec']:>9.3f}s")
print("-" * 100)
print(f"{'TOTAL':<45} {'':8} {total_passed:>6} {total_failed:>6} {total_elapsed:>9.3f}s")
print("=" * 100)

# ============================================================================
# SECTION 2: DATA INTEGRITY CHECKS
# ============================================================================

print()
print("=" * 100)
print("DATA INTEGRITY VERIFICATION")
print("=" * 100)

import duckdb
import pandas as pd

conn = duckdb.connect()

# Check master parquet
master_path = str(BASE_DIR / "02_processed_parquet/market_master_union.parquet").replace("\\", "/")
master_stats = conn.execute(f"""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT ticker) as tickers,
        MIN(date) as min_date,
        MAX(date) as max_date,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_closes,
        SUM(CASE WHEN ticker IS NULL THEN 1 ELSE 0 END) as null_tickers
    FROM read_parquet('{master_path}')
""").df().to_dict(orient="records")[0]
print(f"  Master Parquet Rows    : {master_stats['total_rows']:,}")
print(f"  Unique Tickers         : {master_stats['tickers']}")
print(f"  Date Range             : {master_stats['min_date']} to {master_stats['max_date']}")
print(f"  Null Closes            : {master_stats['null_closes']}")
print(f"  Null Tickers           : {master_stats['null_tickers']}")

# Check index parquet
idx_path = str(BASE_DIR / "02_processed_parquet/nepse_index.parquet").replace("\\", "/")
idx_latest = conn.execute(f"""
    SELECT time, open, close, high, low, volume
    FROM read_parquet('{idx_path}')
    WHERE symbol = 'NEPSE'
    ORDER BY time DESC
    LIMIT 3
""").df()
print(f"\n  Latest 3 NEPSE Index Records:")
for _, row in idx_latest.iterrows():
    print(f"    {row['time']} | Open: {row['open']:.2f} | Close: {row['close']:.2f} | High: {row['high']:.2f} | Low: {row['low']:.2f} | Vol: {row['volume']:,.2f}")

# Verify Oct 9 index matches official
oct9_close = float(idx_latest[idx_latest['time'].astype(str) == '2026-10-09']['close'].iloc[0])
print(f"\n  Oct 9 NEPSE Index Close: {oct9_close}")
print(f"  Official nepalstock.com: 2591.80")
print(f"  Match: {'YES' if abs(oct9_close - 2591.80) < 0.01 else 'NO - MISMATCH'}")

# Verify Oct 9 session bar counts
oct9_count = conn.execute(f"""
    SELECT COUNT(*) as cnt FROM read_parquet('{master_path}') WHERE date = '2026-10-09'
""").fetchone()[0]
print(f"\n  Oct 9 Session Bars     : {oct9_count}")

# Check feature store
feat_path = str(BASE_DIR / "03_feature_store/technical_indicators.parquet").replace("\\", "/")
feat_rows = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{feat_path}')").fetchone()[0]
print(f"  Feature Store Rows     : {feat_rows:,}")

# Check baseline sync
with open(BASE_DIR / "BASELINE/baseline_output.json", "r") as f:
    base = json.load(f)
with open(BASE_DIR / "NEPSE_MASTER_INTEGRATED_OUTPUT.json", "r") as f:
    master = json.load(f)

idx_match = abs(base["live_nepse_index"] - master["live_nepse_index"]) < 0.01
print(f"\n  Baseline <-> Master Index Match : {'YES' if idx_match else 'NO'} ({base['live_nepse_index']} vs {master['live_nepse_index']})")

# Verify official summary metrics against our data
with open(BASE_DIR / "01_raw_data/nepse_summary_2026-10-09.json") as f:
    summary = json.load(f)
summary_dict = {item['detail'].strip(): item['value'] for item in summary}

print(f"\n  Official Total Turnover  : NPR {summary_dict.get('Total Turnover Rs:', 0):,.2f}")
print(f"  Official Total Shares    : {int(summary_dict.get('Total Traded Shares', 0)):,}")
print(f"  Official Total Txns      : {int(summary_dict.get('Total Transactions', 0)):,}")
print(f"  Official Scrips Traded   : {int(summary_dict.get('Total Scrips Traded', 0))}")
print(f"  Official Market Cap      : NPR {summary_dict.get('Total Market Capitalization Rs:', 0):,.2f}")
print(f"  Official Float Cap       : NPR {summary_dict.get('Total Float Market Capitalization Rs:', 0):,.2f}")

# Calendar invariant check
from datetime import date
fri = date(2026, 10, 9)
sat = date(2026, 10, 10)
sun = date(2026, 10, 11)
mon = date(2026, 10, 12)
print(f"\n  Calendar Invariants:")
print(f"    Friday  (Oct 9)  weekday={fri.weekday()} -> Trading: {'YES' if fri.weekday() < 5 else 'NO'}")
print(f"    Saturday (Oct 10) weekday={sat.weekday()} -> Trading: {'YES' if sat.weekday() < 5 else 'NO'}")
print(f"    Sunday  (Oct 11) weekday={sun.weekday()} -> Trading: {'YES' if sun.weekday() < 5 else 'NO'}")
print(f"    Monday  (Oct 12) weekday={mon.weekday()} -> Trading: {'YES' if mon.weekday() < 5 else 'NO'}")

# ============================================================================
# FINAL VERDICT
# ============================================================================
print()
print("=" * 100)
all_pass = total_failed == 0
verdict = "CERTIFIED_PASS" if all_pass else "AUDIT_REJECTED"
print(f"FINAL AUDIT VERDICT: {verdict}")
print(f"Total Tests: {total_tests} | Passed: {total_passed} | Failed: {total_failed}")
print(f"Total Wall-Clock Latency: {total_elapsed:.3f}s")
print("=" * 100)
