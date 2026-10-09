import urllib.request
import json

req = urllib.request.Request("http://127.0.0.1:8000/api/market/tape")
with urllib.request.urlopen(req) as resp:
    data = json.load(resp)
    print("STATUS:", data.get("status"))
    print("SOURCE:", data.get("source"))
    print("LAST UPDATED:", data.get("last_updated_npt"))
    print("TOTAL TURNOVER: Rs.", round(data.get("total_turnover_npr", 0) / 1e9, 2), "Billion")
    print("TOTAL VOLUME:", f"{data.get('total_volume_shares', 0):,.0f} shares")
    print("TICK COUNT:", len(data.get("ticks", [])))
    print("\nGENUINE LIVE EXECUTIONS FROM NEPSE MATCHING ENGINE:")
    for t in data.get("ticks", [])[:10]:
        print(f"  [{t['timestamp_npt']}] {t['symbol']:<8} LTP: Rs. {t['ltp']:<7.1f} Vol: {t['volume']:<5} {t['buyer_broker']} -> {t['seller_broker']}")
    print("\nREAL-TIME OFI IMBALANCE METRICS:")
    print(json.dumps(data.get("ofi"), indent=2))
