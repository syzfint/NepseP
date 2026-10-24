# 🔬 Engineering & Research Log — October 24, 2026
**Topic:** Hardware Thread Pinning & Low-Latency Real-Time Ingress Architecture  
**Date:** `2026-10-24 03:20:00 PM NPT`  
**Author:** ApexMarketEngine Infrastructure & Systems Engineering  
**Classification:** Low-Latency Execution Architecture  

---

## 1. Executive Summary
High-frequency floorsheet reconciliation in NEPSE suffers from Windows thread migration jitter when UI rendering and background factor estimation run on the same logical CPU cores. Today's research established hard CPU affinity masking: Core 0-1 for low-latency ingress, and Core 2-N for asynchronous WebSocket and analytics.

## 2. CPU Affinity Mask Topology
On a multi-core x86-64 host with $N$ logical processors:
* **Core 0-1 (Ingress Sentinel):** Affined with bitmask `0x3` (`0b00000011`).
* **Core 2-N (Async Pool):** Affined with dynamic inverted bitmask:

$$\text{Mask}_{\text{async}} = \left( 2^N - 1 \right) \oplus \text{0x3}$$

For an 8-core CPU, $\text{Mask}_{\text{async}} = \text{0xFC}$.

## 3. SEBON Anti-Wash & Circular Trade Dead-Letter Quarantine
The ingress engine operates a sub-50ms ring buffer (`AntiWashFilter`):
1. **Direct Self-Dealing:** Identical buyer and seller broker IDs within $\Delta t < 50\text{ ms}$ at matched price/qty.
2. **Circular Pump Syndicates:** Broker A selling to Broker B, matched immediately by Broker B selling back to Broker A within 3 ticks.
Violating ticks are severed from analytical feature arrays and redirected to `data/sebon_dlq/` for regulatory reporting.
