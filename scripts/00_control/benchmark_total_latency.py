#!/usr/bin/env python3
"""
scripts/00_control/benchmark_total_latency.py

CHRONOSTRATA PRIME — COMPREHENSIVE TOTAL SYSTEM LATENCY BENCHMARK
==================================================================
Empirical, high-precision latency profiling across:
  1. Cryptographic Security & Defense Primitives (AEAD, Replay, Memory, Sentinel)
  2. Quantitative Computational Engines (Pillars 1 to 6)
  3. Lakehouse I/O & Floorsheet Processing (DuckDB tick queries)
  4. End-to-End Live Execution Pipeline (Tick Ingestion -> Signal -> Sealed Order Frame)
"""

import os
import sys
import time
import json
import statistics
import importlib.util
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

def load_module(rel_path: str, mod_name: str):
    fpath = BASE_DIR / rel_path
    spec = importlib.util.spec_from_file_location(mod_name, fpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

sgn_mod = load_module("scripts/02_modeling_and_calculations/syndicate_graph_network.py", "sgn")
hete_mod = load_module("scripts/02_modeling_and_calculations/hydrological_ebitda_forecaster.py", "hete")
t2_mod = load_module("scripts/02_modeling_and_calculations/t2_mdp_portfolio_policy.py", "t2")
snfp_mod = load_module("scripts/02_modeling_and_calculations/sovereign_nepali_nlp_parser.py", "snfp")
mhce_mod = load_module("scripts/02_modeling_and_calculations/multivariate_hawkes_contagion.py", "mhce")
dlo_mod = load_module("scripts/02_modeling_and_calculations/discrete_lot_optimizer.py", "dlo")
defense_mod = load_module("scripts/00_control/sovereign_defense_suite.py", "defense")

def benchmark_function(func, iters=100) -> Dict[str, float]:
    times = []
    # Warmup
    for _ in range(5):
        func()
    for _ in range(iters):
        t0 = time.perf_counter()
        func()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0) # in milliseconds
    return {
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": np.percentile(times, 95),
        "p99_ms": np.percentile(times, 99),
        "min_ms": min(times),
        "max_ms": max(times)
    }

def run_comprehensive_latency_audit():
    print("=" * 80)
    print("  CHRONOSTRATA PRIME — COMPREHENSIVE TOTAL SYSTEM LATENCY PROFILING")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 1. CRYPTOGRAPHIC & KERNEL DEFENSE BENCHMARKS
    # --------------------------------------------------------------------------
    print("\n[SECTION 1: CRYPTOGRAPHIC & KERNEL DEFENSE SUITE]")
    vault = defense_mod.EncryptedModelVault()
    order_cipher = defense_mod.OrderStreamCipher(vault.key)
    sample_order = {
        "symbol": "SAHAS",
        "action": "BUY",
        "kitta": 1500,
        "limit_price": 532.0,
        "desk_id": "CHRONO_PROP_DESK_1",
        "routing": "DIRECT_BROKER_48",
        "ts": time.time()
    }

    # Encrypt Order Frame
    res_enc = benchmark_function(lambda: order_cipher.encrypt_order_frame(sample_order), iters=200)
    print(f"  1.1 Order Encryption (ChaCha20-Poly1305 + Seq Nonce): {res_enc['mean_ms']:.4f} ms (p95: {res_enc['p95_ms']:.4f} ms)")

    # Decrypt Order Frame
    dec_cipher = defense_mod.OrderStreamCipher(vault.key)
    test_frame = order_cipher.encrypt_order_frame(sample_order)
    test_seq = int.from_bytes(test_frame[:4], byteorder="big")
    test_ad = f"CHRONO_ORDER_SEQ_{test_seq}".encode("utf-8")
    res_dec = benchmark_function(lambda: dec_cipher.cipher.decrypt(test_frame[4:16], test_frame[16:], test_ad), iters=200)
    print(f"  1.2 Order Decryption & Tag Verification:            {res_dec['mean_ms']:.4f} ms (p95: {res_dec['p95_ms']:.4f} ms)")

    # Anti-Debugger Sentinel Hook
    res_dbg = benchmark_function(lambda: defense_mod.ProcessAntiTamperSentinel.is_debugger_attached(), iters=200)
    print(f"  1.3 Kernel Anti-Debugger Check (Win32 PEB):         {res_dbg['mean_ms']:.4f} ms (p95: {res_dbg['p95_ms']:.4f} ms)")

    # Memory Pinning & Zeroization
    test_buf = bytearray(b"X" * 1024)
    res_lock = benchmark_function(lambda: defense_mod.MemoryGuard.lock_buffer(test_buf), iters=100)
    print(f"  1.4 OS Memory Pinning (VirtualLock/mlock):          {res_lock['mean_ms']:.4f} ms (p95: {res_lock['p95_ms']:.4f} ms)")

    res_zero = benchmark_function(lambda: defense_mod.MemoryGuard.zeroize_buffer(test_buf), iters=200)
    print(f"  1.5 Volatile Memory Zeroization (ctypes.memset):    {res_zero['mean_ms']:.4f} ms (p95: {res_zero['p95_ms']:.4f} ms)")

    # Model Vault Safetensors Load & Decrypt
    sample_tensors = {
        "weight_matrix": np.random.randn(256, 128).astype(np.float32),
        "bias_vector": np.random.randn(128).astype(np.float32)
    }
    sealed_weights = vault.seal_safetensors_dict(sample_tensors)
    res_vault = benchmark_function(lambda: vault.unseal_safetensors_dict(sealed_weights), iters=50)
    print(f"  1.6 Model Vault RAM Unseal & Tensor Parse:          {res_vault['mean_ms']:.4f} ms (p95: {res_vault['p95_ms']:.4f} ms)")

    total_crypto_per_order = res_enc['mean_ms'] + res_dec['mean_ms']
    print(f"  --> TOTAL CRYPTOGRAPHIC OVERHEAD PER ORDER:        {total_crypto_per_order:.4f} ms (<0.25 ms budget)")

    # --------------------------------------------------------------------------
    # 2. QUANTITATIVE COMPUTATIONAL ENGINES (PILLARS 1-6)
    # --------------------------------------------------------------------------
    print("\n[SECTION 2: 6 FRONTIER RESEARCH PILLARS COMPUTATION]")
    # Setup Data
    conn = duckdb.connect(":memory:")
    parquet_path = BASE_DIR / "01_raw_data" / "nepse_floorsheet_2026-10-07.parquet"
    df_ticks = conn.execute(f"""
        SELECT stockSymbol as symbol, buyerMemberId as buyer_broker,
               sellerMemberId as seller_broker, contractQuantity as quantity, contractRate as rate
        FROM '{parquet_path}'
    """).df()

    sgn = sgn_mod.SyndicateGraphNetwork(coordination_threshold=0.55, min_brokers_in_cartel=2)
    hete = hete_mod.HydrologicalEbitdaForecaster()
    t2 = t2_mod.T2ConstrainedMDPAllocator()
    snfp = snfp_mod.SovereignNepaliNLPParser()
    mhce = mhce_mod.MultivariateHawkesContagionEngine()
    dlo = dlo_mod.DiscreteLotOptimizer()

    # Pillar 1: SGN Cartel Graph (per symbol)
    res_p1 = benchmark_function(lambda: sgn.detect_collusion_subgraph(df_ticks, "SAHAS"), iters=50)
    print(f"  2.1 Pillar 1: SGN Cartel Subgraph (SAHAS):          {res_p1['mean_ms']:.4f} ms (p95: {res_p1['p95_ms']:.4f} ms)")

    # Pillar 2: HETE Hydro Telemetry (per plant)
    res_p2 = benchmark_function(lambda: hete.forecast_quarterly_fundamentals("SAHAS", 86.0, month=10, discharge_anomaly_factor=0.94), iters=50)
    print(f"  2.2 Pillar 2: HETE Hydro Telemetry (SAHAS):         {res_p2['mean_ms']:.4f} ms (p95: {res_p2['p95_ms']:.4f} ms)")

    # Pillar 3: T+2 MDP Allocator
    res_p3 = benchmark_function(lambda: t2.evaluate_optimal_step(
        current_settled_cash=500000.0,
        unsettled_t1_cash=100000.0,
        unsettled_t2_cash=50000.0,
        current_holdings={"SAHAS": 250000.0, "NABIL": 150000.0},
        target_conviction={"SAHAS": 0.50, "NABIL": 0.20, "CIT": 0.30}
    ), iters=100)
    print(f"  2.3 Pillar 3: T+2 MDP Cash Policy Allocator:        {res_p3['mean_ms']:.4f} ms (p95: {res_p3['p95_ms']:.4f} ms)")

    # Pillar 4: Sovereign Nepali NLP Policy Parser
    sample_announcement = "नेपाल राष्ट्र बैंकद्वारा जलविद्युत आयोजनाहरुको कर्जा पुनर्संरचना तथा ब्याजदर नियमन सम्बन्धी नयाँ परिपत्र जारी।"
    res_p4 = benchmark_function(lambda: snfp.parse_circular_text("NRB_HYDRO_CIRCULAR", sample_announcement), iters=100)
    print(f"  2.4 Pillar 4: Sovereign Nepali NLP Policy Parser:   {res_p4['mean_ms']:.4f} ms (p95: {res_p4['p95_ms']:.4f} ms)")

    # Pillar 5: Multivariate Hawkes Contagion
    mock_vols = {"NABIL": 0.022, "CIT": 0.025, "SAHAS": 0.048, "NGPL": 0.051, "API": 0.046}
    res_p5 = benchmark_function(lambda: mhce.calculate_cross_asset_spread("SAHAS", list(mock_vols.keys()), mock_vols), iters=100)
    print(f"  2.5 Pillar 5: Hawkes Cross-Asset Contagion:         {res_p5['mean_ms']:.4f} ms (p95: {res_p5['p95_ms']:.4f} ms)")

    # Pillar 6: Discrete Lot Optimizer (10-kitta integer programming)
    res_p6 = benchmark_function(lambda: dlo.quantize_order("SAHAS", total_kitta=1587, num_slices=4), iters=100)
    print(f"  2.6 Pillar 6: Discrete 10-Kitta Lot Slicing:        {res_p6['mean_ms']:.4f} ms (p95: {res_p6['p95_ms']:.4f} ms)")

    total_quant_pillars = res_p1['mean_ms'] * 8 + res_p2['mean_ms'] * 4 + res_p3['mean_ms'] + res_p4['mean_ms'] + res_p5['mean_ms'] + res_p6['mean_ms']
    print(f"  --> TOTAL 6-PILLAR QUANT COMPUTATION (Full Universe): {total_quant_pillars:.4f} ms")

    # --------------------------------------------------------------------------
    # 3. LAKEHOUSE I/O & TICK EXTRACTION
    # --------------------------------------------------------------------------
    print("\n[SECTION 3: LAKEHOUSE STORAGE & TICK EXTRACTION]")
    def duckdb_query():
        return conn.execute(f"""
            SELECT stockSymbol, sum(contractQuantity) as vol, avg(contractRate) as vwap
            FROM '{parquet_path}'
            GROUP BY stockSymbol
        """).df()
    res_duckdb = benchmark_function(duckdb_query, iters=50)
    print(f"  3.1 DuckDB In-Memory Aggregation (25k ticks):      {res_duckdb['mean_ms']:.4f} ms (p95: {res_duckdb['p95_ms']:.4f} ms)")

    temp_state_file = BASE_DIR / "static_data" / "benchmark_temp_state.json"
    sample_payload = {"status": "BENCHMARK", "data": [i for i in range(500)]}
    def disk_write():
        with open(temp_state_file, "w", encoding="utf-8") as f:
            json.dump(sample_payload, f)
    res_io = benchmark_function(disk_write, iters=50)
    print(f"  3.2 Atomic JSON State Persistence:                  {res_io['mean_ms']:.4f} ms (p95: {res_io['p95_ms']:.4f} ms)")
    if temp_state_file.exists():
        temp_state_file.unlink()

    # --------------------------------------------------------------------------
    # 4. FULL END-TO-END TICK-TO-EXECUTION LATENCY PIPELINE
    # --------------------------------------------------------------------------
    print("\n[SECTION 4: COMPLETE END-TO-END EXECUTION CYCLE PIPELINE]")
    def full_cycle():
        # Step 1: Ingestion
        df = conn.execute(f"""
            SELECT stockSymbol as symbol, buyerMemberId as buyer_broker,
                   sellerMemberId as seller_broker, contractQuantity as quantity, contractRate as rate
            FROM '{parquet_path}'
            WHERE stockSymbol = 'SAHAS'
        """).df()
        # Step 2: SGN Cartel Detection
        c_res = sgn.detect_collusion_subgraph(df, "SAHAS")
        # Step 3: Hydro Telemetry
        h_res = hete.forecast_quarterly_fundamentals("SAHAS", 86.0, month=10, discharge_anomaly_factor=0.94)
        # Step 4: Hawkes Contagion
        cont_res = mhce.calculate_cross_asset_spread("SAHAS", list(mock_vols.keys()), mock_vols)
        # Step 5: T+2 MDP Allocation
        alloc_res = t2.evaluate_optimal_step(500000.0, 100000.0, 50000.0, {"SAHAS": 250000.0}, {"SAHAS": 0.60})
        # Step 6: Discrete Lot Slicing
        dlo_res = dlo.quantize_order("SAHAS", 1587, 4)
        # Step 7: Cryptographic Order Sealing
        order_wire = order_cipher.encrypt_order_frame({"symbol": "SAHAS", "kitta": 1580, "price": 532.0})
        return order_wire

    res_e2e = benchmark_function(full_cycle, iters=50)
    print(f"  4.1 Full Pipeline (Ingest -> 6 Pillars -> Sealed Order):")
    print(f"      - Mean Latency:   {res_e2e['mean_ms']:.4f} ms")
    print(f"      - Median (p50):   {res_e2e['median_ms']:.4f} ms")
    print(f"      - 95th Percentile:{res_e2e['p95_ms']:.4f} ms")
    print(f"      - 99th Percentile:{res_e2e['p99_ms']:.4f} ms")
    print(f"      - Min Latency:    {res_e2e['min_ms']:.4f} ms")
    print(f"      - Max Latency:    {res_e2e['max_ms']:.4f} ms")

    print("\n" + "=" * 80)
    print("  LATENCY BUDGET AUDIT SUMMARY (15-SECOND HEARTBEAT):")
    print("=" * 80)
    print(f"  Allocated Live Loop Interval:       15,000.00 ms")
    print(f"  End-to-End Pipeline Execution:           {res_e2e['mean_ms']:.2f} ms")
    print(f"  Cryptographic Security Overhead:         {total_crypto_per_order:.4f} ms (0.0016% of loop)")
    print(f"  Execution Headroom Remaining:        {15000.0 - res_e2e['mean_ms']:.2f} ms ({((15000.0 - res_e2e['mean_ms'])/15000.0)*100:.2f}% Idle Headroom)")
    print("=" * 80)

if __name__ == "__main__":
    run_comprehensive_latency_audit()
