#!/usr/bin/env python3
"""
tests/test_structural_asymmetry.py

Unit test suite for Structural Asymmetry & Regulatory Calendar Miner.
Verifies:
1. Promoter 3-year lock-in window detection.
2. Floorsheet broker concentration & HHI calculations.
3. Gold mine cornering vs fatal trap classification.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import importlib

miner_mod = importlib.import_module("scripts.02_modeling_and_calculations.structural_asymmetry_miner")
StructuralAsymmetryMiner = miner_mod.StructuralAsymmetryMiner


class TestStructuralAsymmetry:

    def test_01_promoter_lockin_mining(self):
        miner = StructuralAsymmetryMiner(as_of_date="2026-10-07")
        df_lockin = miner.mine_promoter_lockin_asymmetries()
        assert not df_lockin.empty
        assert "regime" in df_lockin.columns
        assert "days_to_expiry" in df_lockin.columns

        # Verify HATHY and MANDU are flagged in active window
        hathy = df_lockin[df_lockin["symbol"] == "HATHY"]
        assert not hathy.empty
        assert hathy.iloc[0]["days_to_expiry"] == 4
        assert hathy.iloc[0]["regime"] == "ACTIVE_FREEZE_SHOCK_WINDOW"

    def test_02_broker_floorsheet_concentration(self):
        miner = StructuralAsymmetryMiner(as_of_date="2026-10-07")
        df_conc = miner.mine_broker_floorsheet_concentration()
        assert not df_conc.empty
        assert "top1_share_pct" in df_conc.columns
        assert "buyer_hhi" in df_conc.columns
        assert "cartel_status" in df_conc.columns

        # Verify LLBS has high concentration (> 50% top broker)
        llbs = df_conc[df_conc["symbol"] == "LLBS"]
        assert not llbs.empty
        assert llbs.iloc[0]["top1_share_pct"] > 50.0

    def test_03_full_stress_test_classification(self):
        miner = StructuralAsymmetryMiner(as_of_date="2026-10-07")
        res = miner.run_full_structural_stress_test()
        assert res["total_lockin_tracked"] > 300
        assert res["active_freeze_window_count"] > 0
        assert len(res["gold_mines_low_float"]) > 0
        assert len(res["fatal_traps_supply_wall"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
