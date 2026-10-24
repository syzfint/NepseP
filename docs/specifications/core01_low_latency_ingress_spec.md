# Core 0-1 Real-Time Tape Ingress Specification
**Date:** 2026-10-24

## Wash Trading Heuristic
1. Direct self-match: `buyer_broker == seller_broker` within 50ms.
2. Immediate circular round-trip: Broker A -> Broker B followed by Broker B -> Broker A.
