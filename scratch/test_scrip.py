from nepse_client import NepseClient

c = NepseClient()
c.setTLSVerification(False)

# Let's test getDailyScripPriceGraph and getCompanyPriceVolumeHistory
for sym, sec_id in [("ADBL", 397), ("NABIL", 131), ("SAHAS", 2854)]:
    try:
        if hasattr(c, "getDailyScripPriceGraph"):
            graph = c.getDailyScripPriceGraph(sec_id)
            print(f"{sym} (id={sec_id}) daily graph: {len(graph) if graph else 0} items")
            if graph:
                print("  Sample:", graph[-1])
    except Exception as e:
        print(f"Daily graph {sym} error: {e}")

    try:
        if hasattr(c, "getCompanyPriceVolumeHistory"):
            pvh = c.getCompanyPriceVolumeHistory(sec_id)
            print(f"{sym} (id={sec_id}) PV history: {len(pvh) if pvh else 0} items")
            if pvh:
                print("  Sample:", pvh[-1] if isinstance(pvh, list) else pvh)
    except Exception as e:
        print(f"PV history {sym} error: {e}")
