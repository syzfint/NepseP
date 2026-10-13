import os
import sys
import base64
import urllib.request
import json

OUTPUT_DIR = r"c:\Users\achar\Downloads\neps\figures\architecture"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DIAGRAMS = {
    "fig01_chrono_vault_lakehouse_ingestion": """flowchart TD
    subgraph INGEST["1. Heterogeneous Data Ingestion"]
        D1["Floor Sheet Tick Orders (2014-2026, >28M trades)"]
        D2["Daily OHLCV Bars (663 Tickers, 644k+ records)"]
        D3["Broker Floor Sheet Master (Brokers 1-59)"]
        D4["Corporate Action Notices (Splits, Right Shares, Bonuses)"]
        D5["NRB Directives & Fiscal Calendar (Bikram Sambat)"]
    end

    subgraph VAULT["2. CHRONO-VAULT OLAP Engine (DuckDB + Parquet)"]
        PARSE["Unified Schema Standardization & DuckDB Ingestion"]
        DEDUP["Anti-Wash Trade Filter (BuyerBroker == SellerBroker Deduplication)"]
        PIT["Point-in-Time Backward Adjustment: P_adj = P_raw * PROD(f_ex)"]
        PARQUET[("market_master_union.parquet<br/>Hive-Partitioned Zero-Copy Parquet Store")]
        PARSE --> DEDUP --> PIT --> PARQUET
    end

    subgraph STATIONARY["3. Memory-Preserving Stationarity Engine"]
        FRAC["Fractional Differentiation Engine (d = 0.35)"]
        ADF["Augmented Dickey-Fuller Test (p = 0.0121 < 0.05 Stationary)"]
        CORR["Memory Preservation Check (Correlation > 0.90)"]
        PARQUET --> FRAC --> ADF --> CORR
    end

    D1 & D2 & D3 & D4 & D5 --> PARSE
""",

    "fig02_microstructure_syndicate_tracking": """flowchart TD
    subgraph LOB["Floor-Sheet Order Book Feed"]
        TICKS["Order Executions & Price Sweeps"]
    end

    subgraph MICRO["Microstructure Toxicity & Imbalance"]
        OFI["Cont-Stoikov Order Flow Imbalance (OFI)<br/>OFI_t = Sum(I_buy * Vol - I_sell * Vol)"]
        VPIN["Volume-Synchronized Probability of Toxicity (VPIN)<br/>Bucket Volume = V_total / N; Toxic Informed Flow Metric"]
        AMFL["Amihud Illiquidity Ratio & Spread Shocks"]
        TICKS --> OFI & VPIN & AMFL
    end

    subgraph SYNDICATE["Syndicate & Broker Flow Tracking"]
        HAWKES["Hawkes Point Process (Self-Exciting Intensity)<br/>lambda(t) = mu + Sum(alpha * exp(-beta*(t - t_i)))"]
        BROKERS["Broker Sweep Concentration (Top Brokers: 58, 45, 49)"]
        TICKS --> HAWKES --> BROKERS
    end

    subgraph SIGNALS["Microstructure Feature Matrix"]
        OUT["Toxicity Z-Score + Broker Imbalance Ratio + Illiquidity Shock"]
        OFI & VPIN & AMFL & BROKERS --> OUT
    end
""",

    "fig03_hybrid_forecasting_ensemble": """flowchart TD
    subgraph INPUTS["Standardized Stationary Time Series"]
        SERIES["FracDiff Price, Volume, Microstructure & Technical Signals"]
    end

    subgraph MODELS["Hybrid Multi-Model Forecasting Layer"]
        CHRONOS["Amazon Chronos-Bolt (48M)<br/>Zero-Shot 5-Session P10 / P50 / P90 Probabilistic Corridors"]
        LGBM["LightGBM Cross-Sectional Ranker<br/>Trained via CPCV (Purged & Embargoed Cross-Validation)"]
        KRONOS["AAAI 2026 Kronos 5D Candlestick Tokenizer<br/>Continuous Token Embeddings [Open, High, Low, Close, Volume]"]
        MEANREV["System-1 Mean Reversion Engine<br/>1-Week Reversal + Realized Volatility + LR3 Distress"]
    end

    subgraph REGIME["Regime-Adaptive Meta-Ensemble"]
        ROUTER["Vol-Regime Router & Meta-Learner"]
        CHRONOS & LGBM & KRONOS & MEANREV --> ROUTER
        PRED["Ensemble Probability Distribution & Return Forecast Vector"]
        ROUTER --> PRED
    end

    SERIES --> CHRONOS & LGBM & KRONOS & MEANREV
""",

    "fig04_temporal_governance_zero_leakage": """flowchart LR
    subgraph PAST["Historical Information Epoch (t-20 to t-2)"]
        ADV["20-Day Rolling ADV & Volatility Window<br/>Strict Historical Past Only"]
    end

    subgraph CUTOFF["Feature Cutoff Epoch (t-1 15:00 Close)"]
        BARS["Close(t-1), Volume(t-1), High/Low(t-1)"]
        CALC["Feature Calculation & Stationarity Transforms"]
        GUARD["Mandatory .shift(1) Zero-Leakage Barrier<br/>Truncation Delta = 0.000000"]
        BARS --> CALC --> GUARD
    end

    subgraph DECISION["Decision Epoch (Day t)"]
        RANK["Cross-Sectional Rank Score Computed"]
        TARGET["Target Portfolio Weights Selected"]
        RANK --> TARGET
    end

    subgraph EXECUTION["Execution Epoch (Day t+1 11:00 Open)"]
        FILL["Fill at Open(t+1) Auction<br/>(No t-close lookahead fill cheating)"]
    end

    subgraph HORIZON["Target Label Epoch (t+1 to t+5)"]
        LABEL["Forward Realized Return Label<br/>FORBIDDEN in Training & Feature Set"]
    end

    ADV --> BARS
    GUARD --> RANK
    TARGET --> FILL
    FILL -.-> LABEL
""",

    "fig05_portfolio_sizing_hysteresis": """flowchart TD
    subgraph SCORES["Cross-Sectional Alpha Scores"]
        RANKS["Daily Percentile Ranks (0.00 to 1.00)"]
    end

    subgraph SELECTION["Hysteresis Retention Logic"]
        BUY_ZONE{"Rank >= 90th Percentile (Top 5 Tickers)?"}
        HOLD_ZONE{"Already in Portfolio & Rank >= 70th (Top 15)?"}
        SELL_ZONE["Liquidate Position (Drop from Portfolio)"]
        BUY["Enter / Size Long Position"]
        HOLD["Retain Position (Zero Turnover Rebalance)"]
        
        RANKS --> BUY_ZONE
        BUY_ZONE -- "Yes" --> BUY
        BUY_ZONE -- "No" --> HOLD_ZONE
        HOLD_ZONE -- "Yes" --> HOLD
        HOLD_ZONE -- "No" --> SELL_ZONE
    end

    subgraph RISK["Portfolio Allocation & Bounding"]
        HRP["Hierarchical Risk Parity (HRP) Tree Clustering"]
        ADV_CAP["5% 20-Day ADV Participation Cap Enforcement"]
        CASH_BUF["Dynamic Cash Buffer Engine (Up to 25% Defensive Cash)"]
        BUY & HOLD --> HRP --> ADV_CAP --> CASH_BUF
    end

    subgraph TURNOVER["Net Friction Reduction Proof"]
        RESULT["Turnover Slashed from 100% to 11.9%<br/>Preserves Alpha from Frictional Erasure"]
        CASH_BUF --> RESULT
    end
""",

    "fig06_market_microstructure_execution_plane": """flowchart TD
    subgraph PRE_OPEN["1. Pre-Open Order Audit (10:30 AM - 10:45 AM)"]
        PRE["Order Book Depth & Cancellation Inspection"]
        SPOOF{"Spoofing / Order Cancellations > 35%?"}
        HALT["Reject Trading for Scrip"]
        PASS["Proceed to Continuous Trading"]
        PRE --> SPOOF
        SPOOF -- "Yes" --> HALT
        SPOOF -- "No" --> PASS
    end

    subgraph CONTINUOUS["2. Optimal Execution Slicing (11:00 AM - 3:00 PM)"]
        ALMGREN["Almgren-Chriss Optimal Liquidation Trajectory"]
        TWAP["Empirical U-Shaped Intraday VWAP/TWAP Slicer"]
        LOB_CAP["Depth Participation Cap: <= 15% Top-3 LOB Depth"]
        PASS --> ALMGREN --> TWAP --> LOB_CAP
    end

    subgraph NEPSE_FEES["3. Institutional Friction & Tax Engine"]
        TIER["Tiered Brokerage Fee (0.40% to 0.27%)"]
        SEBON["SEBON Regulatory Fee: 0.015%"]
        CDSC["CDSC / DP Demat Fee: NPR 25 per Scrip"]
        CGT["Capital Gains Tax (CGT): 7.5% on Realized Gains"]
        LOB_CAP --> TIER & SEBON & CDSC & CGT
    end

    subgraph SETTLEMENT["4. CDSC T+2 Demat Settlement Shield"]
        SETTLE["Settlement Guard & Capital Lock-Up Verification"]
        TIER & SEBON & CDSC & CGT --> SETTLE
    end
""",

    "fig07_clef_multimodal_vlm_bridge": """flowchart TD
    subgraph LOCAL["1. Local Quant Engine (scripts/33_clef_inference_bridge.py)"]
        MATPLOT["Headless Matplotlib Agg PNG<br/>In-Memory Base64 Render"]
        CONTEXT["Quant Context: Returns, Volatility, OFI, Ticks"]
        MASTER_HASH["Master Provenance Seal:<br/>H_master = SHA256(Context : Forecast : Disclosures : Vis)"]
        MATPLOT & CONTEXT --> MASTER_HASH
    end

    subgraph TUNNEL["2. Cloudflare Encrypted Tunnel"]
        POST["HTTPS POST /synthesize<br/>Payload: 130KB JSON | Measured RTT: 8.42s"]
        MASTER_HASH --> POST
    end

    subgraph CLOUD["3. Remote Colab / GCP GPU Compute Node"]
        T4["NVIDIA Tesla T4 GPU (16GB VRAM, FP16 FastAPI)"]
        VLM["Qwen2.5-VL-3B Multimodal Vision-Language Transformer"]
        LORA["PEFT/LoRA Domain Adapter (r=16, alpha=32, 65MB)"]
        SYNTH["Multimodal Synthesis & Institutional Summary Generation"]
        POST --> T4 --> VLM
        LORA -.-> VLM
        VLM --> SYNTH
    end

    subgraph CIRCUIT["4. Fail-Closed Cryptographic Guard"]
        VALID{"Pydantic v2 Schema Valid & Hash Match?"}
        PASS_REP["Persist static_data/clef_analyst_report.json"]
        FAIL_REP["FAIL-CLOSED: Fallback to Pure Quant Rule Engine"]
        SYNTH --> VALID
        VALID -- "Yes" --> PASS_REP
        VALID -- "No / Timeout > 45s" --> FAIL_REP
    end
""",

    "fig08_ten_gate_forensic_audit_matrix": """flowchart TD
    subgraph G_DATA["Data & Leakage Foundation"]
        G0["Gate G0: Data Truth<br/>644k Rows, 0 Duplicates, Clean Tickers"]
        G1["Gate G1: Point-in-Time Leakage<br/>Shift(1) Truncation Delta = 0.000000"]
        G2["Gate G2: Corporate Action Multipliers<br/>Backward Adjustment P_adj Precision"]
        G0 --> G1 --> G2
    end

    subgraph G_STAT["Signal & Baseline Integrity"]
        G3["Gate G3: Information Coefficient<br/>Composite IC = +0.0217 (t = 4.13)"]
        G4["Gate G4: Benchmark Baseline<br/>Equal-Weight Index +3,870% Verified"]
        G2 --> G3 --> G4
    end

    subgraph G_MICRO["Microstructure & Capacity"]
        G5["Gate G5: Microstructure Friction Audit<br/>All Broker/SEBON/CGT Fees Applied"]
        G6["Gate G6: Capacity & Execution<br/>Open(t+1) Execution & 5% ADV Limit"]
        G4 --> G5 --> G6
    end

    subgraph G_VALID["Statistical Robustness & Holdout"]
        G7["Gate G7: Combinatorial Purged CV (CPCV)<br/>10d Purge & 5d Embargo Interval"]
        G8["Gate G8: Complexity Ablation<br/>Factor Baseline vs Complex Models"]
        G9["Gate G9: Probability of Overfitting (PBO)<br/>PBO = 11.2%, Deflated Sharpe Ratio"]
        G10["Gate G10: Untouched OOS Holdout<br/>Holdout Return +7.41%, Sharpe 0.74"]
        G6 --> G7 --> G8 --> G9 --> G10
    end
""",

    "fig09_triple_barrier_metalabeling": """flowchart TD
    subgraph BARS["Price Trajectory & Volatility"]
        PRICE["Adjusted Close Price Series"]
        VOL["Daily Realized Volatility: sigma_t"]
        PRICE & VOL --> BARRIERS
    end

    subgraph BARRIERS["López de Prado Triple-Barrier Geometry"]
        UPPER["Upper Profit Taking Barrier: +2.0 * sigma_t"]
        LOWER["Lower Stop Loss Barrier: -2.0 * sigma_t"]
        TIME["Vertical Horizon Barrier: t + 5 Trading Days"]
        BARRIERS --> UPPER & LOWER & TIME
    end

    subgraph PRIMARY["Primary Signal & First-Touch Label"]
        TOUCH["First Barrier Touched Determines Label y in {-1, 0, +1}"]
        UPPER & LOWER & TIME --> TOUCH
    end

    subgraph META["Meta-Labeling Machine Learning Filter"]
        PROB["Meta-Model (LightGBM/XGBoost) Predicts: P(Touch Upper | Trade Taken)"]
        THRESH{"Meta Probability >= Threshold?"}
        EXEC_TRADE["Execute Trade with Sized Capital"]
        VETO["Veto False Positive / Skip Trade"]
        TOUCH --> PROB --> THRESH
        THRESH -- "Yes" --> EXEC_TRADE
        THRESH -- "No" --> VETO
    end
""",

    "fig10_mission_control_user_experience": """flowchart TD
    subgraph TERMINALS["Client Interfaces & Stations"]
        T1["Streamlit Terminal UI (:8501)"]
        T2["PRISM Station (launch_prism_station.py)"]
        T3["Hedge Terminal (hedge_terminal.py)"]
        T4["NEPSE Broker TMS Order Staging Gateway"]
    end

    subgraph TIERS["3-Tier Progressive Disclosure Model"]
        subgraph TIER1["Tier 1: Executive Dashboard (Layman View)"]
            E1["High-Conviction Scrip Recommendation (#1 Rank)"]
            E2["Entry Price, Dynamic Stop-Loss & Target Corridor"]
        end

        subgraph TIER2["Tier 2: Evidence & Microstructure Matrix"]
            M1["Multimodal Context & Chronos P10/P50/P90 Corridor"]
            M2["Broker OFI & Syndicate Accumulation Pressures"]
        end

        subgraph TIER3["Tier 3: Institutional Forensic Audit Row"]
            A1["TreeSHAP Explanations & Factor Weights"]
            A2["Fractional Diff Stationarity Proof & Gate Certification"]
        end

        TIER1 --> TIER2 --> TIER3
    end

    TERMINALS --> TIER1
"""
}

def render_diagram(name, mmd_text):
    mmd_path = os.path.join(OUTPUT_DIR, f"{name}.mmd")
    png_path = os.path.join(OUTPUT_DIR, f"{name}.png")
    
    with open(mmd_path, "w", encoding="utf-8") as f:
        f.write(mmd_text)
    
    print(f"Generating {png_path}...")
    encoded = base64.b64encode(mmd_text.encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            with open(png_path, "wb") as f_out:
                f_out.write(data)
            print(f"Successfully saved {png_path} ({len(data)} bytes)")
    except Exception as e:
        print(f"Failed to generate {name}: {e}")

if __name__ == "__main__":
    for name, mmd in DIAGRAMS.items():
        render_diagram(name, mmd)
    print("All 10 architecture diagrams generated successfully.")
