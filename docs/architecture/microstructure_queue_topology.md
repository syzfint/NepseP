# Microstructure Queue Topology Specification
**Author:** ApexMarketEngine Quantitative Research
**Date:** 2026-10-21 | NEPSE Market Dynamics

## 1. Discrete Queue Dynamics
In NEPSE's automated trading system (ATS), limit orders are prioritized strictly by Price-Time Priority (FIFO). Because minimum tick sizes vary with price thresholds (NPR 0.10 below 500, NPR 1.00 above 500), queue depth concentration forms distinctive clustering at psychological round numbers.

## 2. Order Book Imbalance (OFI) Estimation
The instantaneous queue state is tracked across $K=5$ levels:
- Bid queue depth $Q_b(t)$
- Ask queue depth $Q_a(t)$
- Normalized volume ratio $\rho(t) = \frac{Q_b(t) - Q_a(t)}{Q_b(t) + Q_a(t)}$
