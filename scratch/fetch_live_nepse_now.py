import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
from playwright.async_api import async_playwright

# Nepal Standard Time (UTC+5:45)
NPT = timezone(timedelta(hours=5, minutes=45))

async def fetch_live_nepse():
    current_time_npt = datetime.now(NPT)
    print(f"[{current_time_npt.strftime('%Y-%m-%d %H:%M:%S NPT')}] Initiating Live NEPSE connection...")

    market_data = {
        "fetch_timestamp_npt": current_time_npt.strftime("%Y-%m-%d %H:%M:%S NPT"),
        "fetch_timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "market_status": "UNKNOWN",
        "nepse_index": None,
        "index_change": None,
        "index_pct_change": None,
        "total_turnover_npr": None,
        "total_shares_traded": None,
        "total_transactions": None,
        "indices": {},
        "today_prices": [],
        "api_responses": {}
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        async def handle_response(response):
            url = response.url
            if "/api/nots/" in url:
                try:
                    data = await response.json()
                    market_data["api_responses"][url] = data
                    
                    if "today-price" in url and isinstance(data, dict):
                        content = data.get("content", [])
                        if content and len(content) > len(market_data["today_prices"]):
                            market_data["today_prices"] = content
                            print(f"Captured {len(content)} live today-price quotes!")
                            
                    elif "index" in url.lower() or "indices" in url.lower():
                        print(f"Captured index endpoint: {url}")
                        if isinstance(data, list):
                            for idx in data:
                                if isinstance(idx, dict) and "index" in idx:
                                    market_data["indices"][idx.get("index")] = idx
                        elif isinstance(data, dict):
                            market_data["indices"]["summary"] = data

                    elif "market-summary" in url.lower() or "marketopen" in url.lower():
                        print(f"Captured market summary: {url}")
                        market_data["market_summary_raw"] = data
                except Exception:
                    pass

        page.on("response", handle_response)

        # 1. First visit homepage for live index, ticker tape, and status
        print("Navigating to https://nepalstock.com...")
        try:
            await page.goto("https://nepalstock.com", timeout=30000, wait_until="networkidle")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Warning on homepage load: {e}")

        # Extract visible market status and index from DOM
        try:
            # Check market status text (e.g. "Market Open", "Market Closed")
            status_elements = await page.query_selector_all(".market-status, .status, .market-open, span:has-text('Market')")
            for el in status_elements:
                txt = (await el.inner_text()).strip()
                if "open" in txt.lower() or "closed" in txt.lower():
                    market_data["market_status"] = txt
                    break
        except Exception:
            pass

        try:
            # Check live index text
            index_el = await page.query_selector(".index-value, .current-index, .nepse-index")
            if index_el:
                market_data["nepse_index_dom"] = (await index_el.inner_text()).strip()
        except Exception:
            pass

        # 2. Navigate to today-price page to fetch live board
        print("Navigating to https://nepalstock.com/today-price...")
        try:
            await page.goto("https://nepalstock.com/today-price", timeout=35000, wait_until="networkidle")
            await asyncio.sleep(2)
            
            # Select 500 in dropdown if available
            selects = await page.query_selector_all("select")
            for s in selects:
                options = await s.query_selector_all("option")
                opt_texts = [await opt.inner_text() for opt in options]
                if "500" in opt_texts:
                    await s.select_option(value="500")
                    await asyncio.sleep(1)
                    break
                    
            # Click Filter/Search button
            buttons = await page.query_selector_all("button")
            for b in buttons:
                txt = (await b.inner_text()).strip()
                if "Filter" in txt or "Search" in txt:
                    await b.click()
                    await asyncio.sleep(3)
                    break
        except Exception as e:
            print(f"Warning on today-price page load: {e}")

        await browser.close()

    # Save raw snapshot
    out_dir = Path("static_data")
    out_dir.mkdir(exist_ok=True)
    snapshot_path = out_dir / "live_nepse_snapshot.json"
    with open(snapshot_path, "w") as f:
        json.dump(market_data, f, indent=2, default=str)
        
    print(f"\nLive snapshot written to {snapshot_path}")
    return market_data

if __name__ == "__main__":
    asyncio.run(fetch_live_nepse())
