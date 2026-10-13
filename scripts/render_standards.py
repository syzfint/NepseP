import os
import urllib.request
import base64

OUTPUT_DIR = r"c:\Users\achar\Downloads\neps\figures\architecture\subsections\frameworks\standards"
os.makedirs(OUTPUT_DIR, exist_ok=True)

STANDARDS_DIAGRAMS = {
    "std01_c4_hierarchical_abstraction_levels": """flowchart TD
    subgraph L1["C4 Level 1: System Context (Simon Brown)"]
        direction TB
        ACTOR["Persons: Quant / PM / Compliance"]
        SYS_CTX["ApexMarketEngine (Single Bounded System)"]
        EXT_CTX["External: NEPSE TMS / CDSC / NRB"]
        ACTOR --> SYS_CTX --> EXT_CTX
    end

    subgraph L2["C4 Level 2: Container (Deployable Units)"]
        direction TB
        C_SPA["Streamlit Terminal UI Container"]
        C_API["FastAPI Inference and Order Bridge"]
        C_OLAP[("Chrono-Vault DuckDB and Parquet Store")]
        C_WORKER["Background Feature and Slicing Worker"]
        C_SPA --> C_API
        C_API --> C_OLAP
        C_WORKER --> C_OLAP
    end

    subgraph L3["C4 Level 3: Component (In-Container Modules)"]
        direction TB
        COMP1["Feature Engineering Controller"]
        COMP2["Fractional Diff Calculator (d=0.35)"]
        COMP3["Zero-Leakage Shift(1) Guard"]
        COMP4["Alpha Ensemble Ranker"]
        COMP1 --> COMP2 --> COMP3 --> COMP4
    end

    subgraph L4["C4 Level 4: Code (Implementation Details)"]
        direction TB
        CLASS1["MarketDataUnion Model"]
        CLASS2["CorporateActionAdjuster Class"]
        CLASS3["TripleBarrierLabeler Class"]
        CLASS1 --> CLASS2 --> CLASS3
    end

    L1 ==> L2
    L2 ==> L3
    L3 ==> L4
""",

    "std02_mbse_sysml2_kerml_meta_model": """flowchart TD
    subgraph KERML["KerML Mathematical and Logical Kernel (OMG)"]
        direction TB
        CORE_ROOT["Root Kernel Elements"]
        FEATURE["Features and Types"]
        BEHAVIOR["Behaviors, Steps, and Invocations"]
        STRUCT["Structures, Occurrences, and 4D Space-Time"]
        CORE_ROOT --> FEATURE & BEHAVIOR & STRUCT
    end

    subgraph SYSML2["SysML 2.0 Definitions vs. Usages Metamodel"]
        direction TB
        DEF_PART["Part Definition: LakehouseEngine"]
        USAGE_PART["Part Usage: production_chrono_vault"]
        
        DEF_PORT["Port Definition: TickFeedPort"]
        USAGE_PORT["Port Usage: nepse_live_ticks_in"]
        
        OCCUR_4D["4D Occurrence: Day-t Execution Snapshot"]
        
        DEF_PART --> USAGE_PART
        DEF_PORT --> USAGE_PORT
        USAGE_PART --> OCCUR_4D
    end

    subgraph API_LAYER["REST / JSON Systems API"]
        JSON_EP["REST JSON Endpoints: /models, /elements, /commits"]
        TOOL_SYNC["Real-Time Synchronized Syntax: Code <==> Diagram"]
        JSON_EP --> TOOL_SYNC
    end

    KERML ==> SYSML2
    SYSML2 ==> API_LAYER
""",

    "std03_eventstorming_timeline_taxonomy": """flowchart LR
    subgraph TAXONOMY["Alberto Brandolini EventStorming Semantic Taxonomy"]
        direction TB
        EVT["Domain Event (Orange): OrderFilledAtOpen"]
        CMD["Command (Blue): SubmitTWAPOrder"]
        AGG["Aggregate (Yellow): PortfolioOrderBook"]
        ACT["Actor (Small Yellow): ExecutionTrader"]
        POL["Policy (Lilac): Whenever Spread Widens, Dampen Participation"]
        EXT["External System (Pink): NEPSE Broker TMS"]
        HOT["HotSpot (Red): High Pre-Open Order Cancellation Rate"]
        READ["Read Model (Green): Top-3 LOB Depth Summary"]
    end

    subgraph TIMELINE["Chronological EventStorming Workflow"]
        direction LR
        T1["Actor: ExecutionTrader"] --> T2["Command: StageOrders"]
        T2 --> T3["Aggregate: PortfolioEngine"]
        T3 --> T4["Domain Event: OrdersStaged"]
        T4 --> T5["Policy: Run Pre-Open Spoof Audit"]
        T5 --> T6["HotSpot: Spoof Risk > 35%?"]
        T6 --> T7["External: NEPSE TMS"]
        T7 --> T8["Domain Event: FillExecuted"]
        T8 --> T9["Read Model: Post-Trade NAV"]
    end
""",

    "std04_strategic_ddd_context_map": """flowchart TD
    subgraph UPSTREAM["Upstream Contexts (U)"]
        MARKET_CTX["Market Data Context (U)<br/>[OHLCV Bars and Tick Records]"]
        REG_CTX["Regulatory and SEBON Context (U)<br/>[Margin rules, Fees, and Lock-ins]"]
    end

    subgraph CORE_DOMAIN["Core Strategic Bounded Context"]
        ALPHA_CTX["Quantitative Alpha Context<br/>[Hybrid ML, Signal Ensemble, and Ranking]"]
    end

    subgraph PATTERNS["DDD Relationship Patterns"]
        OHS_PL["Open Host Service / Published Language (OHS/PL):<br/>Standard JSON Schema and Parquet Tables"]
        ACL["Anti-Corruption Layer (ACL):<br/>Isolates NEPSE Legacy TMS Format into Clean Value Objects"]
        CONF["Conformist (CF):<br/>Directly adopts SEBON Fee and Demat Tax Schedule"]
        SK["Shared Kernel (SK):<br/>Common Ticker and Instrument Identity Value Object"]
    end

    subgraph DOWNSTREAM["Downstream Contexts (D)"]
        EXEC_CTX["Execution and OMS Context (D)<br/>[Almgren-Chriss TWAP/VWAP Slicers]"]
        RISK_CTX["Enterprise Risk and Accounting Context (D)<br/>[VaR, CDSC T+2 Demat Settlement]"]
    end

    MARKET_CTX -->|OHS/PL| ALPHA_CTX
    REG_CTX -->|Conformist| RISK_CTX
    ALPHA_CTX -->|Shared Kernel| EXEC_CTX
    EXEC_CTX -->|Anti-Corruption Layer| DOWNSTREAM_TMS["External NEPSE TMS"]
""",

    "std05_dfd_yourdon_gane_sarson_comparison": """flowchart TD
    subgraph YOURDON["1. Yourdon and DeMarco Notation"]
        direction TB
        Y_EXT["Rectangle: External Entity<br/>[Broker Floor Sheet]"]
        Y_PROC(("Circle / Bubble:<br/>Process 1.0<br/>Deduplicate Ticks"))
        Y_STORE["Parallel Lines:<br/>=== D1 Raw Store ==="]
        Y_FLOW["Directed Arc: Data Flow"]
        Y_EXT -->|Raw Order Log| Y_PROC -->|Clean Trades| Y_STORE
    end

    subgraph GANE["2. Gane and Sarson Notation"]
        direction TB
        G_EXT["Solid Rectangle:<br/>External Entity [NEPSE]"]
        G_PROC["Rounded Box with Top Header:<br/>P2.0 | Stationarity Transform"]
        G_STORE["Open-Ended Rectangle:<br/>[D2 | Feature Parquet Cache]"]
        G_EXT -->|Master Parquet| G_PROC -->|FracDiff Series| G_STORE
    end

    subgraph DECOMP["3. Hierarchical Decomposition"]
        D0["Level 0: Master Context Diagram (ApexMarketEngine Black Box)"]
        D1["Level 1: System-Wide Process Decomposition (P1 to P5)"]
        D2["Level 2: In-Depth Microstructure Process Sub-Decomposition"]
        D0 ==> D1 ==> D2
    end
""",

    "std06_diagrams_as_code_execution_engines": """flowchart TD
    subgraph DSL["1. Declarative Source Code (Version Controlled)"]
        C4_DSL["Structurizr DSL<br/>workspace { model { ... } views { ... } }"]
        D2_LANG["D2 Declarative Code<br/>direction: right; x -> y: label"]
        PUML["PlantUML Source<br/>@startuml ... !include C4_Context.puml"]
        MERMAID_SRC["Mermaid.js Markdown<br/>flowchart TD ... sequenceDiagram"]
    end

    subgraph ENGINES["2. Compilation and Layout Layout Engines"]
        STRUCT_ENG["Structurizr Engine (Java/Lite)<br/>[Native C4 implied relations]"]
        D2_ENG["D2 Compiler Engines<br/>[Dagre DOT / ELK Port Layout / TALA Cognitive]"]
        GRAPHVIZ["Graphviz Dot Engine<br/>[PlantUML C4 Macro Compilation]"]
        MM_INK["Mermaid Compiler Runtime<br/>[SVG and Raster Canvas Renderer]"]
        
        C4_DSL --> STRUCT_ENG
        D2_LANG --> D2_ENG
        PUML --> GRAPHVIZ
        MERMAID_SRC --> MM_INK
    end

    subgraph ARTIFACTS["3. Deterministic Output Artifacts"]
        OUT_SVG["Scalable Vector Graphics (SVG)"]
        OUT_PNG["High-Resolution Raster (PNG)"]
        OUT_DOC["Automated Architecture Markdown Documents"]
        
        STRUCT_ENG & D2_ENG & GRAPHVIZ & MM_INK --> OUT_SVG & OUT_PNG & OUT_DOC
    end
"""
}

def render_standards():
    for name, mmd in STANDARDS_DIAGRAMS.items():
        mmd_file = os.path.join(OUTPUT_DIR, f"{name}.mmd")
        png_file = os.path.join(OUTPUT_DIR, f"{name}.png")
        
        with open(mmd_file, "w", encoding="utf-8") as f:
            f.write(mmd)
            
        print(f"Rendering {name}...")
        enc = base64.b64encode(mmd.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{enc}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                with open(png_file, "wb") as f_out:
                    f_out.write(data)
                print(f"{name}: SUCCESS ({len(data)} bytes)")
        except Exception as e:
            print(f"{name}: ERROR ({e})")

if __name__ == "__main__":
    render_standards()
