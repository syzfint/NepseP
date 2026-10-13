import os
import urllib.request
import base64

OUTPUT_DIR = r"c:\Users\achar\Downloads\neps\figures\architecture\subsections"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SUBSECTION_DIAGRAMS = {
    "sub01_mlops_concept_drift_retraining_pipeline": """flowchart TD
    subgraph MONITOR["1. Production Performance & Feature Drift Monitoring"]
        LIVE_FILLS["Live Fill Ingestion & Return Accounting"]
        IC_TRACK["Rolling 20-Day Rank IC Tracker"]
        PSI_TRACK["Population Stability Index (PSI) & Feature Drift Z-Score"]
        LIVE_FILLS --> IC_TRACK
        LIVE_FILLS --> PSI_TRACK
    end

    subgraph DRIFT_TRIGGER["2. Automated Retraining Decision Guard"]
        IC_CHECK{"Rolling IC < +0.015 OR PSI > 0.25?"}
        SCHED{"Scheduled Monthly CPCV Horizon?"}
        IC_TRACK & PSI_TRACK --> IC_CHECK
        IC_CHECK -->|No| RUN_PROD["Maintain Active Production Model Weights"]
        IC_CHECK -->|Yes| TRIGGER["Trigger Automated Retraining Workflow"]
        SCHED -->|Yes| TRIGGER
    end

    subgraph RETRAIN["3. Combinatorial Purged Retraining (CPCV)"]
        INGEST_EXP["Append Latest Certified Lakehouse Data"]
        PURGE["10-Session Purging & 5-Session Embargo Window"]
        FIT["Retrain LightGBM Ranker & Calibrate Chronos Hyperparameters"]
        INGEST_EXP --> PURGE --> FIT
    end

    subgraph HARNESS["4. Automated G0-G10 Re-Certification Gate"]
        G_RUN["Execute Full Forensic Gate Suite (G0 to G10)"]
        G_CHECK{"All 10 Gates Certified PASS & DSR >= 0.95?"}
        FIT --> G_RUN --> G_CHECK
        G_CHECK -->|No| REJECT["Reject Candidate: Alert Quant Desk & Rollback"]
    end

    subgraph DEPLOY["5. Model Registry & Zero-Downtime Hot-Swap"]
        REGISTRY["Register Model in Registry (SHA-256 + Model Card)"]
        HOTSWAP["Atomic Hot-Swap in Production Prediction Engine"]
        G_CHECK -->|Yes| REGISTRY --> HOTSWAP
    end

    TRIGGER --> INGEST_EXP
""",

    "sub02_live_oms_broker_tms_order_lifecycle": """sequenceDiagram
    autonumber
    actor QuantDesk as Alpha Strategy Engine
    participant OMS as Internal Order Mgmt (OMS)
    participant Risk as Pre-Trade Risk Shield
    participant TMS as NEPSE Broker TMS Gateway
    participant CDSC as CDSC Demat Settlement Engine

    QuantDesk->>OMS: Day t Close (15:00): Target Weights Generated
    OMS->>Risk: Staged Order Batch (5% ADV Cap & Cash Check)
    Risk->>Risk: Verify Pre-Trade Limit (Single Stock <= 10% NAV)
    Risk-->>OMS: Risk Checks Approved
    
    Note over OMS,TMS: Pre-Open Session (10:30 - 10:45 AM Day t+1)
    OMS->>TMS: Query Order Book Depth & Inspect Cancellation Ratio
    alt Cancellation Rate > 35% (Spoofing Flag)
        TMS-->>OMS: Warning: Abnormal Pre-Open Imbalance
        OMS->>OMS: Trigger Order Postponement / Scrip Blacklist
    else Healthy Market Depth
        OMS->>TMS: Stage Valid Orders for Continuous Session
    end

    Note over OMS,TMS: Continuous Market Open (11:00 AM Day t+1)
    OMS->>TMS: Submit TWAP/VWAP Child Orders at Open Auction
    TMS-->>OMS: Order Accepted (Order ID: NEPSE-892341)
    
    alt Full Execution
        TMS-->>OMS: Execution Report: Filled at Open(t+1)
    else Partial Fill (Liquidity Exhaustion)
        TMS-->>OMS: Partial Fill Report (Filled 65%, Rest Open)
        OMS->>OMS: Re-estimate Trajectory or Cancel Remainder at 14:50 PM
    else Order Rejection / Circuit Breaker (+/-10%)
        TMS-->>OMS: Order Rejected: 10% Dynamic Band Hit
        OMS->>QuantDesk: Raise Circuit Breaker Event Notice
    end

    OMS->>CDSC: Post-Trade Allocation & T+2 Demat Lock Verification
    CDSC-->>OMS: Demat Settlement Confirmed
""",

    "sub03_realtime_execution_slippage_feedback_loop": """flowchart TD
    subgraph INTENT["1. Order Intent & Theoretical Benchmark"]
        DECISION["Alpha Target Order: Q_target, T_horizon"]
        BENCHMARK["Theoretical Fill Price Model: Open(t+1)"]
        DECISION --> BENCHMARK
    end

    subgraph EXEC["2. Algorithmic Market Execution"]
        ALMGREN["Almgren-Chriss Slicer Trajectory"]
        VWAP["Intraday U-Shaped VWAP Schedule"]
        MARKET["NEPSE Floor-Sheet Matching Engine"]
        BENCHMARK --> ALMGREN --> VWAP --> MARKET
    end

    subgraph METRICS["3. Slippage Measurement & Decomposition"]
        REALIZED["Realized Fill Price: P_exec"]
        DECOMP["Slippage Decomposition:<br/>Total Slippage = (P_exec - P_expected) / P_expected<br/>- Permanent Market Impact<br/>- Temporary Spread Crossing Cost<br/>- Broker Fee & Taxes (0.40% to 0.27% + 0.015%)"]
        MARKET --> REALIZED --> DECOMP
    end

    subgraph FEEDBACK["4. Adaptive Calibration Engine"]
        KALMAN["Recursive Adaptive Estimator (Kalman Filter)"]
        DECOMP --> KALMAN
        UPDATE_IMPACT["Update Impact Parameter: eta(t)"]
        UPDATE_URGENCY["Update Risk Aversion / Execution Urgency: lambda"]
        UPDATE_PARTICIPATION["Calibrate Max Participation Rate (<= 15% Top-3 LOB)"]
        KALMAN --> UPDATE_IMPACT & UPDATE_URGENCY & UPDATE_PARTICIPATION
    end

    UPDATE_IMPACT & UPDATE_URGENCY & UPDATE_PARTICIPATION -.->|Real-Time Feedback Adjustment| ALMGREN
""",

    "sub04_lakehouse_data_schema_er_model": """erDiagram
    RAW_FLOOR_SHEETS {
        bigint transaction_id PK
        timestamp trade_timestamp
        string ticker FK
        int buyer_broker_id
        int seller_broker_id
        int contract_quantity
        decimal contract_rate
        decimal contract_amount
        boolean is_wash_trade
    }

    DAILY_OHLCV_BARS {
        string ticker PK
        date trade_date PK
        decimal open_npr
        decimal high_npr
        decimal low_npr
        decimal close_npr
        bigint volume_shares
        decimal turnover_npr
        int transaction_count
    }

    CORPORATE_ACTIONS {
        int action_id PK
        string ticker FK
        date book_closure_date
        string action_type
        decimal bonus_ratio
        decimal right_ratio
        decimal cash_dividend_rs
        decimal backward_multiplier
    }

    ADJUSTED_FEATURES {
        string ticker PK
        date feature_date PK
        decimal adj_close
        decimal fracdiff_price
        decimal ret_1w_lagged
        decimal realized_vol_20d
        decimal butt_distress_lr3
        decimal broker_imbalance_ofi
        decimal composite_alpha_z
        decimal forward_ret_5d_label
    }

    DAILY_OHLCV_BARS ||--o{ RAW_FLOOR_SHEETS : "aggregates"
    DAILY_OHLCV_BARS ||--o{ CORPORATE_ACTIONS : "adjusts_via"
    DAILY_OHLCV_BARS ||--|| ADJUSTED_FEATURES : "transforms_into"
""",

    "sub05_system_risk_breakers_disaster_recovery": """flowchart TD
    subgraph SENSORS["1. Real-Time Risk & Telemetry Sensors"]
        M1["Portfolio NAV & Intraday PnL Stream"]
        M2["Parametric & Historical Value-at-Risk (99% VaR)"]
        M3["Exchange Heartbeat & Gateway Latency Watcher"]
        M4["Data Lakehouse Feed Integrity Sentinel"]
    end

    subgraph THRESHOLDS["2. Enterprise Circuit Breaker Hierarchy"]
        L1{"Intraday Drawdown >= 3.0%?"}
        L2{"90-Day Trailing Drawdown >= 14.0%?"}
        L3{"Exchange Feed Disconnect > 60 Seconds?"}
        L4{"Daily VaR Exceeded Portfolio Risk Budget?"}
        M1 --> L1
        M1 --> L2
        M3 --> L3
        M2 --> L4
    end

    subgraph ACTIONS["3. Automated Mitigation Protocols"]
        WARN["Level 1: Throttle New Buys & Freeze Position Expansion"]
        DERISK["Level 2: De-risk Portfolio to 50% Cash Allocation"]
        HALT["Level 3: Hard Stop / Kill Switch (Emergency Soft Liquidation)"]
        HOT_FAIL["Level 4: Failover to Secondary Hot Standby Node"]
        
        L1 -->|Yes| WARN
        L4 -->|Yes| WARN
        L2 -->|Yes| DERISK
        L3 -->|Yes| HOT_FAIL
        DERISK --> HALT
    end

    subgraph TOPOLOGY["4. Disaster Recovery & Node Topology"]
        PRIMARY["Primary Node: Active TMS Execution Engine (Zero-Copy DuckDB)"]
        REPLICA["Hot-Standby Replica: Real-Time State Synced over TLS"]
        VAULT_DR["Cold Backup: Immutable Parquet Lakehouse in Cloud Storage"]
        
        PRIMARY -.->|Continuous State Replication| REPLICA
        HOT_FAIL -.->|Promote Replica to Master| REPLICA
        PRIMARY -.->|Nightly Encrypted Snapshot| VAULT_DR
    end
"""
}

def render_diagrams():
    for name, mmd in SUBSECTION_DIAGRAMS.items():
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
    render_diagrams()
