# Advances in Financial Machine Learning: DSR & PBO Whitepaper
**Author:** ApexMarketEngine Quantitative Research
**Date:** 2026-10-22

## 1. Multiple Testing Problem
When an algorithmic trading team evaluates $N$ factor variations, the maximum observed Sharpe ratio $\max_n \{SR_n\}$ is an upward-biased estimate of future performance. Under the null hypothesis of zero true skill, standard t-tests overstate significance.

## 2. Deflated Sharpe Ratio (DSR)
DSR computes the probability that the observed Sharpe ratio exceeds the expected maximum Sharpe ratio under the null hypothesis of no alpha, accounting for track record length, skewness, and kurtosis.
