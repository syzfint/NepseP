import json

with open('NEPSE_MASTER_INTEGRATED_OUTPUT.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f"Master output live_nepse_index = {data['live_nepse_index']}")
print(f"Master output live_nepse_change = {data['live_nepse_change']}")

# Also check baseline
with open('BASELINE/baseline_output.json', 'r', encoding='utf-8') as f:
    base = json.load(f)
print(f"Baseline live_nepse_index = {base['live_nepse_index']}")
