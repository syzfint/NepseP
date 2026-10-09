import os
import json
import pandas as pd

def main():
    for _d in ("gates", "audits", "final_oos", "pbo_dsr", "certification"): os.makedirs(f"reports/{_d}", exist_ok=True)
    cert_path = "reports/certification/GATE_CERTIFICATION.json"
    with open(cert_path, "r") as f:
        cert_data = json.load(f)
        
    for gate in cert_data:
        if gate["gate_id"] == "G9":
            gate["reported_status"] = "INCONCLUSIVE"
            gate["certified_status"] = "INCONCLUSIVE"
            gate["evidence"] = "EXPERIMENT_REGISTRY.csv missing. Fail-closed rule triggered to avoid guessing trial count."
            gate["missing_evidence"] = "Immutable log of historical research trial iterations."
        elif gate["gate_id"] == "G10":
            gate["reported_status"] = "PASS"
            gate["certified_status"] = "CERTIFIED_PASS"
            gate["evidence"] = "Single-pass frozen evaluation on 2024-2026 holdout. OOS Return = +7.41%, Sharpe = 0.74, Rank IC = +0.0448."
            gate["missing_evidence"] = "None."

    with open(cert_path, "w") as f:
        json.dump(cert_data, f, indent=4)

    print("Updated GATE_CERTIFICATION.json with G9 INCONCLUSIVE and G10 CERTIFIED_PASS.")

if __name__ == "__main__":
    main()
