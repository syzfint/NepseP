#!/usr/bin/env python3
"""
tests/test_institutional_extensions.py

Unit and integration tests for the three institutional Tier-1 extensions:
1. Playwright / TMS Order-Staging Connector (10-lot sizing, <=15% LOB depth, circuits, T+2 Demat)
2. CLEF Multimodal Panic Cycle Fine-Tuning (chart generation, LoRA adapter configuration, loss convergence)
3. Remote S3 / MinIO Cloud Storage Sync (manifests, models, baseline hashes, verification receipts)
"""

import os
import sys
import json
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scripts" / "00_control"))

from tms_order_staging import TMSOrderStagingEngine, PlaywrightTMSBridge, run_staging_pipeline
from clef_panic_cycle_trainer import ClefPanicDatasetBuilder, ClefPanicLoRATrainer
from s3_storage_sync import CloudStorageAdapter, CloudSyncManager


class TestInstitutionalExtensions(unittest.TestCase):

    def test_01_tms_order_staging_microstructure(self):
        """Validates that staged orders obey board lots, 15% depth, and circuit limits."""
        res = run_staging_pipeline(cash_npr=1_000_000.0, dry_run=True)
        blotter = res["blotter"]
        staging_res = res["staging_result"]

        self.assertTrue(blotter["compliance_passed"])
        self.assertGreater(blotter["total_staged_orders"], 0)
        self.assertLessEqual(blotter["total_buy_value_npr"], blotter["available_cash_npr"])

        for tkt in blotter["tickets"]:
            # Board lot check (strictly multiple of 10)
            self.assertEqual(tkt["quantity"] % 10, 0, f"Ticket {tkt['ticket_id']} quantity not multiple of 10")
            self.assertGreaterEqual(tkt["quantity"], 10)
            # 15% LOB depth cap check
            self.assertLessEqual(tkt["lob_depth_share_pct"], 15.01)
            # Circuit check
            self.assertGreaterEqual(tkt["limit_price"], tkt["circuit_min"])
            self.assertLessEqual(tkt["limit_price"], tkt["circuit_max"])
            # Status
            self.assertEqual(tkt["status"], "STAGED")

        self.assertEqual(staging_res["status"], "SUCCESS")
        self.assertIn("execution_hash", staging_res)

    def test_02_clef_panic_cycle_adapter(self):
        """Validates CLEF multimodal fine-tuning artifacts and checkpoint manifests."""
        model_dir = BASE_DIR / "registry" / "models" / "MODEL-CLEF-LORA-001"
        self.assertTrue(model_dir.exists())

        config_path = model_dir / "adapter_config.json"
        weights_path = model_dir / "adapter_model.safetensors"
        manifest_path = model_dir / "model_manifest.json"

        self.assertTrue(config_path.exists())
        self.assertTrue(weights_path.exists())
        self.assertTrue(manifest_path.exists())

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["peft_type"], "LORA")
        self.assertEqual(cfg["r"], 16)
        self.assertEqual(cfg["lora_alpha"], 32)
        self.assertIn("q_proj", cfg["target_modules"])

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["model_id"], "MODEL-CLEF-LORA-001")
        self.assertEqual(manifest["status"], "CERTIFIED_FOR_PRODUCTION")
        self.assertLess(manifest["final_val_loss"], 1.0)

    def test_03_cloud_storage_sync(self):
        """Validates that cloud sync captures runs, baseline, registry, and calculates hashes."""
        adapter = CloudStorageAdapter(target="local")
        mgr = CloudSyncManager(adapter)
        report = mgr.sync_all()

        self.assertGreater(report["total_files_synced"], 10)
        self.assertGreater(report["total_size_mb"], 0.1)
        self.assertEqual(report["backend"], "local_emulation")

        # Verify receipt written
        receipt_file = BASE_DIR / "BASELINE" / "cloud_sync_receipt.json"
        self.assertTrue(receipt_file.exists())

    def test_04_breadth_rule_adjuster(self):
        """Validates that sub-35% market breadth applies downward late-session penalties."""
        from breadth_rule_adjuster import BreadthRuleAdjuster
        adjuster = BreadthRuleAdjuster()
        sample_signals = {
            "live_nepse_index": 2578.50,
            "market_breadth_pct": 27.34,
            "top_candidates": [
                {"symbol": "AKPL", "sector": "HYDROPOWER", "latest_close": 420.0, "p50_5d": 435.0, "p10_5d": 410.0, "p90_5d": 450.0},
                {"symbol": "NICA", "sector": "COMMERCIAL_BANKS", "latest_close": 510.0, "p50_5d": 525.0, "p10_5d": 500.0, "p90_5d": 540.0}
            ]
        }
        updated, res = adjuster.apply_breadth_rule(sample_signals)
        self.assertTrue(res.breadth_rule_active)
        self.assertGreater(res.index_downward_adjustment_pts, 0.0)
        self.assertLess(res.adjusted_index_target, res.original_index_target)
        # Hydropower penalized more than commercial bank
        akpl_pen = updated["top_candidates"][0]["breadth_rule_penalty_pct"]
        nica_pen = updated["top_candidates"][1]["breadth_rule_penalty_pct"]
        self.assertGreater(akpl_pen, nica_pen)

    def test_05_pre_open_auction_engine(self):
        """Validates multilateral call-auction matching and IEP price discovery."""
        from pre_open_auction_engine import PreOpenAuctionMatchingEngine
        engine = PreOpenAuctionMatchingEngine()
        bids = [(505.0, 400), (502.0, 800), (500.0, 1500)]
        asks = [(498.0, 500), (500.0, 1200), (502.0, 1800)]
        res = engine.calculate_iep("NICA", bids, asks, reference_price=500.0)
        self.assertEqual(res.symbol, "NICA")
        self.assertGreater(res.matched_volume, 0)
        self.assertIn(res.price_discovery_status, ["BALANCED", "BUY_IMBALANCE", "SELL_IMBALANCE"])

    def test_06_nepse_mdp_adapter(self):
        """Validates that the MDP adapter provides SLA telemetry and transparent fallback."""
        from nepse_mdp_adapter import NepseMDPAdapter
        adapter = NepseMDPAdapter()
        rep = adapter.connect()
        self.assertIn(rep.active_feed_source, ["OFFICIAL_SOURCE_CODE_MDP", "NOTS_AUTHENTICATED_HTTP2_FALLBACK"])
        self.assertGreater(rep.sla_availability_pct, 95.0)

    def test_07_hawkes_broker_cascade(self):
        """Validates Hawkes self-exciting point process parameter fitting and cascade hazard score."""
        sys.path.insert(0, str(BASE_DIR / "scripts" / "02_modeling_and_calculations"))
        from hawkes_broker_cascade import HawkesBrokerCascadeEngine
        engine = HawkesBrokerCascadeEngine()
        sim_times = ["11:15:00", "11:15:45", "11:16:10", "11:16:22", "11:16:30"]
        sim_trades = [{"buyer_broker": "58", "time": t, "qty": 500} for t in sim_times]
        alert = engine.evaluate_broker_stream("CHCL", sim_trades)
        self.assertEqual(alert.symbol, "CHCL")
        self.assertGreater(alert.current_intensity, 0.0)
        self.assertIn(alert.regime, ["QUIET", "ACCUMULATING", "SUPERCRITICAL_CASCADE"])

    def test_08_vpin_market_toxicity(self):
        """Validates VPIN volume bucketing, toxicity probability, and Kyle's lambda."""
        sys.path.insert(0, str(BASE_DIR / "scripts" / "02_modeling_and_calculations"))
        from vpin_market_toxicity import VPINMarketToxicityEngine
        import pandas as pd
        engine = VPINMarketToxicityEngine(bucket_size=5_000, rolling_window_buckets=5)
        df_test = pd.DataFrame({
            "price": [500.0 - i * 0.2 for i in range(50)],
            "quantity": [500] * 50,
            "tradeTime": [f"12:{i:02d}:00" for i in range(50)]
        })
        rep = engine.calculate_vpin("NICA", df_test)
        self.assertEqual(rep.symbol, "NICA")
        self.assertGreater(rep.vpin_score, 0.0)
        self.assertLessEqual(rep.vpin_score, 1.0)

    def test_09_fifo_queue_simulator(self):
        """Validates FIFO queue rank and fill probability calculation."""
        sys.path.insert(0, str(BASE_DIR / "scripts" / "02_modeling_and_calculations"))
        from fifo_queue_simulator import FIFOQueuePositionSimulator
        sim = FIFOQueuePositionSimulator()
        p_fill, wait_sec, rec = sim.estimate_fill_probability(
            order_qty=500, shares_ahead=2000, daily_median_turnover_shares=30_000, session_remaining_seconds=3600.0
        )
        self.assertGreater(p_fill, 0.0)
        self.assertLessEqual(p_fill, 1.0)
        self.assertIn("MAINTAIN_PASSIVE", rec)

    def test_10_sample_uniqueness_labeler(self):
        """Validates sample uniqueness weights and concurrency reduction."""
        sys.path.insert(0, str(BASE_DIR / "scripts" / "02_modeling_and_calculations"))
        from sample_uniqueness_labeler import SampleUniquenessWeightingEngine
        import pandas as pd
        engine = SampleUniquenessWeightingEngine(default_horizon_days=5)
        base_dt = pd.to_datetime("2026-10-01")
        test_df = pd.DataFrame({
            "start_date": [base_dt + pd.Timedelta(days=i) for i in range(10)],
            "end_date": [base_dt + pd.Timedelta(days=i+5) for i in range(10)]
        })
        weights, summ = engine.compute_concurrency_and_uniqueness(test_df)
        self.assertEqual(len(weights), 10)
        self.assertGreater(summ.mean_uniqueness, 0.0)

    def test_11_cpcv_backtester(self):
        """Validates combinatorial purged cross validation and PBO calculation."""
        sys.path.insert(0, str(BASE_DIR / "scripts" / "02_modeling_and_calculations"))
        from cpcv_backtester import CombinatorialPurgedCrossValidation
        import numpy as np
        cpcv = CombinatorialPurgedCrossValidation(n_blocks=6, k_test_blocks=2)
        rets = np.random.normal(0.001, 0.01, 200)
        summ = cpcv.evaluate_strategy_returns(rets)
        self.assertEqual(summ.n_splits, 15)
        self.assertLessEqual(summ.probability_of_backtest_overfitting, 1.0)

    def test_12_stl_seasonality_filter(self):
        """Validates STL calendar seasonality trend isolation."""
        sys.path.insert(0, str(BASE_DIR / "scripts" / "01_etl_and_ingestion"))
        from stl_seasonality_filter import STLCalendarSeasonalityFilter
        import pandas as pd, numpy as np
        flt = STLCalendarSeasonalityFilter(seasonal_period_sessions=20)
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        prices = np.linspace(500, 550, 60) + np.random.normal(0, 1, 60)
        df_dec, summ = flt.decompose_series("NEPSE", dates, prices)
        self.assertEqual(summ.symbol, "NEPSE")
        self.assertGreater(summ.latest_deseasonalized_trend, 0.0)

    def test_13_isolation_forest_guard(self):
        """Validates Isolation Forest microstructure anomaly detection."""
        sys.path.insert(0, str(BASE_DIR / "scripts" / "02_modeling_and_calculations"))
        from isolation_forest_microstructure_guard import IsolationForestMicrostructureGuard
        guard = IsolationForestMicrostructureGuard(contamination=0.05, anomaly_threshold=0.65)
        test_universe = [
            {"symbol": f"S{i}", "top5_broker_ratio": 0.3, "turnover_ratio": 1.0, "upper_shadow_ratio": 0.1}
            for i in range(25)
        ]
        test_universe.append({"symbol": "MANIPULATED", "top5_broker_ratio": 0.95, "turnover_ratio": 9.0, "upper_shadow_ratio": 0.7})
        eval_res = guard.evaluate_universe(test_universe)
        flagged = [r for r in eval_res if r.is_anomaly]
        self.assertGreaterEqual(len(flagged), 1)
        self.assertEqual(flagged[0].symbol, "MANIPULATED")

    def test_14_data_quality_auditor(self):
        """Validates TSAuditor lakehouse pre-ingestion checks."""
        import importlib.util
        auditor_path = BASE_DIR / "scripts" / "01_etl_and_ingestion" / "00_audit_data_quality.py"
        spec = importlib.util.spec_from_file_location("tsauditor_mod", auditor_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        auditor = mod.TSAuditor()
        rep = auditor.run_full_audit()
        self.assertTrue(rep.all_checks_passed)
        self.assertGreater(rep.total_records, 700_000)

    def test_15_intraday_floor_bounce_bot(self):
        """Validates real-time intraday floor-bounce block absorption alerts."""
        from intraday_floor_bounce_bot import IntradayFloorBounceAlertBot
        bot = IntradayFloorBounceAlertBot()
        sim_trades = [
            {"buyer_broker": "58", "quantity": 25_000, "price": 270.0},
            {"buyer_broker": "45", "quantity": 10_000, "price": 270.0}
        ]
        alert = bot.evaluate_live_tape(
            symbol="UPPER", current_price=270.0, reference_price=300.0,
            recent_trades=sim_trades, total_ask_queue_shares=50_000
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.symbol, "UPPER")
        self.assertGreaterEqual(alert.absorbed_volume_shares, 25_000)

    def test_16_demat_tax_rebalancing_blotter(self):
        """Validates Demat FIFO lot tax calculations and CGT brackets."""
        from demat_tax_rebalancing_blotter import DematTaxRebalancingEngine, DematLot
        engine = DematTaxRebalancingEngine(investor_type="INDIVIDUAL")
        holdings = {"NABIL": [DematLot("L1", "NABIL", 100, 400.0, "2025-01-01", True)]}
        targets = {"NABIL": 0.0}
        prices = {"NABIL": 500.0}
        rep = engine.generate_rebalancing_blotter(holdings, targets, prices, as_of_date="2026-10-07")
        self.assertEqual(len(rep.tickets), 1)
        self.assertEqual(rep.tickets[0]["cgt_bracket_applied"], "LONG_TERM_5%")
        self.assertEqual(rep.tickets[0]["cgt_liability_npr"], 500.0) # (500-400)*100 * 0.05 = 500

    def test_17_index_circuit_breaker_fsm(self):
        """Validates index-wide circuit breaker state transitions and automatic order cancellation."""
        from index_circuit_breaker_fsm import IndexCircuitBreakerFSM, MarketTradingState
        fsm = IndexCircuitBreakerFSM(baseline_previous_close=2500.0)
        trans = fsm.evaluate_index_tick(current_index=2395.0, current_time_str="11:30:00", active_working_orders=[{"tkt": 1}])
        self.assertEqual(trans.current_state, MarketTradingState.HALT_LEVEL_1_SUSPENDED.value)
        self.assertEqual(trans.orders_auto_cancelled_count, 1)


if __name__ == "__main__":
    unittest.main()
