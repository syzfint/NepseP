import os
import sys
import base64
import urllib.request
import json

OUTPUT_DIR = r"c:\Users\achar\Downloads\neps\figures\architecture"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DIAGRAMS = {
    "fig1_end_to_end_system_architecture": """flowchart TD
    subgraph S1["1. INGESTION & DATA LAKE"]
        D1["Raw Ticker Daily CSVs (663 Tickers)"]
        D2["Floor Sheet Order Book Trades (2021-2026)"]
        D3["SEBON / Corporate Action Notices"]
        DUCK["DuckDB Schema Normalizer & Deduplicator"]
        PARQ[("market_master_union.parquet<br/>644,188 Point-in-Time Rows")]
        D1 & D2 & D3 --> DUCK --> PARQ
    end

    subgraph S2["2. CORPORATE ACTION & FEATURE STORE"]
        ADJ["Backward Adjustment Engine<br/>P_adj = P_raw * PROD(f_ex)"]
        ZERO_LEAK["Zero-Leakage Shift(1) Guard"]
        FEAT["Feature Store<br/>- 1-Week Mean-Reversion (-ret_1w)<br/>- 20-Day Realized Volatility<br/>- Butt et al. LR3 Distress Liquidity<br/>- Broker Buyer/Seller Concentration"]
        PARQ --> ADJ --> ZERO_LEAK --> FEAT
    end

    subgraph S3["3. ALPHA ENGINE & PORTFOLIO SIZING"]
        ALPHA["Cross-Sectional Ranker & Scoring Engine"]
        FILTER["Top Decile (Top 10%) Filtering"]
        SIZE["Equal/Risk-Parity Weighting"]
        ADV_CAP["5% ADV Liquidity Participation Cap"]
        FEAT --> ALPHA --> FILTER --> SIZE --> ADV_CAP
    end

    subgraph S4["4. EXECUTION SIMULATOR & FRICTIONS"]
        EXEC["Open(t+1) Realistic Fill Model"]
        FRICTION["NEPSE Microstructure Friction Engine<br/>- Tiered Broker Comm: 0.40% to 0.27%<br/>- SEBON Regulatory Fee: 0.015%<br/>- DP Demat Fee: NPR 25/txn<br/>- CGT: 7.5% Realized Profit"]
        ADV_CAP --> EXEC --> FRICTION
    end

    subgraph S5["5. PERFORMANCE & FORENSIC AUDIT"]
        EQUITY["Out-of-Sample Equity Curve & Tearsheet"]
        AUDIT["10-Gate Audit Harness (G0 to G10)"]
        FRICTION --> EQUITY --> AUDIT
    end
""",

    "fig2_point_in_time_leakage_guard": """flowchart LR
    subgraph T_MINUS_20["Lookback Window: t-20 to t-2"]
        ADV["20-Day Rolling ADV & Volatility Calculation<br/>(Strictly Past Information)"]
    end

    subgraph T_MINUS_1["Feature Cutoff: t-1 (Close of Market)"]
        CLOSE["Close(t-1), Volume(t-1), High/Low(t-1)"]
        INDICATORS["Indicators & Z-Scores Computed"]
        SHIFT["Mandatory .shift(1) Boundary<br/>Zero Forward Information Leakage"]
        CLOSE --> INDICATORS --> SHIFT
    end

    subgraph T_DAY["Decision Epoch: Day t"]
        DECISION["Signal Score Computed at Close(t-1)<br/>Target Portfolio Weights Assigned"]
        ADV_BOUND["Liquidity Bounded against Past ADV"]
        DECISION --> ADV_BOUND
    end

    subgraph T_PLUS_1["Execution Epoch: Day t+1"]
        FILL["Order Fill at Open(t+1)<br/>No Intraday t Cheating"]
        FEES["Deduction of SEBON, Broker, DP Fees"]
        FILL --> FEES
    end

    subgraph T_PLUS_5["Forward Label Epoch: t+5"]
        LABEL["Forward Realized Return Label<br/>FORBIDDEN in Feature Calculations"]
    end

    ADV --> CLOSE
    SHIFT --> DECISION
    ADV_BOUND --> FILL
    FEES -.-> LABEL
""",

    "fig3_signal_generation_alpha_engine": """flowchart TD
    subgraph RAW["Market Inputs"]
        P["Adjusted Close Prices"]
        V["Trading Volume & Turnover"]
        F["Broker Floor Sheet Trans"]
    end

    subgraph FACTORS["Multi-Factor Generation"]
        F1["Factor 1: 1-Week Reversal<br/>-ret_1w = -(P_t-1 / P_t-6 - 1)"]
        F2["Factor 2: Volatility Filter<br/>1 / Vol_20d (Inverse Realized Vol)"]
        F3["Factor 3: Distress Liquidity (LR3)<br/>Spread / Illiquidity Shock"]
        F4["Factor 4: Top-3 Broker Imbalance<br/>(Buy Vol - Sell Vol) / Total Vol"]
        P --> F1
        P --> F2
        V --> F3
        F --> F4
    end

    subgraph COMPOSITE["Alpha Synthesis & Ranking"]
        Z["Cross-Sectional Winsorization & Z-Scoring"]
        W["Weighted Linear / Non-Linear Ensemble"]
        RANK["Daily Cross-Sectional Percentile Rank (0.0 to 1.0)"]
        F1 & F2 & F3 & F4 --> Z --> W --> RANK
    end

    subgraph SELECTION["Portfolio Construction"]
        DECILE["Select Top Decile (Rank >= 0.90)"]
        CAP_LIMIT["Cap Max Single Position <= 10% NAV"]
        WEIGHTS["Final Target Weights w_i(t)"]
        RANK --> DECILE --> CAP_LIMIT --> WEIGHTS
    end
""",

    "fig4_execution_liquidity_friction_engine": """flowchart TD
    subgraph SIZING["1. Sizing & Liquidity Bounding"]
        TARGET["Target Position Delta: dW_i"]
        SHARES["Raw Desired Shares to Transact"]
        ADV_FILTER["Historical 20-Day ADV"]
        CAP["Liquidity Cap Enforcement:<br/>Shares <= 5% * ADV_20d"]
        TARGET --> SHARES
        ADV_FILTER & SHARES --> CAP
    end

    subgraph EXEC["2. Execution Simulation"]
        FILL_PRICE["Execution Price: Open(t+1)<br/>(Slip model: Open * (1 +/- Slippage))"]
        TURNOVER["Trade Value NPR: Shares * Fill_Price"]
        CAP --> FILL_PRICE --> TURNOVER
    end

    subgraph FRICTIONS["3. NEPSE Institutional Friction Deductions"]
        B_TIER["Tiered Broker Commission:<br/>- <= 50k: 0.40%<br/>- 50k - 500k: 0.37%<br/>- 500k - 2000k: 0.34%<br/>- 2000k - 10000k: 0.30%<br/>- > 10000k: 0.27%"]
        SEBON["SEBON Regulatory Fee: 0.015%"]
        DP["CDSC / DP Demat Fee: NPR 25 per Scrip"]
        CGT["Capital Gains Tax: 7.5% on Net Realized Profit"]
        TURNOVER --> B_TIER & SEBON & DP & CGT
    end

    subgraph NET["4. Net Settlement & Cash Ledger"]
        SETTLE["Net Cash Flow Deduction from Portfolio NAV"]
        B_TIER & SEBON & DP & CGT --> SETTLE
    end
""",

    "fig5_forensic_gates_audit_harness": """flowchart TD
    subgraph STAGE1["Data Integrity & Leakage Gates"]
        G0["Gate G0: Data Truth<br/>644k Rows, 0 Duplicates, Clean Tickers"]
        G1["Gate G1: Point-in-Time Leakage<br/>Shift(1) Truncation Delta = 0.000000"]
        G2["Gate G2: Corporate Action Multiplier<br/>Adjustment Formula & Split Precision"]
        G0 --> G1 --> G2
    end

    subgraph STAGE2["Signal & Benchmark Baseline"]
        G3["Gate G3: Information Coefficient<br/>Composite IC = +0.0217, t-stat = 4.13"]
        G4["Gate G4: Benchmark Integrity<br/>Equal-Weight Index & Market Drift"]
        G2 --> G3 --> G4
    end

    subgraph STAGE3["Microstructure & Liquidity Gates"]
        G5["Gate G5: Microstructure Frictions<br/>Broker, SEBON, DP & CGT Audit"]
        G6["Gate G6: Capacity & Execution<br/>Open(t+1) Fill & 5% ADV Capacity"]
        G4 --> G5 --> G6
    end

    subgraph STAGE4["Statistical Validation & Holdout"]
        G7["Gate G7: Combinatorial Purged CV<br/>CPCV Embargo & Overlap Removal"]
        G8["Gate G8: Complexity Ablation<br/>Factor Baseline vs Model Complexity"]
        G9["Gate G9: Probability of Backtest Overfitting<br/>PBO = 11.2%, Deflated Sharpe Ratio"]
        G10["Gate G10: Untouched OOS Holdout<br/>Final Lockbox Validation (+7.41% Ret, 0.74 Sharpe)"]
        G6 --> G7 --> G8 --> G9 --> G10
    end
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
        with urllib.request.urlopen(req, timeout=25) as response:
            data = response.read()
            with open(png_path, "wb") as f_out:
                f_out.write(data)
            print(f"Successfully saved {png_path} ({len(data)} bytes)")
    except Exception as e:
        print(f"Failed to generate {name}: {e}")

if __name__ == "__main__":
    for name, mmd in DIAGRAMS.items():
        render_diagram(name, mmd)
    print("All diagrams processed successfully.")
