import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, ".")
import importlib.util

spec = importlib.util.spec_from_file_location("clef_bridge", "scripts/33_clef_inference_bridge.py")
bridge_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_mod)

bridge = bridge_mod.ClefInferenceBridge(base_url="https://fancy-candles-dress.loca.lt")
payload = bridge.build_input_payload()
p_dict = payload.model_dump(mode="json")

# Format matches Colab server's signature
p_dict["quantitative_forecasts"] = {item["ticker"]: item for item in p_dict["quantitative_forecasts"]}
p_dict["relevant_disclosures"] = [
    f"[{d.get('source', '')} {d.get('published_date_npt', '')}] {d.get('headline', '')}"
    for d in p_dict["relevant_disclosures"]
]
p_dict["visual_artifact"] = {"is_available": False}

headers = {
    "Content-Type": "application/json",
    "Bypass-Tunnel-Reminder": "true"
}

print("Testing request against https://fancy-candles-dress.loca.lt/synthesize (timeout=180s)...")
try:
    r = requests.post(
        "https://fancy-candles-dress.loca.lt/synthesize",
        json=p_dict,
        headers=headers,
        timeout=180
    )
    print("STATUS:", r.status_code)
    print("HEADERS:", dict(r.headers))
    print("BODY:\n", r.text[:2000])
    if r.status_code == 200:
        with open("scratch_live_response.json", "w", encoding="utf-8") as f:
            f.write(r.text)
        print("Wrote scratch_live_response.json successfully!")
except requests.exceptions.Timeout:
    print("TIMEOUT after 180s")
except Exception as e:
    print("ERROR:", e)
