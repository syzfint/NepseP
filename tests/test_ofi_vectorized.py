import pytest
import numpy as np

def test_ofi_decay_weights():
    decay = 0.40
    weights = np.exp(-decay * np.arange(5))
    assert np.isclose(weights[0], 1.0)
    assert weights[1] < weights[0]
    assert np.all(weights > 0)

def test_ofi_imbalance_bounds():
    q_b = np.array([100, 200, 300, 400, 500])
    q_a = np.array([50, 100, 150, 200, 250])
    diff = q_b - q_a
    denom = q_b + q_a
    ratio = np.sum(diff) / np.sum(denom)
    assert -1.0 <= ratio <= 1.0
