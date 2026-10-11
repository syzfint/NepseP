from nepse_client import NepseClient
import json

c = NepseClient()
c.setTLSVerification(False)
url = c.api_end_points['floor_sheet']
full_url = c.get_full_url(url)
print("Full URL:", full_url)

for day_val in [9, 8, 7]:
    id_val = c.getPOSTPayloadIDForFloorSheet(f"2026-10-0{day_val}")
    headers = c.getAuthorizationHeaders()
    res = c.client.post(full_url + "?size=10&sort=contractId,desc", headers=headers, json={"id": id_val})
    print(f"Day {day_val} (id={id_val}): status={res.status_code}, length={len(res.text)}")
    try:
        data = res.json()
        print(f"  Response type: {type(data)}")
        if isinstance(data, dict):
            print("  Keys:", list(data.keys()))
        elif isinstance(data, list):
            print(f"  List items: {len(data)}")
            if len(data) > 0:
                print("  Sample:", data[0])
        else:
            print("  Data:", data)
    except Exception as e:
        print("  Error parsing JSON:", e, res.text[:200])
