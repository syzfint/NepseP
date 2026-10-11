import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
from nepse_client import NepseClient

print("Initializing NepseClient...")
c = NepseClient()
c.setTLSVerification(False)

print("Fetching official PriceVolume...")
pv = c.getPriceVolume()
print(f"PriceVolume returned {len(pv)} records.")

# Map symbols to base price volume
symbols_map = {}
for item in pv:
    sym = item.get("symbol")
    if sym:
        sym = sym.upper().strip()
        symbols_map[sym] = {
            "symbol": sym,
            "security_name": item.get("securityName"),
            "close": float(item.get("closePrice") or item.get("lastTradedPrice") or 0.0),
            "prev_close": float(item.get("previousClose") or 0.0),
            "volume": float(item.get("totalTradeQuantity") or 0.0),
            "open": float(item.get("previousClose") or item.get("closePrice") or 0.0),
            "high": max(float(item.get("closePrice") or 0.0), float(item.get("previousClose") or 0.0)),
            "low": min(float(item.get("closePrice") or 0.0), float(item.get("previousClose") or 0.0)),
            "source": "nepse_price_volume"
        }

print(f"Total mapped scrips: {len(symbols_map)}")

# Fetch detailed 1D candles from Sharehub to enrich open, high, low, close
def enrich_candle(sym):
    url = f"https://sharehubnepal.com/data/api/v1/candle-chart/history?symbol={sym}&resolution=1D&countback=2&isAdjust=false"
    try:
        with httpx.Client(timeout=3.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            res = client.get(url)
            if res.status_code == 200:
                d = res.json()
                if d.get("success") and d.get("data"):
                    c_last = d["data"][-1]
                    t_str = time.strftime('%Y-%m-%d', time.localtime(c_last['time']/1000))
                    if t_str == "2026-10-09":
                        return sym, {
                            "open": float(c_last["open"]),
                            "high": float(c_last["high"]),
                            "low": float(c_last["low"]),
                            "close": float(c_last["close"]),
                            "volume": float(c_last["volume"]),
                            "source": "sharehub_candle_exact"
                        }
    except Exception:
        pass
    return sym, None

print("Enriching OHLC candles via Sharehub (5 workers, 3s timeout)...")
enriched_count = 0
with ThreadPoolExecutor(max_workers=5) as pool:
    futures = [pool.submit(enrich_candle, s) for s in list(symbols_map.keys())]
    for fut in as_completed(futures):
        sym, data = fut.result()
        if data:
            symbols_map[sym]["open"] = data["open"]
            symbols_map[sym]["high"] = data["high"]
            symbols_map[sym]["low"] = data["low"]
            symbols_map[sym]["close"] = data["close"]
            symbols_map[sym]["volume"] = data["volume"]
            symbols_map[sym]["source"] = data["source"]
            enriched_count += 1

print(f"Successfully enriched {enriched_count}/{len(symbols_map)} scrips with tick-exact candles!")
print("Sample scrips:")
for s in ["NABIL", "SAHAS", "ADBL", "SHIVM"]:
    if s in symbols_map:
        print(f"  {s}: {symbols_map[s]}")
