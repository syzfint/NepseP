import urllib.request
import base64

frm04_clean = """flowchart TD
    subgraph POOL_INTERNAL["Internal Strategy and Risk Desk"]
        START((Day t Close 15:00)) --> GEN_WEIGHTS["Generate Model Target Weights"]
        GEN_WEIGHTS --> RISK_EVAL{"Pre-Trade Risk Checks Passed?"}
        RISK_EVAL -->|No: NAV or ADV Limit| REJECT_INT["Reject or Trim Position"]
        RISK_EVAL -->|Yes| STAGE_ORDER["Stage Orders for Day t+1 Open"]
    end

    subgraph POOL_COMPLIANCE["Pre-Trade Compliance and Regulatory Shield"]
        STAGE_ORDER --> AUDIT_SPOOF{"Pre-Open 10:30-10:45: Cancellations Above 35%?"}
        AUDIT_SPOOF -->|Yes: Spoofing Flag| ABORT["Halt Execution on Target Scrip"]
        AUDIT_SPOOF -->|No: Order Book Clean| DISPATCH["Approve Order Dispatch"]
    end

    subgraph POOL_BROKER["External NEPSE Broker TMS and Execution"]
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
"""

out_mmd = r"figures\architecture\subsections\frameworks\frm04_bpmn_business_process_choreography.mmd"
out_png = r"figures\architecture\subsections\frameworks\frm04_bpmn_business_process_choreography.png"

with open(out_mmd, "w", encoding="utf-8") as f:
    f.write(frm04_clean)

enc = base64.b64encode(frm04_clean.encode("utf-8")).decode("ascii")
url = f"https://mermaid.ink/img/{enc}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = resp.read()
        with open(out_png, "wb") as f_out:
            f_out.write(data)
        print("frm04 CLEAN SUCCESS:", len(data))
except Exception as e:
    print("frm04 CLEAN ERROR:", e)
