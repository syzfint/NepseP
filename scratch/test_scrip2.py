from nepse_client import NepseClient

c = NepseClient()
c.setTLSVerification(False)

for sym in ["ADBL", "NABIL", "SAHAS"]:
    try:
        graph = c.getDailyScripPriceGraph(sym)
        print(f"{sym} daily graph: {len(graph) if graph else 0} items")
        if graph:
            print("  First:", graph[0])
            print("  Last:", graph[-1])
    except Exception as e:
        print(f"Daily graph {sym} error: {e}")

    try:
        pvh = c.getCompanyPriceVolumeHistory(sym)
        print(f"{sym} PV history: {len(pvh) if pvh else 0} items")
        if pvh:
            print("  First:", pvh[0])
            print("  Last:", pvh[-1])
    except Exception as e:
        print(f"PV history {sym} error: {e}")
