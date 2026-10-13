import urllib.request
import base64

sub01_fixed = """flowchart TD
    subgraph MONITOR["1. Production Performance and Drift Monitoring"]
        LIVE_FILLS["Live Fill Ingestion and Return Accounting"]
        IC_TRACK["Rolling 20-Day Rank IC Tracker"]
        PSI_TRACK["Population Stability Index and Drift Z-Score"]
        LIVE_FILLS --> IC_TRACK
        LIVE_FILLS --> PSI_TRACK
    end

    subgraph DRIFT_TRIGGER["2. Automated Retraining Decision Guard"]
        IC_CHECK{"IC Below 0.015 OR PSI Above 0.25?"}
        SCHED{"Scheduled Monthly CPCV Horizon?"}
        IC_TRACK --> IC_CHECK
        PSI_TRACK --> IC_CHECK
        IC_CHECK -->|No| RUN_PROD["Maintain Active Production Model Weights"]
        IC_CHECK -->|Yes| TRIGGER["Trigger Retraining Workflow"]
        SCHED -->|Yes| TRIGGER
    end

    subgraph RETRAIN["3. Combinatorial Purged Retraining CPCV"]
        INGEST_EXP["Append Latest Certified Lakehouse Data"]
        PURGE["10-Session Purging and 5-Session Embargo Window"]
        FIT["Retrain LightGBM and Calibrate Chronos"]
        TRIGGER --> INGEST_EXP
        INGEST_EXP --> PURGE
        PURGE --> FIT
    end

    subgraph HARNESS["4. Automated G0-G10 Certification Gate"]
        G_RUN["Execute Full Forensic Gate Suite G0 to G10"]
        G_CHECK{"All 10 Gates Certified PASS and DSR Above 0.95?"}
        FIT --> G_RUN
        G_RUN --> G_CHECK
        G_CHECK -->|No| REJECT["Reject Candidate: Alert Quant Desk"]
    end

    subgraph DEPLOY["5. Model Registry and Hot-Swap"]
        REGISTRY["Register Model in Registry with SHA-256 Seal"]
        HOTSWAP["Atomic Hot-Swap in Production Prediction Engine"]
        G_CHECK -->|Yes| REGISTRY
        REGISTRY --> HOTSWAP
    end
"""

out_mmd = r"figures\architecture\subsections\sub01_mlops_concept_drift_retraining_pipeline.mmd"
out_png = r"figures\architecture\subsections\sub01_mlops_concept_drift_retraining_pipeline.png"

with open(out_mmd, "w", encoding="utf-8") as f:
    f.write(sub01_fixed)

enc = base64.b64encode(sub01_fixed.encode("utf-8")).decode("ascii")
url = f"https://mermaid.ink/img/{enc}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
        with open(out_png, "wb") as f_out:
            f_out.write(data)
        print("sub01 FIXED SUCCESS:", len(data))
except Exception as e:
    print("sub01 FIXED ERROR:", e)
