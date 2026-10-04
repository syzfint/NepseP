---
name: Quantitative Strategy Proposal
about: Propose a new quantitative signal, risk model, or execution strategy
title: '[STRATEGY] '
labels: 'strategy, enhancement'
assignees: 'syzfint'
---

### 📈 Strategy Thesis
Describe the economic intuition, market anomaly, or behavioral thesis being exploited.

### 🧮 Mathematical Formulation
Provide LaTeX mathematical formulas for signal calculation, lag structure, and differencing orders:
$$Signal_t = f(X_{t-1}, \dots)$$

### 🛡️ 10-Gate Audit Pre-Screen
- [ ] **No Lookahead Leakage:** Features lagged strictly $t-1$ or earlier.
- [ ] **Stationarity:** Fractional differentiation parameter $d$ identified (ADF $p < 0.05$).
- [ ] **Friction Drag:** Survives $0.65\%$ NEPSE round-trip fee penalty.
- [ ] **Turnover:** Employs hysteresis retention or trade smoothing.
- [ ] **Cross-Validation:** Evaluated under Purged & Embargoed CPCV.

### 📊 Preliminary Backtest Results
* **Deflated Sharpe Ratio (DSR):**
* **Max Drawdown (MDD):**
* **Information Coefficient (Rank IC):**
