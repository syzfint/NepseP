# 🤝 Contributing to ApexMarketEngine

Thank you for your interest in contributing to **ApexMarketEngine**! We welcome research contributions, algorithmic enhancements, and quantitative audits.

---

## 🏛️ Guiding Architectural Principles

### 1. The Blueprint vs. State Paradigm
* **The Remote Repository is a Code Blueprint (<1 MB):** Never commit raw tick datasets (`.parquet`, `.csv`), DuckDB files (`.duckdb`), virtual environments, or secrets (`.env`).
* All pipelines must assume cold-start hydration via `python scripts/init_duckdb.py`.

### 2. The 10-Gate Forensic Standard
Every pull request introducing mathematical formulas or trading signals must pass the 10 validation gates:
1. Purged Walk-Forward Leakage (10-day purge buffer + 5-day embargo)
2. Stationary Memory Preservation ($d = 0.35$, ADF $p < 0.05$)
3. Friction Drag Resilience ($0.65\%$ NEPSE round-trip fee penalty survived)
4. Deflated Sharpe Ratio ($\text{DSR} \ge 0.95$)
5. Max Drawdown Constraint ($\le 18.5\%$)
6. Information Coefficient ($\text{Rank IC} \ge +0.04$)
7. TreeSHAP Attribution Audit
8. Pydantic v2 Canonical Schemas (`extra='forbid'`)
9. Zero Host File Leakage (In-memory Base64 only)
10. Composite Provenance Hash Verification ($\mathbf{H_{master}}$ match)

---

## 🛠️ Development & Testing Workflow

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/syzfint/NepseP.git
   cd NepseP
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify the test harness**:
   ```bash
   pytest tests/test_clef_integration.py -v
   ```

4. **Submit your Pull Request** referencing the relevant issue and filling out the 10-Gate forensic checklist.
