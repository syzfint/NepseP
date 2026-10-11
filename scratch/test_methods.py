from nepse_client import NepseClient

c = NepseClient()
c.setTLSVerification(False)

methods_to_test = [
    ("getMarketStatus", []),
    ("getNepseIndex", []),
    ("getSummary", []),
    ("getNepseSubIndices", []),
    ("getPriceVolume", []),
    ("getTopTenGainers", []),
    ("getTopTenLosers", []),
    ("getTopTenTurnover", []),
    ("getTopTenTransactions", []),
    ("getTopTenTrades", []),
    ("getSupplyDemand", []),
    ("getSecurityList", []),
]

for m, args in methods_to_test:
    if hasattr(c, m):
        try:
            fn = getattr(c, m)
            res = fn(*args)
            length = len(res) if isinstance(res, (list, dict)) else "N/A"
            print(f"SUCCESS {m}: type={type(res)}, length={length}")
            if isinstance(res, list) and len(res) > 0:
                print(f"   Sample: {res[0]}")
        except Exception as e:
            print(f"FAIL {m}: {e}")
