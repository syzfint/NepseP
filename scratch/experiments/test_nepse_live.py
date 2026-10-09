import requests
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

urls = [
    "https://nepalstock.com/api/npts/nepse-data/today-price",
    "https://nepalstock.com/api/npts/live-market",
    "https://nepalstock.com/api/npts/nepse-data/market-summary"
]

for url in urls:
    try:
        r = requests.get(url, headers=headers, timeout=5)
        print(f"{url} -> Status: {r.status_code}, Length: {len(r.content)}")
    except Exception as e:
        print(f"{url} -> Error: {e}")
