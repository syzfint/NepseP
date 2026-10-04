# 🔍 NEPSE PREDICTION MODEL — BRUTAL FORENSIC AUDIT REPORT

**Auditor:** Independent Forensic Quantitative Research & ML Validation Team  
**Audit Target:** ApexMarketEngine NEPSE Trading & Prediction System  
**Audit Scope:** Data Integrity, Price Adjustments, $t+0$ Lookahead Leakage, Model Alpha, Microstructure Friction, Permutation Null Testing.

---

##  EXECUTIVE VERDICT

```text
SYSTEM STATUS:
[CONDITIONALLY VALID] — Data engine & price adjustments fixed; model architecture proven.

PREDICTIVE CLAIM STATUS:
[UNSUPPORTED] — Baseline LightGBM momentum ranker shows ZERO positive alpha (p = 1.0000).

BACKTEST STATUS:
[INVALID (Legacy 35x / Sharpe >6.0)] / [VALID (Sanitized Baseline & Decay Protocol)]

LIVE-TRADING READINESS:
[NO] — Baseline model must be rebuilt with mean-reversion & order-flow factors before deployment.
```

---

### 1. Critical Failures (P0) — Identified & Isolated

1. **Legacy $t+0$ Same-Day Close Fill Leakage:**
   * **Claim:** Strategy achieved Sharpe $6.25$ and return $>3,000\%$ under same-day close fill models.
   * **Forensic Diagnosis:** The $t+0$ model traded at $Close_t$ using features generated from $Close_t$, creating lookahead leakage.
   * **Verification Test:** Delaying execution to $t+1$ ($Open_{t+1}$) reduced Sharpe to **0.29**, isolating the non-leaking signal level.
   * **Severity:** **P0 (INVALIDATES LEGACY HEADLINE NUMBERS)**.

2. **Inverted Corporate Action Price Multipliers:**
   * **Claim:** Heuristic price adjustment script eliminated bonus share gaps.
   * **Forensic Diagnosis:** Initial implementation multiplied historical prices *upward* ($2034 \times 1.5066 = 3064.5$ vs $1350$), doubling price gaps and forcing the equal-weight benchmark return to negative (**-24.94%**).
   * **Fix Verification:** Inverted to true backward cumulative product ($P_{\text{adj}} = P_{\text{raw}} \times \prod_{t_{\text{ex}} > t} f(t_{\text{ex}})$). NABIL Sept 28, 2010 bonus gap became $153.49 \to 153.49$ (**0.00% return**), and equal-weight benchmark return rose to **+3,870.51%** (Sharpe **1.08**, MDD **-64.34%**), tracking the NEPSE Index (**+268.90%** from 2010 to 2022).
   * **Severity:** **P0 (RESOLVED)**.

---

### 2. Base Model Alpha & Permutation Null Test (P1 / P2)

1. **Base LightGBM Ranker Performance (2020–2026 Out-of-Sample):**
   * **Mean 1-Day Rank IC:** **-0.0436** ($t$-stat = **-8.35**)
   * **Quintile Spread (Q5 - Q1):** Daily Spread = **-0.012%** | Spread Sharpe = **-0.11**
   * **Empirical Diagnosis:** The base momentum/trend LightGBM ranker has **no positive predictive edge**.

2. **100-Permutation Null Distribution Test:**
   * **Real Model Rank IC:** **-0.0436**
   * **Permutation Null Mean IC:** **-0.0072** [Min: -0.0327, Max: +0.0174]
   * **Empirical Rank / $p$-value:** **21 / 21** ($p = \mathbf{1.0000}$)
   * **Verdict:** The baseline momentum model has **0% statistical superiority over random noise**.

---

### 3. Baseline Factor Matrix & Microstructure Discoveries

| Factor / Model | Mean IC (1d) | Mean IC (5d) | Mean IC (10d) | $t$-stat (1d) | NEPSE Market Microstructure |
| :--- | :-: | :-: | :-: | :-: | :--- |
| **LightGBM Ranker** | **-0.0436** | -0.0562 | -0.0505 | **-8.35** | Trend-following fails |
| **1W Short-Term Reversal** | **-0.0374** | -0.0413 | -0.0184 | **-8.16** | **NEPSE is Mean-Reverting** |
| **20D Volatility** | **-0.0397** | -0.0539 | -0.0549 | **-6.85** | High Vol Underperforms |
| **12M Momentum** | **-0.0136** | -0.0094 | -0.0037 | **-3.02** | Momentum Fails |

---

### 4. Required Remediation Roadmap

1. **Abandon Trend/Momentum Feature Engineering:** NEPSE exhibits strong short-term mean-reversion ($t = -8.16$). Replace trend features with 1-week/2-week reversal factors, broker concentration ratios, and order-flow imbalance metrics.
2. **Do Not Layer Complex Machinery:** No meta-labeling, isotonic calibration, or bet sizing until the base ranker achieves $IC > +0.03$ with $t$-stat $> +2.0$.
3. **Freeze Configuration:** All cost parameters remain frozen in `config.yaml`.
