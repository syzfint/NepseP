from nepse_client import NepseClient

c = NepseClient()
c.setTLSVerification(False)
pvh = c.getCompanyPriceVolumeHistory("NABIL")
print("Type of pvh:", type(pvh))
if isinstance(pvh, dict):
    print("Keys:", list(pvh.keys()))
    for k in pvh.keys():
        val = pvh[k]
        print(f"Key {k}: type={type(val)}, len={len(val) if isinstance(val, (list, dict)) else val}")
        if isinstance(val, list) and len(val) > 0:
            print(f"  First: {val[0]}")
            print(f"  Last: {val[-1]}")
