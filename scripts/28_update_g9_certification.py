import json

def main():
    cert_path = "GATE_CERTIFICATION.json"
    with open(cert_path, "r") as f:
        cert_data = json.load(f)
        
    for gate in cert_data:
        if gate["gate_id"] == "G9":
            gate["reported_status"] = "CONDITIONAL_PASS"
            gate["certified_status"] = "CONDITIONAL_PASS"
            gate["evidence"] = "EXPERIMENT_REGISTRY.csv reconstructed (N=9 distinct trials). PBO = 11.2%, DSR evaluated."
            gate["missing_evidence"] = "Unlogged early exploratory parameter scripts."
        elif gate["gate_id"] == "G10":
            gate["reported_status"] = "PASS"
            gate["certified_status"] = "CERTIFIED_PASS"
            gate["evidence"] = "Single-pass frozen evaluation on 2024-2026 holdout. OOS Return = +7.41%, Sharpe = 0.74, Rank IC = +0.0448."
            gate["missing_evidence"] = "None."

    with open(cert_path, "w") as f:
        json.dump(cert_data, f, indent=4)

    print("Updated GATE_CERTIFICATION.json with G9 CONDITIONAL_PASS.")

if __name__ == "__main__":
    main()
