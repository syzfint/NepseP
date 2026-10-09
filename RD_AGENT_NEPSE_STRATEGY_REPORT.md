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
- **Total Out-of-Sample Forecasts:** 3963
- **Ensemble Rank IC:** 0.0136 (p-value = 0.392741)
- **Unfiltered Baseline Hit Rate:** 49.99%
- **Gate G4 Certified Trades:** 494
- **Gate G4 Certified Hit Rate:** **51.82%**
- **Latest 5-Day Forward Return Forecast:** **0.02%** (Meta-Prob: 50.1%)

## 4. Cross-Asset Alpha Forecasts & Hierarchical Risk Parity (HRP) Weights
| Symbol | Close (NPR) | Exp 5D Return | Meta-Conviction | Uncertainty Spread | HRP Weight | Risk-Adjusted Weight |
|---|---|---|---|---|---|---|
| **NABIL** | NPR 532.9 | +0.30% | 52.3% | 16.95% | 45.0% | **45.0%** |
| **CHCL** | NPR 328.0 | +0.52% | 52.8% | 24.37% | 45.0% | **45.0%** |
| **SHIVM** | NPR 671.0 | -1.14% | 42.4% | 19.43% | 0.0% | **0.0%** |
| **CIT** | NPR 1712.0 | -0.03% | 49.8% | 19.96% | 0.0% | **0.0%** |
| **GBIME** | NPR 241.0 | -0.01% | 49.9% | 17.07% | 0.0% | **0.0%** |
| **CASH RESERVE** | N/A | 0.00% | 100.0% | 0.00% | 10.0% | **10.0%** |

## 5. Portfolio Tail Risk & Kupiec POF Backtesting
- **Active Portfolio 95% VaR (Gaussian):** 2.45% (Cap: 3.5%)
- **Active Portfolio 95% Expected Shortfall:** 3.07% (Cap: 5.0%)
- **Tail Risk Derisking Activated:** `False`

| Metric / Methodology | Value at Risk (VaR 95%) | Expected Shortfall (ES 95%) |
|---|---|---|
| **Historical Simulation** | 2.393% | 5.04% |
| **Parametric Gaussian** | 3.605% | 4.519% |
| **Monte Carlo Simulation** | 3.669% | 4.583% |

### Kupiec Unconditional Coverage Validation
| Model | Forecasts | Exceptions | Observed Rate | LR Statistic | p-value | Verdict |
|---|---|---|---|---|---|---|
| **Historical** | 3987 | 241 | 6.045% | 8.611885 | 0.00334 | **FAIL** |
| **Parametric** | 3987 | 124 | 3.11% | 34.443574 | 0.0 | **FAIL** |
| **Monte_carlo** | 3987 | 125 | 3.135% | 33.462919 | 0.0 | **FAIL** |

## 6. Live Staged Execution Blotter (Dynamic POV & TMS Gateway)
- **Blotter Reference ID:** `BLOTTER-20261007-233030`
- **Total Capital:** NPR 10,000,000.00 | **Available Cash Reserve:** NPR 1,000,000.00
- **Total Staged Child Orders:** 23
- **Total Buy Value:** NPR 8,400,106.00 | **Est. Commission:** NPR 34,860.44
- **Compliance & Collateral Check:** `PASS`
- **Cryptographic SHA-256 Provenance Hash:** `ff6cce7b52ea9b80c327d4dbbefc962dc31faaca95ddcfc21268ded465e5e4f3`

| Ticket ID | Symbol | Side | Quantity | Limit Price (NPR) | Total NPR | Slices | LOB Depth Share | Circuit Range | Status |
|---|---|---|---|---|---|---|---|---|---|
| `TICK-CHCL-1OF11-BC9282` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 1/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-2OF11-ADC4D1` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 2/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-3OF11-1AD093` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 3/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-4OF11-673D89` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 4/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-5OF11-668381` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 5/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-6OF11-B5B7C2` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 6/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-7OF11-AFAD12` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 7/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-8OF11-0DA84D` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 8/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-9OF11-7F9304` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 9/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-10OF11-66F13A` | **CHCL** | `BUY` | 1200 | NPR 328.0 | 393,600 | 10/11 | 15.0% | [292.5, 357.5] | **STAGED** |
| *... and 13 more child tickets staged in static_data/live_staged_orders.json* | | | | | | | | | |

## 7. R&D Memory Graph: Autonomous Evolution Diagnostics
- **BrokerSyndicateHerdingFactor** [REVISE]: Failed criteria: Rank IC 0.0000 < 0.03; ICIR 0.00 < 0.4; Net Sharpe -1.25 < 0.8; Monotonicity inverted (0.0000 <= 0). Requires reformulation or longer holding horizon.
- **PromoterLockinCorneringFactor** [REVISE]: Failed criteria: Rank IC 0.0117 < 0.03; ICIR -14.02 < 0.4; Net Sharpe 0.33 < 0.8. Requires reformulation or longer holding horizon.
- **MonsoonReconstructionHedgeFactor** [REVISE]: Failed criteria: ICIR -3.33 < 0.4; Net Sharpe 0.16 < 0.8. Requires reformulation or longer holding horizon.
- **OddLotAbsorptionFactor** [REVISE]: Failed criteria: ICIR -5.06 < 0.4. Requires reformulation or longer holding horizon.
- **PreOpenSpoofReversalFactor** [REVISE]: Failed criteria: Net Sharpe -1.55 < 0.8; Monotonicity inverted (-0.0005 <= 0). Requires reformulation or longer holding horizon.

---
*End of RD-Agent & Qlib Institutional Strategy Report.*