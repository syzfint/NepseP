# 🏗️ ApexMarketEngine: System Architecture & Dependency Graph

## 1. System Overview & Ingestion Flow

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        APEXMARKETENGINE DISTRIBUTED PIPELINE                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Local Workstation Data Lakehouse ]                                                   │
│ 01_raw / nepse_data_all CSVs                                                           │
│      │                                                                                 │
│      ▼                                                                                 │
│ [scripts/01_build_master_union.py] (DuckDB Zero-Loss Deduplication)                    │
│      │                                                                                 │
│      ▼                                                                                 │
│ 02_processed_parquet/market_master_union.parquet                                       │
│      │ (644,188 rows, 415 tickers, 2003-06-06 to 2026-10-02)                           │
│      ▼                                                                                 │
│ [scripts/02_feature_engineering.py] (FracDiff d=0.35, Lagged Technicals, News Sent)   │
│      │                                                                                 │
│      ▼                                                                                 │
│ 03_feature_store/technical_indicators.parquet                                          │
│      │                                                                                 │
│      ▼                                                                                 │
│ [scripts/03_train_and_backtest.py] (LightGBM Ranker + Random Forest Meta-Labeler)       │
│      │                                                                                 │
│      ▼                                                                                 │
│ Top-10 Forecasts + Headless 2.0σ Corridor PNG + Historical Disclosures (Cutoff <= t)   │
│      │                                                                                 │
│      ▼ Composite SHA-256 Provenance Seal: H_master = SHA256(Ctx:Fcst:Disc:Vis)        │
│ [scripts/33_clef_inference_bridge.py]                                                  │
│      │                                                                                 │
│      ▼ (POST /synthesize via Cloudflare HTTPS Tunnel - 8.42s RTT)                      │
│ ┌────────────────────────────────────────────────────────────────────────────┐         │
│ │ Remote GPU Worker: Google Colab / GCP (NVIDIA Tesla T4 - 16 GB VRAM)       │         │
│ │ Backbone: Qwen/Qwen2.5-VL-3B-Instruct (Vision-Language Transformer)        │         │
│ │ Fine-Tuned Adapter: PEFT/LoRA (r=16, α=32, 65 MB Weights Attached)         │         │
│ └─────────────────────────────────────┬──────────────────────────────────────┘         │
│                                       │                                                │
│                                       ▼ Pydantic v2 Validation & Circuit Breaker       │
│ [scripts/04_streamlit_terminal_ui.py] (Port 8501 Dashboard) ──► NEPSE TMS Orders       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Inventory & Data Lineage

| Component / File | Purpose & Role | Status / Audit Finding |
| :--- | :--- | :--- |
| `01_raw/ticker_csvs/*.csv` | Master ticker daily OHLCV dumps | 517 CSV files, unadjusted historical data |
| `nepse_data_all/*.csv` | Daily floor sheets (2024–2026) | Expanded ground truth up to Oct 2, 2026 |
| `02_processed_parquet/market_master_union.parquet` | DuckDB unified Parquet store | Clean deduplicated OHLCV dataset |
| `scripts/init_duckdb.py` | DuckDB schema & zero-copy view provisioner | Sets up `news_and_events` & `market_analytics` |
| `scripts/01_build_master_union.py` | Ingestion script | Validated 0-row loss deduplication |
| `scripts/02_feature_engineering.py` | Feature store generator | FFD ($d=0.35$), TF-IDF, News Sentiment |
| `scripts/03_train_and_backtest.py` | Model training & backtest engine | CPCV Folds, LightGBM Ranker + Meta-Labeler |
| `scripts/17_institutional_ic_audit.py` | Forensic IC & permutation audit | Correct backward adjustment, 100-perm null |
| `scripts/33_clef_inference_bridge.py` | Remote Cloudflare tunnel & circuit breaker bridge | 8.42s latency, composite SHA-256 validation |
| `scripts/35_train_clef_lora_t4.py` | Local / T4 GPU LoRA fine-tuning runner | FP16 PEFT ($r=16, \alpha=32$), ~10.4 GB VRAM |
| `notebooks/35_colab_train_clef_lora.py` | 1-Click Google Colab T4 training notebook | Mounts 65 MB adapter to `/synthesize` |
| `tests/test_clef_integration.py` | 11-test automated circuit breaker suite | 100% PASS across edge cases & fail-closed |
| `config.yaml` | System configuration file | Locked capital, fees, CGT (7.5%), ADV cap (5%) |

---

## 3. Code Hygiene & Dead Code Inventory

1. **Active Pipeline:** `scripts/01_build_master_union.py` $\to$ `scripts/02_feature_engineering.py` $\to$ `scripts/17_institutional_ic_audit.py`.
2. **Dead / Legacy Files:**
   * `scripts/02_modeling_and_calculations/04_run_end_to_end_ml_pipeline.py`: Legacy pipeline using unlagged features and unadjusted prices (DEPRECATED).
   * `scripts/02_modeling_and_calculations/02_backtest_nepse_trading_strategies.py`: Legacy backtester using $t+0$ close fills (DEPRECATED).
3. **Hardcoded Constants:**
   * Legacy scripts hardcoded annual trading days to 365 or 252 instead of NEPSE's ~240 trading days.

---

## 4. Blueprint vs. State Paradigm (Version Control vs. Local Storage)

This framework strictly separates the reproducible logic of the NEPSE terminal (version control) from heavy state and secrets (local storage).

### GitHub: The Blueprint (Code & Configuration)
The remote repository is strictly reserved for lightweight (~851 KB), reproducible application logic. Anyone cloning the repository receives this exact skeleton, ready to be hydrated with data.

| Component | Purpose | Examples in Project |
| :--- | :--- | :--- |
| **Core Architecture** | API frameworks and computation logic | Starlette ASGI routes, Python vectorization engines, model schemas |
| **Data Pipelines** | Scripts that fetch and process data, but not the data itself | Scraper scripts, DuckDB ingestion logic, data reconciliation directives |
| **Configuration** | Dependency locking and Git rules | `requirements.txt`, `.gitignore`, `.gitattributes` |
| **Documentation** | System design and instructions | `README.md`, Mermaid architecture diagrams, `CALCULATIONS_INDEX.md` |

### Local Environment: The State (Data, Secrets & Cache)
The local machine handles heavy data loads, sensitive credentials, and compiled runtime state. These files are excluded via `.gitignore` and never leave the local environment.

| Component | Purpose | Examples in Project |
| :--- | :--- | :--- |
| **Raw Data** | Unprocessed feeds and historical archives | `01_raw/`, `nepse_lakehouse/`, `nepse_data_all/` |
| **Processed Analytics** | Feature stores and vectorized outputs | `03_feature_store/`, `02_processed_parquet/`, DuckDB files (`.duckdb`), large `.json`/`.csv` outputs |
| **Secrets** | API keys, passwords, and environment configurations | `.env` file |
| **Runtime Cache** | Virtual environments and compiled byte code | `.venv/`, `__pycache__/`, `.pyc` files, `.pytest_cache/` |

### The Hydration Workflow
Because the GitHub repository serves as a lightweight blueprint, bridging the gap between Git and local execution relies on automated hydration:
1. Clone the repository and install frozen dependencies (`pip install -r requirements.txt`).
2. Run database initialization (`python scripts/init_duckdb.py`) to create schemas and zero-copy views.
3. Ingest raw market feeds or scrapers to populate `nepse_lakehouse/` and raw directories.
4. Execute the pipeline (`python scripts/run_all_pipelines.py`) to build Parquet stores and feature sets.

---

## 5. 10-Phase Sovereign Quant Pipeline Lifecycle

ApexMarketEngine's end-to-end execution follows a rigorous 10-phase progression:

| Phase | Designation | Functional Scope & Computational Subsystems | Key Outputs / Artifacts |
| :---: | :--- | :--- | :--- |
| **01** | **Raw Lakehouse Ingestion** | Ingestion of raw floorsheets (2003–2026), brokerage tick feeds, circulars | `01_raw/`, `nepse_data_all/*.csv` |
| **02** | **Feature Store Mesh** | Fractional Differentiation ($d=0.35$), technical indicators, TextBlob NLP | `03_feature_store/technical_indicators.parquet` |
| **03** | **Combinatorial Modeling** | CPCV Purged K-Fold validation, LightGBM cross-sectional ranking engine | Out-of-fold validation scores, feature SHAP |
| **04** | **Forecasting & Meta-Labeling** | Triple-barrier labeling ($2.0\sigma$ bounds, 5-day horizon), RF meta-labeler | `NEPSE_OCT5_PREDICTION.json` |
| **05** | **Visual Corridor Generation** | Headless Matplotlib Agg rendering of dynamic $\pm 2.0\sigma$ bands | In-memory Base64 PNG bytes (zero host leakage) |
| **06** | **Provenance Sealing** | Strict time-cutoff news queries ($t \le t_{\text{as\_of}}$), SHA-256 composite seal | $\mathbf{H_{master}} = \text{SHA256}(Ctx:Fcst:Disc:Vis)$ |
| **07** | **Cloudflare Tunnel Inference** | Encrypted HTTPS tunnel dispatch to remote GPU FastAPI runtime | 8.42s latency, `ClefToNepseOutputPayload` |
| **08** | **Stratified Dataset Generation**| 130-pair 3-regime stratified dataset preparation for domain fine-tuning | `data/clef_train.jsonl` (109), `data/clef_val.jsonl` (21) |
| **09** | **PEFT / LoRA Fine-Tuning** | Parameter-efficient tuning on Google Colab T4 GPU (FP16, $r=16, \alpha=32$) | `models/clef_nepse_lora_adapter/` (65 MB) |
| **10** | **Terminal UI & TMS Execution** | 3-Tier progressive disclosure dashboard, human audit, TMS order dispatch | Streamlit Terminal UI (`:8501`), NEPSE TMS |

---

## 6. CLEF Multimodal Inference Bridge & Cloudflare Tunnel Protocol

The client bridge (`scripts/33_clef_inference_bridge.py`) mediates between the local desktop quant engine and the remote GPU server:

* **Tunnel Endpoint:** Cloudflare Encrypted HTTPS Tunnel (`trycloudflare.com`). Bypasses corporate NAT and dynamic IP hurdles without opening public inbound router ports.
* **Payload Footprint:** Exactly 130,002 bytes formatted into canonical JSON containing:
  - `metadata`: Schema version `v1.0.0`, client engine ID, request timestamp, and unique `request_id`.
  - `market_context`: Regime enum (`MEAN_REVERSION_BUY_DIP`), index close (2,588.40), projected corridor bounds ($[2574.00, 2615.50]$).
  - `top_10_forecasts`: Ranked candidate array with forward return projections and volatility metrics.
  - `relevant_disclosures`: Historical news items verified strictly on or before the market close cutoff.
  - `visual_artifact`: Base64-encoded PNG chart bytes with MD5 image checksum.
* **Live Latency Profile:**
  - Ingestion & Payload Packing: $\sim 45\text{ ms}$
  - Cloudflare Tunnel Ingress & Egress: $\sim 380\text{ ms}$
  - ViT Image Tokenization & LLM Cross-Attention: $\sim 7,950\text{ ms}$
  - Pydantic v2 Client Validation: $\sim 45\text{ ms}$
  - **Total Measured Round-Trip Time (RTT):** **8.42 seconds**

---

## 7. Cryptographic Provenance Contract & Fail-Closed Circuit Breaker

To prevent hallucinated data or compromised network responses from influencing trading execution, the bridge enforces an immutable cryptographic contract:

### 1. Composite Master Hash
The payload computes 4 sub-hashes across discrete data partitions, sealed by a master composite hash:

$$\mathbf{H_{master} = \text{SHA256}\Big(\text{SHA256}(Ctx) \,\|\, \text{SHA256}(Fcst) \,\|\, \text{SHA256}(Disc) \,\|\, \text{SHA256}(Vis)\Big)}$$

### 2. Zero Host File Leakage
The visual chart is encoded directly into memory as a Base64 string. Local paths (`C:\Users\...`) are never transmitted, preventing host directory structure leakage.

### 3. Canonical Schema Validation
Both input and output schemas enforce Pydantic v2 `extra='forbid'`, rejecting unmodeled keys, floating-point NaN/Inf leaks, or protocol drift.

### 4. Fail-Closed Circuit Breaker State Transition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CIRCUIT BREAKER EXECUTION MATRIX                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Check Network Connectivity & CLEF_BASE_URL                               │
│    └─► UNCONFIGURED / ERROR ──► FAIL-CLOSED (Write Failure Report & Abort)  │
│                                                                             │
│ 2. Dispatch HTTPS POST (Timeout = 45.0s)                                    │
│    └─► TIMEOUT / HTTP != 200 ──► FAIL-CLOSED (Emit Warning & Revert Local)  │
│                                                                             │
│ 3. Pydantic v2 Schema Validation                                            │
│    └─► VALIDATION ERROR ───────► FAIL-CLOSED (Reject Remote Artifact)       │
│                                                                             │
│ 4. Request ID Echo & Master Provenance Hash Audit                           │
│    └─► HASH MISMATCH ──────────► FAIL-CLOSED (Tampering Guard Tripped)      │
│                                                                             │
│ 5. Verified Success: Persist static_data/clef_analyst_report.json (PASS)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

When a failure is tripped, the engine persists `static_data/clef_failure_report.json` with detailed diagnostics and gracefully degrades to **deterministic numerical-only execution**, guaranteeing zero unverified trading actions.

---

## 8. Remote GPU Worker Specifications & LoRA Adapter Configuration

The remote inference server runs as an asynchronous FastAPI application on Google Colab / GCP compute:

* **GPU Hardware:** NVIDIA Tesla T4
  - VRAM: 16 GB GDDR6
  - Memory Bandwidth: 300 GB/sec
  - Tensor Cores: 320 Turing Tensor Cores (65 TFLOPS FP16)
* **Serving Framework:** FastAPI + Uvicorn with FP16 half-precision CUDA execution.
* **PEFT / LoRA Hyperparameters:**
  - Rank: $r = 16$, Alpha: $\alpha = 32$, Dropout: $0.05$.
  - Target Linear Modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`.
  - Gradient Checkpointing: Active (caps backprop memory at $\sim 10.4\text{ GB}$, fitting comfortably in the 16 GB T4 VRAM).
  - Adapter Footprint: **65 MB** (`adapter_model.safetensors`), allowing instant hot-swapping across market regimes without restarting the base model.


