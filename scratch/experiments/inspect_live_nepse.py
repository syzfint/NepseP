import asyncio
import json
from playwright.async_api import async_playwright

async def inspect_today_price_and_floorsheet():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        live_data_payloads = {}

        async def on_response(response):
            url = response.url
            if "/api/nots/" in url:
                try:
                    ctype = response.headers.get("content-type", "")
                    if "json" in ctype:
                        data = await response.json()
                        live_data_payloads[url] = data
                        print(f"[LIVE DATA INTERCEPT] {url} -> {type(data)} with {len(data) if isinstance(data, (list, dict)) else 0} items")
                except Exception as e:
                    pass

        page.on("response", on_response)

        print("Navigating to Today's Price / Live Market...")
        await page.goto("https://nepalstock.com/today-price", timeout=30000, wait_until="networkidle")
        await asyncio.sleep(3)

        print("\nNavigating to Floorsheet...")
        await page.goto("https://nepalstock.com/floor-sheet", timeout=30000, wait_until="networkidle")
        await asyncio.sleep(3)

        await browser.close()

        with open("scratch/live_nepse_dump.json", "w", encoding="utf-8") as f:
            # Save summaries
            summary = {k: (v if not isinstance(v, list) else v[:5]) for k, v in live_data_payloads.items()}
            json.dump(summary, f, indent=2)
        print("\nSaved intercepted samples to scratch/live_nepse_dump.json")

if __name__ == "__main__":
    asyncio.run(inspect_today_price_and_floorsheet())
