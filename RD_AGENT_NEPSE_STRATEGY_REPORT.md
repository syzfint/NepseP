# [RD-Agent & Qlib at NEPSE Scale] Institutional Strategy Execution Report
**Document Classification:** Quantitative Production Architecture & Strategy Audit
**Engine Target:** APEXMARKETENGINE / NEPSE Adaptive Execution Plane

## 1. Executive Summary
This report documents the end-to-end execution of the customized **RD-Agent & Qlib Autonomous Quantitative Strategy** on the Nepal Stock Exchange (NEPSE). Naive Western assumptions have been replaced by empirical NEPSE microstructural realities:
- **Friction Accounting**: Realized round-trip execution cost deducted at 0.85% (broker 0.40% + SEBON 0.015% + DP/Clearing).
- **Settlement Feasibility**: Enforces T+2 Demat settlement holding periods with zero lookahead bias.
- **Execution Realism**: Orders triggered during +/-10% daily circuit locks are penalized and filtered.
- **Sovereign Microstructure Constraints**: 10-unit board lots, 15% top-3 LOB depth caps, Almgren-Chriss dynamic POV slicing, and VPIN adverse selection pause controls.

## 2. Certified AlphaNEPSE Factor Zoo
| Factor Name | Category | Rank IC | ICIR | Turnover | Net Sharpe (Post-0.85% Drag) |
|---|---|---|---|---|---|

## 3. Adaptive Quant Forecaster Performance (Rolling Purged T+2)
- **Total Out-of-Sample Forecasts:** 3969
- **Ensemble Rank IC:** 0.0097 (p-value = 0.541949)
- **Unfiltered Baseline Hit Rate:** 49.96%
- **Gate G4 Certified Trades:** 483
- **Gate G4 Certified Hit Rate:** **51.35%**
- **Latest 5-Day Forward Return Forecast:** **0.12%** (Meta-Prob: 50.9%)

## 4. Cross-Asset Alpha Forecasts & Hierarchical Risk Parity (HRP) Weights
| Symbol | Close (NPR) | Exp 5D Return | Meta-Conviction | Uncertainty Spread | HRP Weight | Risk-Adjusted Weight |
|---|---|---|---|---|---|---|
| **NABIL** | NPR 544.6 | +0.61% | 54.7% | 16.93% | 31.9% | **31.9%** |
| **CHCL** | NPR 334.0 | +0.32% | 51.7% | 24.37% | 26.2% | **26.2%** |
| **SHIVM** | NPR 677.3 | -0.51% | 46.5% | 19.40% | 0.0% | **0.0%** |
| **CIT** | NPR 1727.0 | +0.55% | 53.6% | 19.92% | 31.9% | **31.9%** |
| **GBIME** | NPR 253.0 | -0.16% | 48.8% | 17.06% | 0.0% | **0.0%** |
| **CASH RESERVE** | N/A | 0.00% | 100.0% | 0.00% | 10.0% | **10.0%** |

## 5. Portfolio Tail Risk & Kupiec POF Backtesting
- **Active Portfolio 95% VaR (Gaussian):** 2.27% (Cap: 3.5%)
- **Active Portfolio 95% Expected Shortfall:** 2.85% (Cap: 5.0%)
- **Tail Risk Derisking Activated:** `False`

| Metric / Methodology | Value at Risk (VaR 95%) | Expected Shortfall (ES 95%) |
|---|---|---|
| **Historical Simulation** | 2.377% | 5.044% |
| **Parametric Gaussian** | 3.623% | 4.542% |
| **Monte Carlo Simulation** | 3.687% | 4.607% |

### Kupiec Unconditional Coverage Validation
| Model | Forecasts | Exceptions | Observed Rate | LR Statistic | p-value | Verdict |
|---|---|---|---|---|---|---|
| **Historical** | 3993 | 242 | 6.061% | 8.882572 | 0.002879 | **FAIL** |
| **Parametric** | 3993 | 121 | 3.03% | 37.731927 | 0.0 | **FAIL** |
| **Monte_carlo** | 3993 | 124 | 3.105% | 34.680244 | 0.0 | **FAIL** |

## 6. Live Staged Execution Blotter (Dynamic POV & TMS Gateway)
- **Blotter Reference ID:** `BLOTTER-20261016-100059`
- **Total Capital:** NPR 10,000,000.00 | **Available Cash Reserve:** NPR 999,000.00
- **Total Staged Child Orders:** 25
- **Total Buy Value:** NPR 8,379,190.00 | **Est. Commission:** NPR 34,773.64
- **Compliance & Collateral Check:** `PASS`
- **Cryptographic SHA-256 Provenance Hash:** `bf33389e57deea21b2d7e6e297621c9fee83cc3b3bd48bbf82a9294f3ec4b707`

| Ticket ID | Symbol | Side | Quantity | Limit Price (NPR) | Total NPR | Slices | LOB Depth Share | Circuit Range | Status |
|---|---|---|---|---|---|---|---|---|---|
| `TICK-NABIL-1OF8-C3D9F8` | **NABIL** | `BUY` | 670 | NPR 544.6 | 364,882 | 1/8 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-2OF8-CBB046` | **NABIL** | `BUY` | 670 | NPR 544.6 | 364,882 | 2/8 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-3OF8-ED0C90` | **NABIL** | `BUY` | 670 | NPR 544.6 | 364,882 | 3/8 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-4OF8-95135C` | **NABIL** | `BUY` | 670 | NPR 544.6 | 364,882 | 4/8 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-5OF8-B49033` | **NABIL** | `BUY` | 670 | NPR 544.6 | 364,882 | 5/8 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-6OF8-19AC35` | **NABIL** | `BUY` | 670 | NPR 544.6 | 364,882 | 6/8 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-7OF8-8E92FE` | **NABIL** | `BUY` | 670 | NPR 544.6 | 364,882 | 7/8 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-8OF8-D8C6A5` | **NABIL** | `BUY` | 660 | NPR 544.6 | 359,436 | 8/8 | 14.67% | [477.0, 583.0] | **STAGED** |
| `TICK-CIT-1OF11-C49E08` | **CIT** | `BUY` | 180 | NPR 1727.0 | 310,860 | 1/11 | 15.0% | [1543.5, 1886.5] | **STAGED** |
| `TICK-CIT-2OF11-9B895C` | **CIT** | `BUY` | 180 | NPR 1727.0 | 310,860 | 2/11 | 15.0% | [1543.5, 1886.5] | **STAGED** |
| *... and 15 more child tickets staged in static_data/live_staged_orders.json* | | | | | | | | | |

## 7. R&D Memory Graph: Autonomous Evolution Diagnostics
- **BrokerSyndicateHerdingFactor** [REVISE]: Failed criteria: Rank IC 0.0000 < 0.03; ICIR 0.00 < 0.4; Net Sharpe -1.25 < 0.8; Monotonicity inverted (0.0000 <= 0). Requires reformulation or longer holding horizon.
- **PromoterLockinCorneringFactor** [REVISE]: Failed criteria: Rank IC 0.0115 < 0.03; ICIR -14.06 < 0.4; Net Sharpe 0.27 < 0.8. Requires reformulation or longer holding horizon.
- **MonsoonReconstructionHedgeFactor** [REVISE]: Failed criteria: ICIR -3.32 < 0.4; Net Sharpe 0.14 < 0.8. Requires reformulation or longer holding horizon.
- **OddLotAbsorptionFactor** [REVISE]: Failed criteria: ICIR -4.98 < 0.4. Requires reformulation or longer holding horizon.
- **PreOpenSpoofReversalFactor** [REVISE]: Failed criteria: Rank IC 0.0289 < 0.03; Net Sharpe -1.46 < 0.8. Requires reformulation or longer holding horizon.

---
*End of RD-Agent & Qlib Institutional Strategy Report.*