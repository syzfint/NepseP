import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
from nepse_client import NepseClient

c = NepseClient()
c.setTLSVerification(False)
pv = c.getPriceVolume()
ta = c.getTradingAverage()

all_symbols = set()
for x in pv:
    if x.get("symbol"):
        all_symbols.add(x["symbol"])
for x in ta:
    if x.get("symbol"):
        all_symbols.add(x["symbol"])

all_symbols = sorted(list(all_symbols))
print(f"Total unique symbols to fetch: {len(all_symbols)}")

results = {}
t0 = time.time()

def fetch_symbol(sym):
    url = f"https://sharehubnepal.com/data/api/v1/candle-chart/history?symbol={sym}&resolution=1D&countback=2&isAdjust=false"
    try:
        with httpx.Client(timeout=6.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            res = client.get(url)
            if res.status_code == 200:
                d = res.json()
                if d.get("success") and d.get("data"):
                    last_c = d["data"][-1]
                    t_str = time.strftime('%Y-%m-%d', time.localtime(last_c['time']/1000))
                    if t_str == "2026-10-09":
                        return sym, {
                            "open": float(last_c["open"]),
                            "high": float(last_c["high"]),
                            "low": float(last_c["low"]),
                            "close": float(last_c["close"]),
                            "volume": float(last_c["volume"]),
                            "source": "sharehub_candle"
                        }
    except Exception:
        pass
    return sym, None

with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(fetch_symbol, s) for s in all_symbols]
    for fut in as_completed(futures):
        sym, data = fut.result()
        if data:
            results[sym] = data

print(f"Fetched {len(results)}/{len(all_symbols)} exact candles in {time.time()-t0:.2f}s!")
