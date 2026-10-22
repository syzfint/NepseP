# 🔬 Engineering & Research Log — October 22, 2026
**Topic:** Advances in Financial Machine Learning (AFML): DSR, CSCV, and PBO  
**Date:** `2026-10-22 04:30:00 PM NPT`  
**Author:** ApexMarketEngine Quantitative Research Group  
**Classification:** Institutional Mathematical Specification  

---

## 1. Executive Summary
Today's research formalized the elimination of selection bias under multiple testing in NEPSE factor mining. We implemented Marcos López de Prado's Deflated Sharpe Ratio (DSR) and Combinatorially Symmetric Cross-Validation (CSCV) to establish Gate G9 and Gate G10 compliance for sovereign equity strategies.

## 2. Deflated Sharpe Ratio (DSR) Formulation
Given $N$ independent strategy backtests with benchmark variance $V[\{\widehat{SR}_n\}]$, sample skewness $\hat{\gamma}_3$, and kurtosis $\hat{\gamma}_4$:

$$\widehat{SR}^* = \sqrt{V[\{\widehat{SR}_n\}]} \left( (1-\gamma) Z^{-1}\left(1 - \frac{1}{N}\right) + \gamma Z^{-1}\left(1 - \frac{1}{N e}\right) \right)$$

The Deflated Sharpe Ratio test statistic is:

$$\text{DSR} = Z\left[ \frac{(\widehat{SR} - \widehat{SR}^*) \sqrt{T-1}}{\sqrt{1 - \hat{\gamma}_3 \widehat{SR} + \frac{\hat{\gamma}_4 - 1}{4} \widehat{SR}^2}} \right]$$

A strategy must achieve $\text{DSR} \ge 0.95$ to pass Gate G9 certification, rejecting false-discovery alpha snooping.

## 3. Combinatorially Symmetric Cross-Validation (CSCV) & PBO
To calculate the Probability of Backtest Overfitting (PBO):
1. Partition the $T$ return observations into $S$ contiguous sub-matrices ($S=16$, $N=8$ combinations).
2. For each combination $c \in C(S, S/2)$, compute the in-sample (IS) optimal model and rank its out-of-sample (OOS) performance.
3. Compute the relative rank distribution $\lambda \in [0, 1]$.
4. The PBO is defined as:

$$\text{PBO} = \int_{-\infty}^0 f(\lambda) \, d\lambda \approx \frac{1}{|C|} \sum_{c=1}^{|C|} \mathbf{1}_{\{\lambda_c < 0.5\}}$$

We mandate $\text{PBO} < 0.15$ for any automated production allocation.
