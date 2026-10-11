import httpx
import json
from datetime import datetime

client = httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0"})

for sym in ["NABIL", "SAHAS", "ADBL"]:
    url = f"https://sharehubnepal.com/data/api/v1/candle-chart/history?symbol={sym}&resolution=1D&countback=5&isAdjust=false"
    try:
        res = client.get(url)
        print(f"Sharehub {sym} status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            if data.get("success") and data.get("data"):
                last_candle = data["data"][-1]
                t_str = datetime.fromtimestamp(last_candle["time"]/1000).strftime("%Y-%m-%d")
                print(f"  Latest candle date: {t_str}, O:{last_candle.get('open')} H:{last_candle.get('high')} L:{last_candle.get('low')} C:{last_candle.get('close')} V:{last_candle.get('volume')}")
    except Exception as e:
        print(f"Sharehub {sym} error: {e}")

# Check chukul
try:
    c_res = client.get("https://chukul.com/api/data/historydatav2?symbol=NABIL&resolution=1D")
    print(f"Chukul NABIL status: {c_res.status_code}")
    if c_res.status_code == 200:
        c_data = c_res.json()
        print("Chukul keys:", list(c_data.keys()) if isinstance(c_data, dict) else len(c_data))
except Exception as e:
    print(f"Chukul error: {e}")
