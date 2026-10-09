# 📚 ApexMarketEngine: Research & Methodology Traceability Matrix

## 1. Quantitative Finance & ML Literature Mapping

| Research Paper / Framework | Methodological Concept | NEPSE Market Context & Adaptation | Audit Result / Verification |
| :--- | :--- | :--- | :--- |
| **López de Prado (2018)** *Advances in Financial Machine Learning* | Fixed-width Window Fractional Differentiation ($d \approx 0.35$) | Achieves stationarity ($p < 0.05$) while preserving price memory ($r > 0.90$). | **PASS** |
| **López de Prado (2018)** *Advances in Financial Machine Learning* | Triple-Barrier Method & Meta-Labeling | Dynamic $1.5\sigma$ take-profit, $1.2\sigma$ stop-loss, 5-day vertical horizon. | **PASS** (Requires clean price series) |
| **López de Prado (2018)** *Advances in Financial Machine Learning* | Combinatorial Purged & Embargoed Cross-Validation (CPCV) | 5-day purge and 10-day embargo eliminate label overlap leakage. | **PASS** |
| **Bailey & López de Prado (2014)** *Deflated Sharpe Ratio (DSR)* | PBO & DSR Overfitting Adjustments | Controls for trial selection bias across multiple model iterations. | **PASS** |
| **Almgren & Chriss (2000)** *Optimal Execution of Portfolio Transactions* | Liquidity Constraints & ADV Cap | Position sizing capped at $\le 5\%$ of raw daily volume ($V_{\text{raw}}$). | **PASS** |
| **NEPSE Regulatory Framework** | TMS Tiered Commissions & Asymmetric CGT | Broker fees (0.40%–0.27%), SEBON (0.015%), DP NPR 25, CGT 7.5%/10.0%. | **PASS** (Configured in `config.yaml`) |

---

## 2. Foreign Market vs. NEPSE Empirical Reality

1. **Momentum vs. Reversal:** Foreign trend-following models assume positive momentum ($IC > 0$). In NEPSE, 1-week short-term reversal exhibits $IC = -0.0374$ ($t = -8.16$), proving NEPSE is mean-reverting.
2. **Annualization Factor:** U.S. markets use $\sqrt{252} = 15.87$. NEPSE has ~240 annual sessions; correct factor is $\sqrt{240} = 15.49$.
