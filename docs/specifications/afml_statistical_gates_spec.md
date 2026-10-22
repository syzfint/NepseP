# AFML Statistical Gates Specification
**Gate G9:** Deflated Sharpe Ratio (DSR >= 0.95)
**Gate G10:** Probability of Backtest Overfitting (PBO < 0.15)
**Date:** 2026-10-22

## CSCV Partitioning Matrix
- Split $T$ observations into $S=16$ non-overlapping contiguous slices.
- Evaluate all $\binom{16}{8} = 12,870$ combination pairs.
- Confirm rank distribution symmetry around median.
