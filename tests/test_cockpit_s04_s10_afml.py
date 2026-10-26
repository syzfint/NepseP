"""
tests/test_cockpit_s04_s10_afml.py

Unit test suite verifying:
1. Cont-Stoikov Level-2 Order Flow Imbalance (OFI & NOFI)
2. 10-Level Order Book Reconstruction & Queue Depletion Signals
3. Continuous HMAC-SHA256 Merkle Provenance Ledger & Tamper Proofing
4. AFML Deflated Sharpe Ratio (DSR) & MinTRL
5. Combinatorially Symmetric Cross-Validation (CSCV) & PBO
6. White's Reality Check & Hansen SPA
"""

import sys
import os
import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scripts" / "02_modeling_and_calculations"))
sys.path.insert(0, str(BASE_DIR / "scripts" / "03_data_access_and_storage"))
sys.path.insert(0, str(BASE_DIR / "scripts" / "04_backtesting" / "sovereign_alpha_miner"))

from ofi_depth_calculator import ContStoikovOFICalculator
from market_depth_reconstructor import generate_synthetic_or_real_l2_depth
from merkle_provenance_engine import MerkleProvenanceChain
from deflated_sharpe import deflated_sharpe_ratio, compute_sample_moments
from pbo_evaluator import compute_pbo_from_matrix, generate_cscv_splits
from reality_check import whites_reality_check_and_spa


def test_cont_stoikov_ofi_calculation():
    calc = ContStoikovOFICalculator(depth_levels=5)
    # Initial quote
    calc.update_order_book(
        symbol="NICA",
        bids=[(480.0, 1000), (479.0, 2000)],
        asks=[(481.0, 1000), (482.0, 2000)]
    )
    # Second tick: Price rises at bid, volume added -> strong positive OFI
    res = calc.update_order_book(
        symbol="NICA",
        bids=[(480.5, 2500), (480.0, 3000)],
        asks=[(481.5, 800), (482.0, 1500)]
    )
    assert res is not None
    assert "ofi" in res
    assert "nofi" in res
    assert -1.0 <= res["nofi"] <= 1.0


def test_market_depth_reconstruction():
    book = generate_synthetic_or_real_l2_depth(symbol="NICA", ltp=482.0, num_levels=10)
    assert book["symbol"] == "NICA"
    assert len(book["bids"]) == 10
    assert len(book["asks"]) == 10
    assert book["best_bid"] < book["best_ask"]
    assert "depth_imbalance_ratio" in book
    assert "microprice" in book


def test_merkle_provenance_chain_and_tamper_detection(tmp_path):
    chain_file = tmp_path / "test_merkle.chain"
    chain = MerkleProvenanceChain(chain_path=chain_file)

    b1 = chain.append_block("INITIAL_SNAPSHOT", {"status": "OPEN", "tick": 1})
    b2 = chain.append_block("INTRA_TRADE", {"symbol": "NICA", "qty": 100})
    b3 = chain.append_block("EOD_SEAL", {"total_turnover": 4000000})

    valid, count, err = chain.verify_chain_integrity()
    assert valid is True
    assert count == 3
    assert err is None

    # Tamper test: Corrupt middle line in chain
    lines = chain_file.read_text(encoding="utf-8").strip().split("\n")
    corrupt_block = json.loads(lines[1])
    corrupt_block["payload_hash"] = "bad0" * 16  # Tampered payload hash
    lines[1] = json.dumps(corrupt_block)
    chain_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tampered_chain = MerkleProvenanceChain(chain_path=chain_file)
    valid_tampered, count_t, err_t = tampered_chain.verify_chain_integrity()
    assert valid_tampered is False
    assert "Tampered hash" in err_t or "Broken chain" in err_t


def test_afml_deflated_sharpe_ratio():
    random.seed(42)
    # Generate 252 daily returns with positive Sharpe
    returns = [0.001 + random.gauss(0, 0.015) for _ in range(252)]
    
    # 1 trial: should have positive DSR
    res_1 = deflated_sharpe_ratio(returns=returns, num_trials=1)
    assert res_1["sharpe_annualized"] > 0
    assert 0.0 <= res_1["deflated_sharpe_ratio"] <= 1.0

    # 100 trials: selection bias lowers DSR
    res_100 = deflated_sharpe_ratio(returns=returns, num_trials=100)
    assert res_100["deflated_sharpe_ratio"] <= res_1["deflated_sharpe_ratio"]
    assert res_100["sr_benchmark_hurdle"] > 0


def test_afml_pbo_evaluator():
    random.seed(42)
    # 100 time periods, 10 strategy candidates
    returns_matrix = [
        [random.gauss(0.0005, 0.01) for _ in range(10)]
        for _ in range(100)
    ]
    pbo_res = compute_pbo_from_matrix(returns_matrix, num_blocks=8, max_combos=50)
    assert "pbo" in pbo_res
    assert 0.0 <= pbo_res["pbo"] <= 1.0
    assert "verdict" in pbo_res


def test_afml_whites_reality_check():
    random.seed(42)
    # Excess returns over benchmark
    excess_matrix = [
        [random.gauss(0.0002, 0.008) for _ in range(5)]
        for _ in range(100)
    ]
    spa_res = whites_reality_check_and_spa(excess_matrix, num_bootstrap=50)
    assert "white_rc_pvalue" in spa_res
    assert 0.0 <= spa_res["white_rc_pvalue"] <= 1.0
    assert "hansen_spa_pvalue" in spa_res
    assert 0.0 <= spa_res["hansen_spa_pvalue"] <= 1.0
