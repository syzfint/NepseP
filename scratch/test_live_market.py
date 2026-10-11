from nepse_client import NepseClient

c = NepseClient()
c.setTLSVerification(False)

for m in ["getLiveMarket", "getTradingAverage", "getHolidayList"]:
    try:
        fn = getattr(c, m)
        res = fn()
        length = len(res) if isinstance(res, (list, dict)) else "N/A"
        print(f"SUCCESS {m}: type={type(res)}, length={length}")
        if isinstance(res, list) and len(res) > 0:
            print("  First item:", res[0])
            print("  Item keys:", list(res[0].keys()) if isinstance(res[0], dict) else type(res[0]))
    except Exception as e:
        print(f"FAIL {m}: {e}")
