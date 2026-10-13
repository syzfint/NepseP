import os
import urllib.request
import base64

OUTPUT_DIR = r"c:\Users\achar\Downloads\neps\figures\architecture\subsections\frameworks"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FRAMEWORK_DIAGRAMS = {
    "frm01_c4_level1_system_context": """flowchart TD
    subgraph USERS["External Human Actors"]
        PM["Portfolio Manager<br/>[Monitors allocations, risk, and PnL]"]
        QR["Quantitative Researcher<br/>[Develops signals, audits alpha, runs CPCV]"]
        COMP["Compliance Officer<br/>[Audits SEBON rules and capital limits]"]
    end

    subgraph SYSTEM["APEXMARKETENGINE SYSTEM BOUNDARY"]
        CORE["ApexMarketEngine<br/>[Vectorized OLAP lakehouse, hybrid ML forecasting, zero-leakage guards, friction engine, and OMS gateway]"]
    end

    subgraph EXTERNAL["External Third-Party Systems"]
        NEPSE["NEPSE TMS / Exchange<br/>[Floor-sheet tick feeds and order execution]"]
        CDSC["CDSC Demat Clearing House<br/>[T+2 securities clearing and settlement]"]
        NRB["NRB Regulatory Portal<br/>[Fiscal policies, directives, and interest rates]"]
        DATA["External Market Data Vendors<br/>[Historical corporate actions and disclosures]"]
    end

    PM -->|Monitors PnL and triggers de-risking| CORE
    QR -->|Deploys alpha models and inspects gates| CORE
    COMP -->|Inspects audit reports and tax records| CORE

    CORE -->|Fetches real-time ticks and order status| NEPSE
    CORE -->|Submits TWAP/VWAP child orders| NEPSE
    CORE -->|Verifies settlement and Demat transfers| CDSC
    DATA -->|Feeds financial disclosures and splits| CORE
    NRB -->|Provides macro interest and liquidity rates| CORE
""",

    "frm02_wardley_strategy_evolution_map": """flowchart LR
    subgraph VALUE_CHAIN["Quantitative Value Chain (High to Low Visibility)"]
        direction TB
        V1["User Need: Superior Risk-Adjusted Alpha (Sharpe > 1.0)"]
        V2["Forensic Audit Matrix (G0-G10 Certifications)"]
        V3["Microstructure Alpha & OFI Imbalance"]
        V4["Point-in-Time Zero-Leakage Engine"]
        V5["Fractional Differentiation Engine (d=0.35)"]
        V6["CPCV Purged Cross-Validation Harness"]
        V7["Vectorized OLAP Engine (DuckDB / Parquet)"]
        V8["Cloud GPU Compute (NVIDIA T4 / Colab)"]
        V9["Commodity Storage & Host OS"]
    end

    subgraph STAGES["Evolution Axis"]
        direction LR
        S1["Genesis<br/>(Novel Research)"]
        S2["Custom Built<br/>(Proprietary Edge)"]
        S3["Product / Rental<br/>(Standardized Engines)"]
        S4["Commodity / Utility<br/>(Ubiquitous Substrate)"]
    end

    V1 --> S2
    V2 --> S1
    V3 --> S2
    V4 --> S2
    V5 --> S2
    V6 --> S3
    V7 --> S4
    V8 --> S4
    V9 --> S4
""",

    "frm03_causal_loop_system_dynamics": """flowchart TD
    subgraph R_LOOP["Reinforcing Loop (R1: Capital Growth & Scale)"]
        ALPHA["(+) Alpha Signal Quality"] --> TARGET["(+) Target Portfolio Allocation"]
        TARGET --> PROFIT["(+) Cumulative Trading Profit"]
        PROFIT --> NAV["(+) Portfolio NAV / AUM"]
        NAV --> RESEARCH["(+) Compute & Research Reinvestment"]
        RESEARCH --> ALPHA
    end

    subgraph B_LOOP1["Balancing Loop (B1: Market Impact & Friction)"]
        TARGET --> VOL["(+) Trading Order Volume"]
        VOL --> IMPACT["(+) Market Impact & Slippage"]
        IMPACT --> FRICTION["(+) Realized Friction Cost"]
        FRICTION --> NET_P["(-) Net Realized Profit"]
        NET_P --> REBAL["(-) Slower Turnover / Hysteresis Hold"]
        REBAL --> VOL
    end

    subgraph B_LOOP2["Balancing Loop (B2: Alpha Decay / Crowding)"]
        VOL --> CROWD["(+) Broker Syndicate Crowding"]
        CROWD --> DECAY["(-) Factor Predictive Decay"]
        DECAY --> ALPHA
    end
""",

    "frm04_bpmn_business_process_choreography": """flowchart TD
    subgraph POOL_INTERNAL["Internal Strategy & Risk Desk"]
        START((Day t Close: 15:00)) --> GEN_WEIGHTS["Generate Model Target Weights"]
        GEN_WEIGHTS --> RISK_EVAL{"Pre-Trade Risk Checks Passed?"}
        RISK_EVAL -->|No: NAV/ADV Limit| REJECT_INT["Reject / Trim Position"]
        RISK_EVAL -->|Yes| STAGE_ORDER["Stage Orders for Day t+1 Open"]
    end

    subgraph POOL_COMPLIANCE["Pre-Trade Compliance & Regulatory Shield"]
        STAGE_ORDER --> AUDIT_SPOOF{"Pre-Open 10:30-10:45: Cancellations > 35%?"}
        AUDIT_SPOOF -->|Yes: Spoofing Flag| ABORT["Halt Execution on Target Scrip"]
        AUDIT_SPOOF -->|No: Order Book Clean| DISPATCH["Approve Order Dispatch"]
    end

    subgraph POOL_BROKER["External NEPSE Broker TMS & Execution"]
        DISPATCH --> ROUTE["Submit Sliced TWAP/VWAP to Broker TMS"]
        ROUTE --> MATCH{"Matching Engine Response"}
        MATCH -->|Full Fill| REPORT_FILL["Generate Execution Report"]
        MATCH -->|Partial Fill| SLICE_REST["Continue Slicing or Cancel at 14:50"]
        MATCH -->|Rejection / Circuit Breaker| HALT_ALERT["Alert Quant Desk"]
    end

    subgraph POOL_CLEARING["Post-Trade CDSC Demat Clearing"]
        REPORT_FILL --> CDSC_LOCK["Verify T+2 Demat Share Settlement"]
        CDSC_LOCK --> END_OK(((Settlement Finalized)))
    end
""",

    "frm05_dfd_level1_data_flow_diagram": """flowchart TD
    subgraph SOURCES["External Data Entities"]
        E1["NEPSE Floor Sheet Feed"]
        E2["SEBON Corporate Action Notices"]
        E3["Trading Desk Orders"]
    end

    subgraph PROCESSES["Transformations & Core Processes"]
        P1["Process 1.0: Ingestion & Anti-Wash Trade Filter"]
        P2["Process 2.0: Split & Bonus Adjustment Multiplier"]
        P3["Process 3.0: Fractional Differentiation & Lagging (Shift 1)"]
        P4["Process 4.0: Cross-Sectional Alpha Ranker"]
        P5["Process 5.0: Friction Deduction & Execution Sizing"]
    end

    subgraph STORES["Data Stores (Parquet / Memory)"]
        DS1[("D1: Raw Tick Store")]
        DS2[("D2: market_master_union.parquet")]
        DS3[("D3: Feature Store (Stationary Series)")]
        DS4[("D4: Model Registry & Targets")]
        DS5[("D5: Executed Ledger & Net PnL")]
    end

    E1 --> P1
    P1 --> DS1
    DS1 --> P2
    E2 --> P2
    P2 --> DS2
    DS2 --> P3
    P3 --> DS3
    DS3 --> P4
    P4 --> DS4
    DS4 --> P5
    E3 --> P5
    P5 --> DS5
""",

    "frm06_eda_event_catalog_choreography": """flowchart TD
    subgraph COMMANDS["Commands (Requests for Action)"]
        C1["Command: IngestDailyTicks"]
        C2["Command: CalculateFeatures"]
        C3["Command: GenerateAlphaRanks"]
        C4["Command: ExecutePortfolioRebalance"]
        C5["Command: TriggerEmergencyDeRisk"]
    end

    subgraph EVENTS["Domain Events (Immutable Facts)"]
        direction TB
        E1["Event: RawTicksIngested<br/>(Payload: 28M+ trade records stored)"]
        E2["Event: StationarityVerified<br/>(Payload: ADF p=0.0121, d=0.35)"]
        E3["Event: ZeroLeakageCertified<br/>(Payload: Shift-1 truncation delta=0.0000)"]
        E4["Event: AlphaSignalRanked<br/>(Payload: Top-decile target portfolio)"]
        E5["Event: GateSuitePassed<br/>(Payload: G0-G10 certification hash)"]
        E6["Event: ChildOrderFilled<br/>(Payload: Realized fill at Open t+1)"]
        E7["Event: DematSettled<br/>(Payload: CDSC T+2 allocation confirmed)"]
    end

    subgraph HANDLERS["Event Consumers / Bounded Contexts"]
        H1["Data Lakehouse Service"]
        H2["Feature Store Engine"]
        H3["Forecasting Ensemble"]
        H4["Audit Harness Controller"]
        H5["Execution & OMS Plane"]
        H6["Risk & Ledger Service"]
    end

    C1 --> H1 --> E1
    E1 --> H2
    C2 --> H2 --> E2 & E3
    E2 & E3 --> H3
    C3 --> H3 --> E4
    E4 --> H4 --> E5
    E5 --> H5
    C4 --> H5 --> E6
    E6 --> H6 --> E7
    C5 --> H5 & H6
"""
}

def render_all():
    for name, mmd in FRAMEWORK_DIAGRAMS.items():
        mmd_path = os.path.join(OUTPUT_DIR, f"{name}.mmd")
        png_path = os.path.join(OUTPUT_DIR, f"{name}.png")
        
        with open(mmd_path, "w", encoding="utf-8") as f:
            f.write(mmd)
            
        print(f"Rendering {name}...")
        enc = base64.b64encode(mmd.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{enc}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                with open(png_path, "wb") as f_out:
                    f_out.write(data)
                print(f"{name}: SUCCESS ({len(data)} bytes)")
        except Exception as e:
            print(f"{name}: ERROR ({e})")

if __name__ == "__main__":
    render_all()
