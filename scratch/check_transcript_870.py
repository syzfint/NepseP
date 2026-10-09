import json

with open(r"C:\Users\achar\.gemini\antigravity\brain\f9b1146c-9f17-4ad4-91dc-c18fabafdcd6\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i in [84, 85, 265]:
            obj = json.loads(line)
            src = obj.get("source")
            content = obj.get("content", "")
            print(f"=== Line {i} ({src}) ===")
            print(str(content)[:1000])
