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
- **Total Out-of-Sample Forecasts:** 3965
- **Ensemble Rank IC:** 0.0135 (p-value = 0.394457)
- **Unfiltered Baseline Hit Rate:** 49.96%
- **Gate G4 Certified Trades:** 494
- **Gate G4 Certified Hit Rate:** **51.82%**
- **Latest 5-Day Forward Return Forecast:** **-0.15%** (Meta-Prob: 48.8%)

## 4. Cross-Asset Alpha Forecasts & Hierarchical Risk Parity (HRP) Weights
| Symbol | Close (NPR) | Exp 5D Return | Meta-Conviction | Uncertainty Spread | HRP Weight | Risk-Adjusted Weight |
|---|---|---|---|---|---|---|
| **NABIL** | NPR 536.2 | +0.47% | 53.6% | 16.95% | 26.8% | **26.8%** |
| **CHCL** | NPR 333.0 | +0.72% | 53.9% | 24.37% | 18.7% | **18.7%** |
| **SHIVM** | NPR 686.0 | +0.29% | 51.9% | 19.42% | 17.8% | **17.8%** |
| **CIT** | NPR 1704.8 | -0.10% | 49.4% | 19.95% | 0.0% | **0.0%** |
| **GBIME** | NPR 245.2 | +0.08% | 50.6% | 17.07% | 26.8% | **26.8%** |
| **CASH RESERVE** | N/A | 0.00% | 100.0% | 0.00% | 10.0% | **10.0%** |

## 5. Portfolio Tail Risk & Kupiec POF Backtesting
- **Active Portfolio 95% VaR (Gaussian):** 2.35% (Cap: 3.5%)
- **Active Portfolio 95% Expected Shortfall:** 2.95% (Cap: 5.0%)
- **Tail Risk Derisking Activated:** `False`

| Metric / Methodology | Value at Risk (VaR 95%) | Expected Shortfall (ES 95%) |
|---|---|---|
| **Historical Simulation** | 2.393% | 5.04% |
| **Parametric Gaussian** | 3.604% | 4.518% |
| **Monte Carlo Simulation** | 3.668% | 4.582% |

### Kupiec Unconditional Coverage Validation
| Model | Forecasts | Exceptions | Observed Rate | LR Statistic | p-value | Verdict |
|---|---|---|---|---|---|---|
| **Historical** | 3989 | 241 | 6.042% | 8.567721 | 0.003422 | **FAIL** |
| **Parametric** | 3989 | 124 | 3.109% | 34.5224 | 0.0 | **FAIL** |
| **Monte_carlo** | 3989 | 125 | 3.134% | 33.540709 | 0.0 | **FAIL** |

## 6. Live Staged Execution Blotter (Dynamic POV & TMS Gateway)
- **Blotter Reference ID:** `BLOTTER-20261011-093205`
- **Total Capital:** NPR 10,000,000.00 | **Available Cash Reserve:** NPR 999,000.00
- **Total Staged Child Orders:** 29
- **Total Buy Value:** NPR 8,393,662.00 | **Est. Commission:** NPR 34,833.70
- **Compliance & Collateral Check:** `PASS`
- **Cryptographic SHA-256 Provenance Hash:** `04b1ceb3a74aa5d30e8d6a5fedda817e3e76c00a9f8c6453ec36b87136cb6ae3`

| Ticket ID | Symbol | Side | Quantity | Limit Price (NPR) | Total NPR | Slices | LOB Depth Share | Circuit Range | Status |
|---|---|---|---|---|---|---|---|---|---|
| `TICK-CHCL-1OF4-D3E60F` | **CHCL** | `BUY` | 1200 | NPR 333.0 | 399,600 | 1/4 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-2OF4-10882F` | **CHCL** | `BUY` | 1200 | NPR 333.0 | 399,600 | 2/4 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-3OF4-32276A` | **CHCL** | `BUY` | 1200 | NPR 333.0 | 399,600 | 3/4 | 15.0% | [292.5, 357.5] | **STAGED** |
| `TICK-CHCL-4OF4-806F25` | **CHCL** | `BUY` | 1000 | NPR 333.0 | 333,000 | 4/4 | 12.5% | [292.5, 357.5] | **STAGED** |
| `TICK-NABIL-1OF7-FCC35D` | **NABIL** | `BUY` | 670 | NPR 536.2 | 359,254 | 1/7 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-2OF7-78CF94` | **NABIL** | `BUY` | 670 | NPR 536.2 | 359,254 | 2/7 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-3OF7-03CB5E` | **NABIL** | `BUY` | 670 | NPR 536.2 | 359,254 | 3/7 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-4OF7-1AF515` | **NABIL** | `BUY` | 670 | NPR 536.2 | 359,254 | 4/7 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-5OF7-A71446` | **NABIL** | `BUY` | 670 | NPR 536.2 | 359,254 | 5/7 | 14.89% | [477.0, 583.0] | **STAGED** |
| `TICK-NABIL-6OF7-5BC78C` | **NABIL** | `BUY` | 670 | NPR 536.2 | 359,254 | 6/7 | 14.89% | [477.0, 583.0] | **STAGED** |
| *... and 19 more child tickets staged in static_data/live_staged_orders.json* | | | | | | | | | |

## 7. R&D Memory Graph: Autonomous Evolution Diagnostics
- **BrokerSyndicateHerdingFactor** [REVISE]: Failed criteria: Rank IC 0.0000 < 0.03; ICIR 0.00 < 0.4; Net Sharpe -1.25 < 0.8; Monotonicity inverted (0.0000 <= 0). Requires reformulation or longer holding horizon.
- **PromoterLockinCorneringFactor** [REVISE]: Failed criteria: Rank IC 0.0117 < 0.03; ICIR -14.02 < 0.4; Net Sharpe 0.33 < 0.8. Requires reformulation or longer holding horizon.
- **MonsoonReconstructionHedgeFactor** [REVISE]: Failed criteria: ICIR -3.33 < 0.4; Net Sharpe 0.16 < 0.8. Requires reformulation or longer holding horizon.
- **OddLotAbsorptionFactor** [REVISE]: Failed criteria: ICIR -5.06 < 0.4. Requires reformulation or longer holding horizon.
- **PreOpenSpoofReversalFactor** [REVISE]: Failed criteria: Net Sharpe -1.55 < 0.8; Monotonicity inverted (-0.0005 <= 0). Requires reformulation or longer holding horizon.

---
*End of RD-Agent & Qlib Institutional Strategy Report.*