# APEXMARKETENGINE — GATE CERTIFICATION REPORT

## 1. Master Certification Matrix

| Gate | Name | Reported Status | Certified Status | Core Evidence / Finding |
| :--- | :--- | :--- | :--- | :--- |
| **G0** | Data Truth | PASS | **CONDITIONAL_PASS** | 644,188 rows, 663 tickers verified. Pre-2010 delistings partially missing. |
| **G1** | Leakage | PASS | **CONDITIONAL_PASS** | Technical feature truncation passed ($\Delta=0.0$). Full system-wide certification pending. |
| **G2** | Corporate Actions | PASS | **CERTIFIED_PASS** | Backward cumulative multiplier $P_{\text{adj}} = P_{\text{raw}} \times \prod f_{\text{ex}}$ verified. |
| **G3** | Signal / IC | VALID_BUT_NO_EDGE | **CONDITIONAL_PASS** | Base Reversal $t=1.48$. Composite factor $t=4.13$ requires untouched OOS confirmation. |
| **G4** | Benchmark Baseline | PASS | **CERTIFIED_PASS** | Equal-weight benchmark $+3,870.51\%$ (Sharpe 1.08) reconciled vs NEPSE Index. |
| **G5** | Cost & Liquidity | PASS | **CERTIFIED_PASS** | Broker fees (0.40%-0.27%), SEBON (0.015%), DP (NPR 25), CGT (7.5%), 5% ADV verified. |
| **G6** | Execution Viability | PASS | **CONDITIONAL_PASS** | $Open_{t+1}$ fill with 5% ADV cap. L2 queue priority approximated. |
| **G7** | Purged CV | PASS | **CONDITIONAL_PASS** | CPCV embargo logic verified; fold-level metadata log generated. |
| **G8** | Complexity Ablation| PASS | **CONDITIONAL_PASS** | Factor baseline vs composite evaluated; ML hyperparameter grid pending. |
| **G9** | PBO / DSR | PASS | **CONDITIONAL_PASS** | DSR/PBO harness implemented; complete experiment registry logging active. |
| **G10**| Final OOS | PASS | **CONDITIONAL_PASS** | 2024-2026 Holdout defined; strict parameter freeze enforced. |

---

## 2. Hard Stop & Remediation Checklist

1. **System-Wide Zero-Leakage (G1)**: Re-verify end-to-end timestamp order across feature store generation to ensure text sentiment feeds strictly lag publication timestamps.
2. **Untouched OOS Evaluation (G3/G10)**: Ensure zero parameter tuning or feature selection occurs on the 2024–2026 holdout dataset.
3. **Microstructure Proxies (G6)**: Maintain conservative 5% ADV capacity cap to account for lack of historical L2 limit order book depth.
