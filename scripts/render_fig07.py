import urllib.request
import base64

fig07_clean = """flowchart TD
    subgraph S1["1. Local Quant Engine"]
        MAT["Headless Matplotlib Agg PNG<br/>In-Memory Base64 Render"]
        CTX["Quant Context Data<br/>Returns, Volatility, OFI, Ticks"]
        SEAL["Master Provenance Seal<br/>SHA256 Hash Computation"]
        MAT --> SEAL
        CTX --> SEAL
    end

    subgraph S2["2. Cloudflare Encrypted Tunnel"]
        NET["HTTPS POST /synthesize<br/>130KB Payload, RTT 8.42s"]
        SEAL --> NET
    end

    subgraph S3["3. Remote Colab GPU Node"]
        GPU["NVIDIA Tesla T4 GPU 16GB"]
        VLM["Qwen2.5-VL-3B VLM"]
        LORA["PEFT LoRA Adapter 65MB"]
        SYNTH["Multimodal Synthesis Engine"]
        NET --> GPU --> VLM
        LORA -.-> VLM
        VLM --> SYNTH
    end

    subgraph S4["4. Fail-Closed Cryptographic Guard"]
        CHECK{"Pydantic v2 Schema Valid and Hash Match?"}
        OK["Persist clef_analyst_report.json"]
        FAIL["FAIL-CLOSED: Revert to Pure Quant Mode"]
        SYNTH --> CHECK
        CHECK -->|Yes| OK
        CHECK -->|No| FAIL
    end
"""

with open(r"figures\architecture\fig07_clef_multimodal_vlm_bridge.mmd", "w", encoding="utf-8") as f:
    f.write(fig07_clean)

enc = base64.b64encode(fig07_clean.encode("utf-8")).decode("ascii")
url = f"https://mermaid.ink/img/{enc}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
        with open(r"figures\architecture\fig07_clef_multimodal_vlm_bridge.png", "wb") as f_out:
            f_out.write(data)
        print("fig07 SUCCESS:", len(data))
except Exception as e:
    print("fig07 ERROR:", e)
