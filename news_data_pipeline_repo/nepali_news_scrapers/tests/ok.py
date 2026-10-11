import os
import requests
import json

symbols = [ "NICA"]  # Add more symbols here

base_url = "https://www.onlinekhabar.com/smtm"
endpoints = {
    "price_chart": "ticker-page/chart/{symbol}/1d",
    "key_statistics": "ticker-page/ticker-stats/{symbol}",
    "quick_view": "ticker-page/ticker-quick-view/{symbol}",
    "technical_indicators": "ticker-page/ticker-technical-indicator/{symbol}",
    "ticker_info": "ticker-page/ticker-info/{symbol}",
    "market_range": "ticker-page/market-range/{symbol}",
    "market_status": "home/market-status"  # not symbol-specific
}

output_dir = "tests/html_test_files"
os.makedirs(output_dir, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124"
})

# Fetch market status (only once, not symbol-based)
try:
    url = f"{base_url}/{endpoints['market_status']}"
    response = session.get(url)
    response.raise_for_status()
    with open(os.path.join(output_dir, "market_status.json"), "w", encoding="utf-8") as f:
        json.dump(response.json(), f, indent=2)
    print("Saved market_status.json")
except Exception as e:
    print(f"Failed to fetch market_status: {e}")

# Now fetch all symbol-specific endpoints
for symbol in symbols:
    for section, endpoint_template in endpoints.items():
        if section == "market_status":
            continue  # already handled above

        endpoint = endpoint_template.format(symbol=symbol)
        url = f"{base_url}/{endpoint}"

        try:
            response = session.get(url)
            response.raise_for_status()
            data = response.json()

            symbol_dir = os.path.join(output_dir, symbol)
            os.makedirs(symbol_dir, exist_ok=True)

            filepath = os.path.join(symbol_dir, f"{section}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print(f"Saved {section}.json for {symbol}")
        except Exception as e:
            print(f"Failed to fetch {section} for {symbol}: {e}")
