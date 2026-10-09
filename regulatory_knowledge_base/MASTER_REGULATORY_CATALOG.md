# NEPSE / NRB / SEBON Master Regulatory Knowledge Catalog

This repository contains the complete regulatory framework governing the Nepal Stock Exchange (NEPSE).
It is partitioned into two distinct directories to prevent algorithmic models from referencing obsolete laws:

- **`updated_active_laws/`**: ONLY current, in-force statutory directives, fee slabs, margin limits, and bylaws.
- **`superseded_historical_laws/`**: Repealed, amended, and historical rules preserved for event-study backtesting.

---

## 1. Updated Active Laws (`updated_active_laws/`)

| ID | Regulator | Title | Effective Date | Key Impact |
| :--- | :---: | :--- | :---: | :--- |
| `NRB-DIR-08-2081` | **NRB** | Unified Directive No. 8: Margin Lending & Share Collateral Credit Caps | `2024-08-15` | Governs loan against shares (Margin Lending). Individual borrowing cap fixed at NPR 15 Cro... |
| `NRB-DIR-03-2081` | **NRB** | Unified Directive No. 3: Capital Adequacy & Risk Weighting on Margin Loans | `2024-05-10` | Risk-weight on share-backed loans up to NPR 50 Lakhs lowered to 100%. Loans above NPR 50 L... |
| `NRB-MONETARY-POLICY-2081-82` | **NRB** | Annual Monetary Policy 2081/82 & Semi-Annual Review | `2024-07-26` | Maintains accommodative monetary stance. Cash Reserve Ratio (CRR) fixed at 4.0%; Statutory... |
| `SEBON-COMMISSION-2081` | **SEBON** | Securities Broker Commission Slabs & Regulatory Fee Directive | `2024-04-10` | Establishes tiered broker commission slabs: 0.40% up to NPR 50k, 0.37% (50k-500k), 0.34% (... |
| `SEBON-LOCKIN-REG-2075` | **SEBON** | Securities Registration and Issue Regulations: 3-Year Promoter Lock-In Rule | `2018-09-01` | Mandates that promoter shares of real-sector and hydropower companies cannot be traded or ... |
| `SEBON-CGT-TAX-2081` | **SEBON** | Capital Gains Tax (CGT) & TDS Schedule (Finance Act 2081) | `2024-07-16` | Statutory capital gains tax deducted at source: 7.5% for individual short-term holders (<3... |
| `SEBON-IPO-10KITTA-2075` | **SEBON** | Public Issue Allotment Guidelines: Mandatory 10-Kitta Minimum Rule | `2019-03-20` | Mandates pro-rata lottery distribution ensuring minimum 10 shares (10-kitta) to each succe... |
| `NEPSE-CIRCUIT-BREAKER-2081` | **NEPSE** | Automated Index Circuit Breaker By-laws & Trading Halt Schedule | `2024-01-01` | Automated 3-tier index circuit breakers: 4% index change halts trading for 20 minutes if o... |
| `NEPSE-PRE-OPEN-BYLAW-2077` | **NEPSE** | Pre-Open Call Auction By-laws (10:30 AM – 10:45 AM) | `2020-11-01` | Establishes automated multilateral call auction matching. Order entry occurs between 10:30... |
| `NEPSE-LISTING-BYLAW-2075` | **NEPSE** | Securities Listing and Classification By-laws (Category A, B, G, Z) | `2018-08-15` | Classifies listed equities into four distinct risk classes based on minimum paid-up capita... |

---

## 2. Superseded & Historical Laws (`superseded_historical_laws/`)

| ID | Regulator | Title | Repealed Date | Replaced By | Reason for Repeal |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `NRB-DIR-08-2079` | **NRB** | Previous Margin Lending Cap Directive (4-12 Crore Rule) | `2023-10-05` | `NRB-DIR-08-2081` | Restricted capital market liquidity and forced fire-sales; replaced by... |
| `NRB-CIRC-RW-150` | **NRB** | Punitive 150% Risk-Weighting on All Margin Loans | `2023-09-18` | `NRB-DIR-03-2081` | Reduced to 125% and 100% (under 50L) to revive trading turnover.... |
| `SEBON-COMMISSION-2077` | **SEBON** | Previous Broker Commission Slabs (0.60% to 0.40%) | `2024-04-10` | `SEBON-COMMISSION-2081` | Reduced by ~10% to 15% across all slabs to lower retail and institutio... |
| `SEBON-CGT-TAX-2078` | **SEBON** | Uniform 5.0% Capital Gains Tax Code | `2021-07-16` | `SEBON-CGT-TAX-2081` | Replaced by dual short-term (7.5%) vs long-term (5.0%) tiers to discou... |
| `NEPSE-CIRCUIT-OLD-2072` | **NEPSE** | Legacy Manual Circuit Breaker System | `2023-12-31` | `NEPSE-CIRCUIT-BREAKER-2081` | Replaced by fully automated algorithm integrated into NEPSE NOTS core ... |
| `NEPSE-MANUAL-OPEN-OLD` | **NEPSE** | Previous Open-Outcry Pre-Open Matching Procedure | `2020-10-31` | `NEPSE-PRE-OPEN-BYLAW-2077` | Replaced by electronic IEP call auction matching.... |