# Low-Latency Thread Pinning & IPC Shared Memory
**Date:** 2026-10-24

## Logical Core Allocation
- Cores 0-1: Tape Ingress, Anti-Wash Heuristics, VPIN toxicity.
- Cores 2-N: ASGI Server, WebSockets, Factor Evaluator, DuckDB out-of-core queries.
