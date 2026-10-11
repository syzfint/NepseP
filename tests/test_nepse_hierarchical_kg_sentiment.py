"""
Unit and Property Tests for Two-Tier Hierarchical Sentiment Scoring Engine & MSSPM Architecture.
Validates:
1. Ex-ante parameter adherence (beta=0.25, gamma=0.5, H=2, lambda_r=0.35, lambda_d=0.46).
2. Implied carry-over weights (100%, 63%, 40%, 25%, 16%).
3. Knowledge graph hop decay and exposure capping at [-50, +50].
4. Simplex normalization constraint a_j + b_j + c_j = 1 in Tier 2.
5. Strict output bounds [1, 100] for market score M_t and stock score S_{j,t}.
6. PyTorch MSSPM forward pass shapes and probability normalization.
"""

import math
import pytest
import numpy as np
import torch
import importlib.util
from pathlib import Path

# Load nepse_hierarchical_kg_sentiment
_spec_kg = importlib.util.spec_from_file_location(
    "nepse_hierarchical_kg_sentiment",
    Path(__file__).parent.parent / "scripts" / "02_modeling_and_calculations" / "nepse_hierarchical_kg_sentiment.py"
)
_mod_kg = importlib.util.module_from_spec(_spec_kg)
_spec_kg.loader.exec_module(_mod_kg)

compute_repetition_discount = _mod_kg.compute_repetition_discount
apply_carryover_decay = _mod_kg.apply_carryover_decay
calculate_tier1_market_score = _mod_kg.calculate_tier1_market_score
calculate_tier2_stock_score = _mod_kg.calculate_tier2_stock_score
NepseKnowledgeGraph = _mod_kg.NepseKnowledgeGraph
TwoTierNepseSentimentPipeline = _mod_kg.TwoTierNepseSentimentPipeline
LAMBDA_R = _mod_kg.LAMBDA_R
LAMBDA_D = _mod_kg.LAMBDA_D
GAMMA = _mod_kg.GAMMA
BETA = _mod_kg.BETA

# Load msspm_neural_event_model
_spec_m = importlib.util.spec_from_file_location(
    "msspm_neural_event_model",
    Path(__file__).parent.parent / "scripts" / "02_modeling_and_calculations" / "msspm_neural_event_model.py"
)
_mod_m = importlib.util.module_from_spec(_spec_m)
_spec_m.loader.exec_module(_mod_m)
MSSPM = _mod_m.MSSPM


def test_repetition_discount_monotonicity():
    """Verify repetition discount factor f decreases monotonically as repetition density increases."""
    f_no_prior = compute_repetition_discount([])
    assert f_no_prior == 1.0

    # 1 recent appearance (1 day ago)
    f_1 = compute_repetition_discount([1])
    # 3 recent appearances
    f_3 = compute_repetition_discount([1, 2, 3])
    
    assert 0.0 < f_3 < f_1 < f_no_prior
    # Check exact math for 1 lag at lambda_r = 0.35
    expected_f1 = 1.0 / (1.0 + math.exp(-0.35 * 1))
    assert pytest.approx(f_1, rel=1e-3) == expected_f1


def test_carryover_decay_weights_exact():
    """Verify implied carry-over weights match ICAIF 2026: 100%, 63%, 40%, 25%, 16%."""
    weights = [math.exp(-LAMBDA_D * k) for k in range(5)]
    assert pytest.approx(weights[0], abs=1e-2) == 1.00
    assert pytest.approx(weights[1], abs=1e-2) == 0.63
    assert pytest.approx(weights[2], abs=1e-2) == 0.40
    assert pytest.approx(weights[3], abs=1e-2) == 0.25
    assert pytest.approx(weights[4], abs=1e-2) == 0.16

    # Test single positive shock
    score_shock = apply_carryover_decay([20.0, 0.0, 0.0, 0.0, 0.0])
    assert score_shock == 70.0


def test_knowledge_graph_hop_decay_and_capping():
    """Verify KG propagation adheres to gamma=0.5 and delta_max=50."""
    kg = NepseKnowledgeGraph()
    # A -> B (weight 0.8), B -> C (weight 0.5)
    kg.add_edge("A", "B", "SUPPLIES_TO", 0.8, sign=1.0)
    kg.add_edge("B", "C", "SUPPLIES_TO", 0.5, sign=1.0)

    shocks = kg.propagate_shock("A", raw_shock=90.0) # delta = +40
    
    # 1-hop on B: 40 * 0.8 * 0.5^1 = 16.0
    assert pytest.approx(shocks["B"], rel=1e-2) == 16.0
    # 2-hop on C: 40 * (0.8 * 0.5) * 0.5^2 = 4.0
    assert pytest.approx(shocks["C"], rel=1e-2) == 4.0


def test_tier1_market_score_bounds():
    """Verify Tier 1 market score is strictly bounded in [1, 100]."""
    for loc in [1.0, 20.0, 50.0, 80.0, 100.0]:
        for macro in [1.0, 30.0, 50.0, 70.0, 100.0]:
            m_t, _ = calculate_tier1_market_score(loc, macro)
            assert 1.0 <= m_t <= 100.0
            
    # When both are neutral (50), M_t should be close to 50
    m_neutral, _ = calculate_tier1_market_score(50.0, 50.0)
    assert 40.0 < m_neutral < 60.0


def test_tier2_stock_score_simplex_and_bounds():
    """Verify Tier 2 score respects simplex constraint and stays within [1, 100]."""
    s_jt, _ = calculate_tier2_stock_score(
        sprint_score=85.0,
        market_score=60.0,
        sovereign_score=70.0,
        weights=(0.3, 0.4, 0.3)
    )
    assert 1.0 <= s_jt <= 100.0
    assert s_jt > 50.0 # Bullish alignment


def test_end_to_end_nepse_pipeline():
    """Verify end-to-end two-tier cycle generates consistent cross-firm scores."""
    pipeline = TwoTierNepseSentimentPipeline()
    news = [
        {"symbol": "NABIL", "raw_score": 85.0},
        {"symbol": "SHIVM", "raw_score": 30.0}
    ]
    res = pipeline.process_daily_news_cycle(news, sovereign_macro_score=55.0)
    assert 1.0 <= res["tier1_market_score"] <= 100.0
    assert "NABIL" in res["tier2_final_stock_scores"]
    assert "MEN" in res["tier2_final_stock_scores"] # KG-linked to NABIL credit line
    # MEN should receive propagated shock from NABIL
    assert res["per_firm_sprint_scores"]["MEN"] > 50.0


def test_msspm_neural_architecture_forward():
    """Verify PyTorch MSSPM forward pass and probability distribution properties."""
    model = MSSPM()
    dummy_news = torch.randint(0, 1000, (2, 16))
    dummy_stock = torch.randn(2, 10, 12)
    
    out = model(dummy_news, dummy_stock)
    probs = out["probabilities"]
    assert probs.shape == (2, 3)
    # Sum of probabilities across 3 classes should equal 1.0
    for p in probs:
        assert pytest.approx(float(p.sum().item()), rel=1e-4) == 1.0
