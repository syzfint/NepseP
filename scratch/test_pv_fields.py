from nepse_client import NepseClient
import json

c = NepseClient()
c.setTLSVerification(False)
pv = c.getPriceVolume()

print(f"Total scrips in getPriceVolume today: {len(pv)}")
nabil_pv = [x for x in pv if x.get("symbol") == "NABIL"]
print("NABIL today:", nabil_pv)
sahas_pv = [x for x in pv if x.get("symbol") == "SAHAS"]
print("SAHAS today:", sahas_pv)

# Check all fields in pv
all_fields = set()
for item in pv:
    all_fields.update(item.keys())
print("All fields in getPriceVolume:", all_fields)
