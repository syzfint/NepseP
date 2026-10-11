from nepse_client import NepseClient
import json

c = NepseClient()
c.setTLSVerification(False)
print("Available endpoints in NepseClient:")
for k, v in c.api_end_points.items():
    print(f"  {k}: {v}")

pv = c.getPriceVolume()
print(f"\nPriceVolume total records: {len(pv)}")
if pv:
    print("PriceVolume fields:", list(pv[0].keys()))
    print("First 3 records:")
    for item in pv[:3]:
        print(" ", item)
