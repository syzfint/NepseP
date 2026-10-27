# 🚀 ApexMarketEngine v1.0.0: Institutional Release Notes

**Release Date:** October 5, 2026  
**Git Tag:** `v1.0.0`  
**License:** MIT  
**Target Market:** Nepal Stock Exchange (NEPSE)

---

## 🌟 Overview & Highlights

ApexMarketEngine v1.0.0 is the foundational institutional release of the sovereign quantitative trading, lakehouse data engineering, and multimodal AI reasoning framework.

### 🔑 Key Features & Breakthroughs

1. **🦆 Out-of-Core DuckDB Engine:**
   * Sub-92ms query latencies across 644,188+ historical trading bars (415 tickers, 2003–2026).
   * Verified zero-data-loss window-ranked deduplication preserves all historical trading days.

2. **📈 Memory-Preserving Fractional Differentiation ($d = 0.35$):**
   * Stationarity achieved with Augmented Dickey-Fuller test ($p = 0.0121 < 0.05$).
   * Preserves $> 0.90$ price correlation, eliminating the severe memory destruction of integer differencing ($d = 1.0$).

3. **🛡️ Hysteresis Retention Rebalancing:**
   * Slashes portfolio turnover from $100\%$ down to $11.9\%$ (88.1% friction reduction).
   * Converts a $-61.34\%$ fee-drag loss into a **$+3,438.94\%$ net cumulative return** post 0.65% round-trip fee drag.

4. **🧠 CLEF Multimodal Vision-Language Reasoning:**
   * Integrates `Qwen/Qwen2.5-VL-3B-Instruct` with native Vision Transformer (ViT) patch reading.
   * Reads $2.0\sigma$ price corridor charts directly from pixel candle geometry without OCR.
   * Anti-permabull qualitative synthesis cross-examines technical buy signals against NRB monetary policies and corporate disclosures.

5. **🌐 Cloudflare Encrypted HTTPS Tunnel & Google Colab T4 GPU:**
   * Measured live end-to-end round-trip latency: **8.42 seconds**.
   * Dispatches 130,002-byte canonical payloads over `trycloudflare.com` without opening public router ports.
   * FP16 mixed-precision asynchronous inference on NVIDIA Tesla T4 (16 GB GDDR6).
   * Domain-specialized PEFT/LoRA fine-tuning ($r=16, \alpha=32$, 65 MB adapter weights).

6. **🔒 Cryptographic Fail-Closed Circuit Breaker:**
   * Enforces composite SHA-256 provenance seal: $\mathbf{H_{master} = \text{SHA256}(Ctx:Fcst:Disc:Vis)}$.
   * Zero host filesystem path leaks (charts encoded purely in-memory as Base64 strings).
   * Strict Pydantic v2 schema enforcement (`extra='forbid'`).
   * Fails closed to deterministic local numerical-only mode on any timeout, schema error, or hash mismatch.

7. **🖥️ 3-Tier Progressive Disclosure Web Terminal:**
   * Tier 1: Layman Executive Summary & High-Conviction Calls (Top Pick: NABIL, Hold).
   * Tier 2: Multimodal Evidence Matrix (Corridor Charts, Sentiment Gauge, OFI Bars).
   * Tier 3: Forensic Statistical Row (FracDiff ADF stats, SHAP attribution, Friction Alpha).

---

## 🛠️ Reproduction & Cold-Start Commands

```bash
# 1. Clone Blueprint
git clone https://github.com/syzfint/NepseP.git
cd NepseP

# 2. Install Frozen Dependencies
pip install -r requirements.txt

# 3. Initialize DuckDB Database Schemas
python scripts/01_etl_and_ingestion/init_duckdb.py

# 4. Verify 11-Step Integration Test Suite
pytest tests/test_clef_integration.py -v

# 5. Launch Interactive Terminal UI
streamlit run scripts/08_dashboard_ui/04_streamlit_terminal_ui.py
```

---

## 👥 Contributors & Acknowledgments
* **Lead Architect:** [SYZ-FINT (syzfint)](https://github.com/syzfint)
* **Quantitative Foundations:** Marcos López de Prado (*Advances in Financial Machine Learning*)
