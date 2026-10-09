#!/usr/bin/env python3
"""
tests/test_high_yield_povs.py

High-Yield Structural & Algorithmic POVs Test Suite
===================================================
Verifies the complete implementation of the 6 NEPSE Structural & Algorithmic POVs:
1. 10-Kitta Mandatory Allotment: Book-Building (40% QIB 6-month lock-in) vs Par-Value dual track.
2. Monsoon Hydro Risk: 90-day fiscal disbursement lag and PPA contractual terms (Take-or-Pay vs Take-and-Pay).
3. 3-Year Promoter Lock-in Expiry: BFI Pledged Share Ratio haircut scaling.
4. Pre-Open Spoof Detector: 10:44:30 AM Cutoff Buffer and late packet filter.
5. Dynamic POV Engine: Broker TMS 5,000 ms Order State Acknowledgment Timeout guard.
6. Syndicate-Cluster VPIN: Cartel broker cluster volume aggregation (Brokers 58, 45, 49).
"""

import sys
import importlib
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

ten_kitta_mod = importlib.import_module("scripts.02_modeling_and_calculations.ten_kitta_allotment_sink")
monsoon_mod = importlib.import_module("scripts.02_modeling_and_calculations.monsoon_hydro_reconstruction_hedge")
spoof_mod = importlib.import_module("scripts.00_control.pre_open_spoof_detector")
pov_mod = importlib.import_module("scripts.00_control.dynamic_pov_engine")
vpin_mod = importlib.import_module("scripts.02_modeling_and_calculations.vpin_market_toxicity")
pit_mod = importlib.import_module("scripts.01_etl_and_ingestion.nfrs_point_in_time_extractor")


class TestHighYieldPOVs:

    def test_01_ten_kitta_allotment_sink_dual_track(self):
        """Asserts 10-kitta retail absorption, Book-Building QIB lock-in, and phase transitions."""
        sink = ten_kitta_mod.TenKittaAllotmentSink(retail_dump_propensity=0.70)

        # 1. Par-Value Float Profile (e.g. 1M allottees, 10M shares retail float)
        prof_par = sink.compute_retail_float_profile("TEST_PAR", total_ipo_shares=20000000, allottee_count=1000000, issue_type="PAR_VALUE")
        assert prof_par["issue_type"] == "PAR_VALUE"
        assert prof_par["retail_allotted_shares"] == 10000000
        assert prof_par["estimated_dump_volume_target"] == 7000000
        assert prof_par["qib_shares_locked"] == 0
        assert prof_par["retail_flip_margin_threshold_pct"] == 100.0

        # 2. Book-Building Float Profile (40% QIB tranche locked for 180 days, narrower retail margins)
        prof_bb = sink.compute_retail_float_profile(
            "SARBTM",
            total_ipo_shares=10000000,
            allottee_count=600000,
            issue_type="BOOK_BUILDING",
            cutoff_price=430.0,
            qib_tranche_pct=40.0,
            qib_lockin_days=180
        )
        assert prof_bb["issue_type"] == "BOOK_BUILDING"
        assert prof_bb["qib_shares_locked"] == 4000000
        assert prof_bb["qib_lockin_days"] == 180
        assert prof_bb["retail_flip_margin_threshold_pct"] == 20.0
        assert prof_bb["effective_issue_price_npr"] == 430.0

        # 3. Phase 1: Upper circuit lockup
        hist_p1 = [{"day": 1, "close": 110.0, "volume": 5000, "is_upper_circuit": True, "broker_top_buyer_pct": 10.0}]
        res_p1 = sink.evaluate_post_listing_phase("TEST_PAR", 1000000, hist_p1)
        assert res_p1["current_phase"] == "PHASE_1_UPPER_CIRCUIT_LOCKUP"
        assert res_p1["recommended_action"] == "HOLD_WAIT_FOR_LIQUIDITY"

        # 4. Phase 2: Circuit broken, early retail panic wave
        hist_p2 = [
            {"day": 1, "close": 110.0, "volume": 5000, "is_upper_circuit": True, "broker_top_buyer_pct": 10.0},
            {"day": 2, "close": 105.0, "volume": 1000000, "is_upper_circuit": False, "broker_top_buyer_pct": 15.0}
        ]
        res_p2 = sink.evaluate_post_listing_phase("TEST_PAR", 1000000, hist_p2)
        assert res_p2["current_phase"] == "PHASE_2_RETAIL_DUMPING_CASCADE"
        assert res_p2["recommended_action"] == "AVOID_RETAIL_PANIC_WAVE"

        # 5. Phase 3: Institutional absorption inflection point (>70% retail target absorbed, top buyer > 40%)
        hist_p3 = [
            {"day": 1, "close": 110.0, "volume": 5000, "is_upper_circuit": True, "broker_top_buyer_pct": 10.0},
            {"day": 2, "close": 105.0, "volume": 3500000, "is_upper_circuit": False, "broker_top_buyer_pct": 20.0},
            {"day": 3, "close": 102.0, "volume": 4000000, "is_upper_circuit": False, "broker_top_buyer_pct": 48.0}
        ]
        res_p3 = sink.evaluate_post_listing_phase("TEST_PAR", 1000000, hist_p3)
        assert res_p3["current_phase"] == "PHASE_3_INSTITUTIONAL_ABSORPTION_INFLECTION"
        assert res_p3["recommended_action"] == "STRONG_BUY_INSTITUTIONAL_ENTRY"

        # 6. Phase 5: Book-Building QIB Lock-in Expiration Shock (> 180 days)
        res_qib_shock = sink.evaluate_post_listing_phase(
            "SARBTM",
            allottee_count=600000,
            daily_trading_history=hist_p3,
            issue_type="BOOK_BUILDING",
            cutoff_price=430.0,
            days_since_listing=185,
            total_ipo_shares=10000000
        )
        assert res_qib_shock["qib_lockin_expired"] is True
        assert res_qib_shock["current_phase"] == "PHASE_5_QIB_LOCKIN_EXPIRY_SUPPLY_SHOCK"
        assert res_qib_shock["recommended_action"] == "DEFENSIVE_HOLD_OR_REDUCE_QIB_SUPPLY_WALL"
        assert res_qib_shock["qib_supply_shock_shares"] == 4000000

    def test_02_monsoon_hydro_reconstruction_hedge_lag_and_ppa(self):
        """Asserts monsoon season detection, 90-day fiscal lag, and contractual PPA haircuts."""
        hedge = monsoon_mod.MonsoonHydroReconstructionHedge(fiscal_disbursement_lag_days=90)

        # Seasonality check
        assert hedge.is_monsoon_season("2026-07-20") is True   # July is peak monsoon
        assert hedge.is_monsoon_season("2026-01-15") is False  # January is dry winter

        # 1. Rebalance under severe flood alert (0.85) in July with 90-day fiscal lag
        reb = hedge.generate_sectoral_rebalance(
            as_of_date="2026-07-25",
            climate_severity_index=0.85,
            hydro_allocation_weight=0.30,
            mfg_allocation_weight=0.10,
            flood_shock_date="2026-07-01"
        )
        assert reb["in_monsoon_window"] is True
        assert reb["flood_shock_active"] is True
        assert reb["days_since_flood_shock"] == 24
        assert reb["reconstruction_lag_active"] is True
        assert reb["reconstruction_phase"] == "DAMAGE_ASSESSMENT_PHASE"
        assert reb["stance"] == "SECTORAL_HEDGE_REBALANCE_ACTIVE"
        assert reb["adjusted_weights"]["ror_hydro"] == 0.15
        assert reb["adjusted_weights"]["reconstruction_mfg"] == 0.25

        # 2. Check PPA Contractual terms
        upper_profile = hedge.assess_hydro_contractual_risk("UPPER")
        assert upper_profile["ppa_type"] == "TAKE_OR_PAY"
        assert upper_profile["storage_type"] == "PROR"

        api_profile = hedge.assess_hydro_contractual_risk("API")
        assert api_profile["ppa_type"] == "TAKE_AND_PAY"
        assert api_profile["grid_force_majeure_exposure"] == "HIGH"
        assert api_profile["recommended_haircut"] == 0.65  # Higher haircut due to zero grid revenue protection

    def test_03_pre_open_spoof_detector_with_cutoff_buffer(self):
        """Asserts detection of synthetic pre-open tape painting and 10:44:30 AM cutoff buffer."""
        detector = spoof_mod.PreOpenSpoofDetector(cutoff_buffer_seconds=30, auction_cutoff_time="10:44:30")

        # 1. Packet filtering: packets past 10:44:30 AM are dropped
        raw_events = [
            {"timestamp": "10:40:00", "bid": 500},
            {"timestamp": "10:44:25", "bid": 502},
            {"timestamp": "10:44:35", "bid": 502},  # Dropped!
            {"timestamp": "10:44:59", "bid": 480},  # Dropped!
        ]
        valid, dropped = detector.filter_late_order_events(raw_events)
        assert len(valid) == 2
        assert dropped == 2

        # 2. Synthetic Spoof: 50% bids pulled in last 60s
        res_spoof = detector.evaluate_pre_open_order_flow(
            symbol="TEST_SCRIP",
            prev_close=500.0,
            indicative_match_price=524.0,  # +4.8% gap
            total_entered_bid_shares=30000,
            canceled_bid_shares_final_60s=15000,  # 50% canceled
            final_executable_matched_shares=150,  # matched volume is tiny
            unmatched_bid_shares=500,
            unmatched_ask_shares=18000,
            order_events=raw_events,
            as_of_time="10:44:30"
        )
        assert res_spoof["verdict"] == "SYNTHETIC_PRE_OPEN_SPOOF"
        assert res_spoof["recommended_action"] == "REJECT_GAP_ENTRY_FADE_OPEN"
        assert res_spoof["cancellation_rate_pct"] == 50.0
        assert res_spoof["pre_open_cutoff_enforced"] is True
        assert res_spoof["late_packets_filtered_count"] == 2

        # 3. Genuine Gap: Minimal cancellations and deep executable volume
        res_real = detector.evaluate_pre_open_order_flow(
            symbol="NABIL",
            prev_close=615.0,
            indicative_match_price=632.0,  # +2.76% gap
            total_entered_bid_shares=40000,
            canceled_bid_shares_final_60s=800,    # 2% canceled
            final_executable_matched_shares=7000, # 7,000 shares matched
            unmatched_bid_shares=12000,
            unmatched_ask_shares=1500,
            as_of_time="10:44:30"
        )
        assert res_real["verdict"] == "GENUINE_INSTITUTIONAL_GAP"
        assert res_real["recommended_action"] == "CONFIRM_LONG_MOMENTUM_BREAKOUT"

    def test_04_dynamic_pov_volume_tracking(self):
        """Asserts Dynamic POV engine sizes slices to volume and respects Almgren-Chriss depth caps."""
        engine = pov_mod.DynamicPOVEngine(target_participation_rate=0.08, max_book_depth_cap=0.15)

        # 1. Morning surge: High volume window -> larger slice
        s1 = engine.compute_dynamic_slice(
            symbol="NABIL",
            side="BUY",
            remaining_target_shares=3000,
            limit_price=618.0,
            session_time="11:15",
            observed_market_volume_window=6000,
            prevailing_book_depth_shares=4000,
            live_vpin=0.35
        )
        assert s1["status"] == "STAGED_FOR_EXECUTION"
        assert s1["slice_quantity"] == 480
        assert s1["is_throttled_midday"] is False
        assert s1["within_almgren_chriss_bound"] is True

        # 2. Midday slump at 1:10 PM: Thin volume -> throttled slice
        s2 = engine.compute_dynamic_slice(
            symbol="NABIL",
            side="BUY",
            remaining_target_shares=2500,
            limit_price=618.0,
            session_time="13:10",
            observed_market_volume_window=400,
            prevailing_book_depth_shares=1000,
            live_vpin=0.30
        )
        assert s2["status"] == "STAGED_FOR_EXECUTION"
        assert s2["slice_quantity"] == 32
        assert s2["is_throttled_midday"] is True

    def test_05_vpin_adverse_selection_defense(self):
        """Asserts that predatory institutional toxic sweeps (VPIN > 0.70) pause execution."""
        engine = pov_mod.DynamicPOVEngine()

        s_toxic = engine.compute_dynamic_slice(
            symbol="NABIL",
            side="BUY",
            remaining_target_shares=2000,
            limit_price=618.0,
            session_time="14:30",
            observed_market_volume_window=8000,
            prevailing_book_depth_shares=3000,
            live_vpin=0.76  # Toxic insider sweep
        )
        assert s_toxic["status"] == "PAUSED_TOXIC_VPIN_FLOW"
        assert s_toxic["slice_quantity"] == 0
        assert s_toxic["remaining_shares"] == 2000

    def test_06_dynamic_pov_tms_ack_timeout_guard(self):
        """Asserts that unacknowledged order slices exceeding 5,000 ms freeze further execution."""
        engine = pov_mod.DynamicPOVEngine(order_ack_timeout_ms=5000)

        # Record slice submission at t = 1,000 ms
        engine.record_slice_submission(
            slice_id="SLICE_001",
            symbol="NICA",
            quantity=500,
            price=450.0,
            submitted_at_ms=1000
        )

        # Query slice at t = 3,000 ms (elapsed 2,000 ms < 5,000 ms timeout) -> Not frozen
        s_ok = engine.compute_dynamic_slice(
            symbol="NICA",
            side="BUY",
            remaining_target_shares=1500,
            limit_price=450.0,
            session_time="11:30",
            observed_market_volume_window=5000,
            prevailing_book_depth_shares=4000,
            current_time_ms=3000
        )
        assert s_ok["status"] == "STAGED_FOR_EXECUTION"

        # Query slice at t = 6,500 ms (elapsed 5,500 ms > 5,000 ms timeout) -> FROZEN!
        s_frozen = engine.compute_dynamic_slice(
            symbol="NICA",
            side="BUY",
            remaining_target_shares=1500,
            limit_price=450.0,
            session_time="11:30",
            observed_market_volume_window=5000,
            prevailing_book_depth_shares=4000,
            current_time_ms=6500
        )
        assert s_frozen["status"] == "FROZEN_UNACKED_TMS_SLICE"
        assert s_frozen["slice_quantity"] == 0
        assert s_frozen["reconciliation_required"] is True
        assert s_frozen["reconciliation_query"]["slice_id"] == "SLICE_001"

        # Receive ACK at t = 6,600 ms -> Unfreezes next cycle
        ack_res = engine.record_slice_acknowledgment("SLICE_001", "MATCHED", ack_at_ms=6600)
        assert ack_res is True

        s_resumed = engine.compute_dynamic_slice(
            symbol="NICA",
            side="BUY",
            remaining_target_shares=1000,
            limit_price=450.0,
            session_time="11:31",
            observed_market_volume_window=5000,
            prevailing_book_depth_shares=4000,
            current_time_ms=6700
        )
        assert s_resumed["status"] == "STAGED_FOR_EXECUTION"

    def test_07_syndicate_cluster_vpin_calculation(self):
        """Asserts aggregation of trading across broker syndicate clusters (Brokers 58, 45, 49)."""
        vpin_engine = vpin_mod.VPINMarketToxicityEngine()

        # Simulated floor sheet with coordinated aggressive buying by Syndicate Alpha (58, 45, 49)
        sample_floorsheet = [
            {"buyer_broker": 58, "seller_broker": 14, "quantity": 10000},
            {"buyer_broker": 45, "seller_broker": 21, "quantity": 8000},
            {"buyer_broker": 49, "seller_broker": 32, "quantity": 12000},
            {"buyer_broker": 10, "seller_broker": 58, "quantity": 1000}, # Only 1k sold by cluster
            {"buyer_broker": 22, "seller_broker": 33, "quantity": 5000}, # Independent trade
        ]

        syn_report = vpin_engine.calculate_syndicate_cluster_vpin(
            symbol="HDL",
            floorsheet_trades=sample_floorsheet,
            cluster_name="SYNDICATE_ALPHA_58_45_49"
        )
        assert syn_report["cluster_buy_volume"] == 30000.0
        assert syn_report["cluster_sell_volume"] == 1000.0
        assert syn_report["cluster_total_volume"] == 31000.0
        # Cluster imbalance = 29,000 / 31,000 = 0.9355
        assert syn_report["syndicate_cluster_vpin"] > 0.90
        assert syn_report["is_toxic_cluster_sweep"] is True
        assert syn_report["syndicate_regime"] == "COORDINATED_SYNDICATE_ACCUMULATION_SWEEP"

        # Verify Dynamic POV Engine halts execution when Syndicate Cluster VPIN is toxic
        pov_engine = pov_mod.DynamicPOVEngine()
        s_halt = pov_engine.compute_dynamic_slice(
            symbol="HDL",
            side="BUY",
            remaining_target_shares=5000,
            limit_price=1800.0,
            session_time="11:45",
            observed_market_volume_window=40000,
            prevailing_book_depth_shares=10000,
            live_vpin=0.35,  # Benign single stock VPIN
            syndicate_cluster_vpin=syn_report["syndicate_cluster_vpin"]  # Toxic syndicate cluster VPIN!
        )
        assert s_halt["status"] == "PAUSED_TOXIC_VPIN_FLOW"
        assert s_halt["slice_quantity"] == 0

    def test_08_promoter_lockin_bfi_pledged_scaling(self):
        """Asserts that BFI pledged promoter shares are scaled down from secondary supply dump."""
        dilution_engine = pit_mod.FreeFloatDilutionEngine()

        # Company with 10M ordinary shares, 30M promoter shares
        # If 60% of promoter shares are pledged to BFIs, only 40% (12M) hit secondary market
        shock = dilution_engine.evaluate_dilution_shock(
            symbol="TEST_PLEDGE",
            as_of_date="2026-10-07",
            current_close=400.0,
            ordinary_shares=10000000.0,
            promoter_shares=30000000.0,
            quarterly_net_profit=100000000.0,
            promoter_pledged_ratio=0.60
        )
        assert shock["total_unlocked_promoter_shares"] == 30000000.0
        assert shock["promoter_pledged_ratio"] == 0.60
        assert shock["pledged_promoter_shares"] == 18000000.0
        assert shock["tradable_dump_shares"] == 12000000.0
        # Post free float is 10M ordinary + 12M tradable dump = 22M shares
        assert shock["post_free_float_shares"] == 22000000.0
        # Dilution factor is 22M / 10M = 2.2x (not 4.0x!)
        assert shock["dilution_expansion_factor"] == 2.2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
