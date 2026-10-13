import os
import urllib.request
import base64

OUTPUT_DIR = r"c:\Users\achar\Downloads\neps\figures\architecture"

FIXES = {
    "fig03_hybrid_forecasting_ensemble": """flowchart TD
    subgraph INPUTS["Standardized Stationary Time Series"]
        SERIES["FracDiff Price, Volume, Microstructure & Technical Signals"]
    end

    subgraph MODELS["Hybrid Multi-Model Forecasting Layer"]
        CHRONOS["Amazon Chronos-Bolt (48M)<br/>Zero-Shot 5-Session P10 / P50 / P90 Corridors"]
        LGBM["LightGBM Cross-Sectional Ranker<br/>Trained via CPCV (Purged & Embargoed CV)"]
        KRONOS["AAAI 2026 Kronos 5D Candlestick Tokenizer<br/>Embeddings: Open, High, Low, Close, Volume"]
        MEANREV["System-1 Mean Reversion Engine<br/>1-Week Reversal + Realized Vol + LR3 Distress"]
    end

    subgraph REGIME["Regime-Adaptive Meta-Ensemble"]
        ROUTER["Vol-Regime Router & Meta-Learner"]
        CHRONOS --> ROUTER
        LGBM --> ROUTER
        KRONOS --> ROUTER
        MEANREV --> ROUTER
        PRED["Ensemble Probability Distribution & Return Forecast Vector"]
        ROUTER --> PRED
    end

    SERIES --> CHRONOS
    SERIES --> LGBM
    SERIES --> KRONOS
    SERIES --> MEANREV
""",

    "fig05_portfolio_sizing_hysteresis": """flowchart TD
    subgraph SCORES["Cross-Sectional Alpha Scores"]
        RANKS["Daily Percentile Ranks (0.00 to 1.00)"]
    end

    subgraph SELECTION["Hysteresis Retention Logic"]
        BUY_ZONE{"Rank >= 90th Percentile?"}
        HOLD_ZONE{"In Portfolio & Rank >= 70th?"}
        SELL_ZONE["Liquidate Position"]
        BUY["Enter / Size Long Position"]
        HOLD["Retain Position (Zero Turnover)"]
        
        RANKS --> BUY_ZONE
        BUY_ZONE -->|Yes| BUY
        BUY_ZONE -->|No| HOLD_ZONE
        HOLD_ZONE -->|Yes| HOLD
        HOLD_ZONE -->|No| SELL_ZONE
    end

    subgraph RISK["Portfolio Allocation & Bounding"]
        HRP["Hierarchical Risk Parity (HRP) Tree Clustering"]
        ADV_CAP["5% 20-Day ADV Participation Cap"]
        CASH_BUF["Dynamic Cash Buffer Engine (Up to 25% Defensive Cash)"]
        BUY --> HRP
        HOLD --> HRP
        HRP --> ADV_CAP --> CASH_BUF
    end

    subgraph TURNOVER["Net Friction Reduction Proof"]
        RESULT["Turnover Slashed from 100% to 11.9%<br/>Preserves Alpha from Frictional Erasure"]
        CASH_BUF --> RESULT
    end
""",

    "fig07_clef_multimodal_vlm_bridge": """flowchart TD
    subgraph LOCAL["1. Local Quant Engine"]
        MATPLOT["Headless Matplotlib Agg PNG<br/>In-Memory Base64 Render"]
        CONTEXT["Quant Context: Returns, Volatility, OFI, Ticks"]
        MASTER_HASH["Master Provenance Seal:<br/>H_master = SHA256(Context + Forecast + Disclosures + Vis)"]
        MATPLOT --> MASTER_HASH
        CONTEXT --> MASTER_HASH
    end

    subgraph TUNNEL["2. Cloudflare Encrypted Tunnel"]
        POST["HTTPS POST /synthesize<br/>Payload: 130KB JSON | Measured RTT: 8.42s"]
        MASTER_HASH --> POST
    end

    subgraph CLOUD["3. Remote Colab / GCP GPU Compute Node"]
        T4["NVIDIA Tesla T4 GPU (16GB VRAM, FP16 FastAPI)"]
        VLM["Qwen2.5-VL-3B Multimodal Vision-Language Transformer"]
        LORA["PEFT/LoRA Domain Adapter (r=16, alpha=32, 65MB)"]
        SYNTH["Multimodal Synthesis & Institutional Summary"]
        POST --> T4 --> VLM
        LORA -.-> VLM
        VLM --> SYNTH
    end

    subgraph CIRCUIT["4. Fail-Closed Cryptographic Guard"]
        VALID{"Pydantic v2 Schema Valid & Hash Match?"}
        PASS_REP["Persist static_data/clef_analyst_report.json"]
        FAIL_REP["FAIL-CLOSED: Fallback to Pure Quant Rule Engine"]
        SYNTH --> VALID
        VALID -->|Yes| PASS_REP
        VALID -->|No / Timeout > 45s| FAIL_REP
    end
"""
}

def fix_and_render():
    for name, mmd in FIXES.items():
        mmd_file = os.path.join(OUTPUT_DIR, f"{name}.mmd")
        png_file = os.path.join(OUTPUT_DIR, f"{name}.png")
        
        with open(mmd_file, "w", encoding="utf-8") as f:
            f.write(mmd)
            
        enc = base64.b64encode(mmd.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{enc}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
                with open(png_file, "wb") as f_out:
                    f_out.write(data)
                print(f"{name}: SUCCESS ({len(data)} bytes)")
        except Exception as e:
            print(f"{name}: FAILED ({e})")

if __name__ == "__main__":
    fix_and_render()
