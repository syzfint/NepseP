import httpx
import time
from nepse_client import NepseClient

c = NepseClient()
c.setTLSVerification(False)
pv = c.getPriceVolume()
symbols = [x['symbol'] for x in pv if x.get('symbol')]
print(f"Total symbols from getPriceVolume: {len(symbols)}")

# Test fetching first 10 symbols
client = httpx.Client(timeout=5.0, headers={"User-Agent": "Mozilla/5.0"})
t0 = time.time()
found = 0
for s in symbols[:10]:
    try:
        url = f"https://sharehubnepal.com/data/api/v1/candle-chart/history?symbol={s}&resolution=1D&countback=2&isAdjust=false"
        res = client.get(url)
        if res.status_code == 200:
            d = res.json()
            if d.get("success") and d.get("data"):
                c_today = d["data"][-1]
                t_str = time.strftime('%Y-%m-%d', time.localtime(c_today['time']/1000))
                print(f"  {s}: date={t_str}, O={c_today['open']}, H={c_today['high']}, L={c_today['low']}, C={c_today['close']}, V={c_today['volume']}")
                found += 1
    except Exception as e:
        print(f"  {s} error: {e}")

print(f"Fetched {found}/10 in {time.time()-t0:.2f}s")
