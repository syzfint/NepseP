# 🔬 Engineering & Research Log — October 21, 2026
**Topic:** Microstructure Order Flow Imbalance (OFI) & Multi-Depth Liquidity Modeling  
**Date:** `2026-10-21 02:15:00 PM NPT`  
**Author:** ApexMarketEngine Quantitative Research Group  
**Classification:** Institutional Architecture Specification  

---

## 1. Executive Summary
During the market pause, research focused on formalizing Cont-Stoikov Level-2 Order Flow Imbalance (OFI) specifically tailored to the discrete-lot NEPSE auction structure. Because NEPSE exhibits high queue viscosity and retail clustering around psychological price tiers, naive top-of-book delta fails to capture institutional accumulation hidden across sub-levels.

## 2. Mathematical Formalization: Normalized Multi-Depth OFI
For price level $i \in \{1, \dots, K\}$ with best bid price $P_t^b$, best ask price $P_t^a$, bid quantity $Q_{i,t}^b$, and ask quantity $Q_{i,t}^a$:

$$\Delta W_{i,t}^b = \begin{cases} 
Q_{i,t}^b & \text{if } P_{i,t}^b > P_{i,t-1}^b \\
Q_{i,t}^b - Q_{i,t-1}^b & \text{if } P_{i,t}^b = P_{i,t-1}^b \\
-Q_{i,t-1}^b & \text{if } P_{i,t}^b < P_{i,t-1}^b 
\end{cases}$$

$$\Delta W_{i,t}^a = \begin{cases} 
-Q_{i,t}^a & \text{if } P_{i,t}^a < P_{i,t-1}^a \\
Q_{i,t}^a - Q_{i,t-1}^a & \text{if } P_{i,t}^a = P_{i,t-1}^a \\
Q_{i,t-1}^a & \text{if } P_{i,t}^a > P_{i,t-1}^a 
\end{cases}$$

The multi-depth Normalized OFI ($\text{NOFI}_t$) is weighted exponentially across the top 5 levels:

$$\text{NOFI}_t = \frac{\sum_{i=1}^5 e^{-\lambda (i-1)} (\Delta W_{i,t}^b - \Delta W_{i,t}^a)}{\sum_{i=1}^5 e^{-\lambda (i-1)} (Q_{i,t}^b + Q_{i,t}^a)}$$

Where $\lambda = 0.40$ applies institutional decay to deeper, less immediately executable queues.

## 3. Integration Blueprint
1. Implement in `scripts/02_modeling_and_calculations/ofi_depth_calculator.py`.
2. Map to WebSocket pulse telemetry stream for real-time visualization in Cockpit Screen S04.
3. Compute rolling 60-second queue depletion z-scores to trigger high-frequency institutional absorption flags.
