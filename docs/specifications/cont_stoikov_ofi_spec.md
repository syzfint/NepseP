# Cont-Stoikov OFI Technical Specification
**Module:** `scripts/02_modeling_and_calculations/ofi_depth_calculator.py`
**Date:** 2026-10-21

## 1. Multi-Level Weighting Function
To account for queue decay across depth levels $i \in [1, 5]$:
$$w_i = e^{-\lambda (i - 1)}, \quad \lambda = 0.40$$

Level 1 receives 100% weight, Level 2 receives 67.0%, Level 3 receives 44.9%, Level 4 receives 30.1%, and Level 5 receives 20.2%.
