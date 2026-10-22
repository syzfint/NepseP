import pytest
import numpy as np
from scipy import stats

def test_dsr_zero_variance_benchmark():
    sr_obs = 1.8
    sr_bench = 1.0
    t_years = 3.0
    z_stat = (sr_obs - sr_bench) * np.sqrt(t_years)
    p_val = stats.norm.cdf(z_stat)
    assert p_val > 0.90

def test_mintr_length_positive():
    sr = 1.2
    sr_star = 0.5
    min_trl = 1.0 + (1.0 / (sr - sr_star)**2)
    assert min_trl > 1.0
