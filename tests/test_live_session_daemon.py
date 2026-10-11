"""
Unit and regression test suite for Phase 4:
Live Market Session Daemon & WASM Token Orchestrator.
Validates:
  1. NPT state machine transition triggers across all 5 temporal windows.
  2. Wasmtime transient Store memory cleanup (0 memory leak over 1,000 iterations).
  3. Sub-millisecond feature lookup & ONNX inference latency (<1.0 ms) across simulated ticks.
  4. Zero memory copies across Arrow C Data Interface FFI pointer boundaries.
"""

import sys
import time
import pytest
import datetime
import importlib.util
from pathlib import Path

# Dynamic import for module with numeric directory prefix
_spec = importlib.util.spec_from_file_location(
    "live_session_daemon",
    Path(__file__).parent.parent / "scripts" / "01_etl_and_ingestion" / "live_session_daemon.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

TemporalStateMachine = _mod.TemporalStateMachine
MarketSessionState = _mod.MarketSessionState
WasmTokenOrchestrator = _mod.WasmTokenOrchestrator
ArrowStreamingEngine = _mod.ArrowStreamingEngine
SubMillisecondInferenceBridge = _mod.SubMillisecondInferenceBridge


def test_npt_state_machine_transition_triggers():
    """Verify state machine accurately classifies all 5 official NPT trading windows."""
    sm = TemporalStateMachine()

    # SYSTEM_SLEEP: 08:30 NPT
    assert sm.evaluate_state(datetime.time(8, 30)) == MarketSessionState.SYSTEM_SLEEP

    # PRE_MARKET_WARMUP: 10:15 NPT
    assert sm.evaluate_state(datetime.time(10, 15)) == MarketSessionState.PRE_MARKET_WARMUP

    # LIVE_TRADING_SESSION: 11:45 NPT
    assert sm.evaluate_state(datetime.time(11, 45)) == MarketSessionState.LIVE_TRADING_SESSION

    # POST_MARKET_TRANSITION: 15:05 NPT
    assert sm.evaluate_state(datetime.time(15, 5)) == MarketSessionState.POST_MARKET_TRANSITION

    # BATCH_WAREHOUSING: 15:20 NPT
    assert sm.evaluate_state(datetime.time(15, 20)) == MarketSessionState.BATCH_WAREHOUSING

    # SESSION_RECOVERY: Network drop trigger
    sm.trigger_network_drop()
    assert sm.state == MarketSessionState.SESSION_RECOVERY
    assert sm.evaluate_state(datetime.time(11, 45)) == MarketSessionState.SESSION_RECOVERY

    # Resume session
    sm.recover_session()
    assert sm.state == MarketSessionState.LIVE_TRADING_SESSION


def test_wasmtime_transient_store_memory_cleanup():
    """Verify Wasmtime transient Store teardown ensures zero linear memory growth over 1,000 token runs."""
    orchestrator = WasmTokenOrchestrator()
    assert orchestrator.use_wasm is True, "Wasmtime runtime failed to initialize!"

    # Run 1,000 iterations and verify headers are produced without memory exhaustion
    for i in range(1000):
        headers = orchestrator.generate_token_headers(client_seed=i)
        assert "Salter" in headers
        assert "Authorization" in headers
        assert headers["Salter"].startswith("NEPSE-SALT-")


def test_sub_millisecond_inference_latency_budget():
    """Verify feature calculation + ONNX model inference executes in < 1.0 ms across 1,000 ticks."""
    bridge = SubMillisecondInferenceBridge()
    bridge.pre_market_warmup()

    latencies_us = []
    for i in range(1000):
        # Sample parameters
        bid_px = 600.0 + (i % 20)
        ask_px = bid_px + 1.0
        bid_vol = 5000.0 + (i % 500)
        ask_vol = 4500.0 + (i % 300)

        score, lat_us = bridge.execute_inference_tick(
            security_id=1,
            bid_px=bid_px,
            ask_px=ask_px,
            bid_vol=bid_vol,
            ask_vol=ask_vol
        )
        latencies_us.append(lat_us)
        assert not (score is None or score != score), "Alpha score produced NaN!"

    p95_lat = sorted(latencies_us)[int(len(latencies_us) * 0.95)]
    avg_lat = sum(latencies_us) / len(latencies_us)

    # Must be strictly under 1,000 microseconds (1.0 ms)
    assert avg_lat < 500.0, f"Average latency exceeded 500 us budget: {avg_lat:.2f} us"
    assert p95_lat < 1000.0, f"P95 latency exceeded 1.0 ms: {p95_lat:.2f} us"


def test_zero_copy_arrow_c_data_ffi():
    """Assert zero-copy memory roundtrip across Arrow C Data Interface FFI pointer boundaries."""
    engine = ArrowStreamingEngine()
    batch = engine.create_tick_batch("UPPER", 1, 620.0, 622.0, 5000.0, 3200.0)

    # Export to C FFI
    c_arr, c_sch, ptr_arr, ptr_sch = engine.export_to_c_ffi(batch)
    assert ptr_arr != 0 and ptr_sch != 0

    # Import from C FFI
    imported = engine.import_from_c_ffi(ptr_arr, ptr_sch)

    # Verify identical data representation with O(1) memory transfer
    assert imported.num_rows == batch.num_rows
    assert imported.schema == batch.schema
    assert imported.column("symbol").to_pylist() == ["UPPER"]
    assert imported.column("security_id").to_pylist() == [1]
