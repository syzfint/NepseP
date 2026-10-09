import asyncio
import json
from playwright.async_api import async_playwright

async def get_indices():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        indices_data = {}

        async def on_response(response):
            if "/api/nots/" in response.url:
                try:
                    data = await response.json()
                    if "index" in response.url.lower() or "summary" in response.url.lower() or "point" in response.url.lower():
                        print(f"Captured: {response.url}")
                        indices_data[response.url] = data
                except Exception:
                    pass

        page.on("response", on_response)

        await page.goto("https://nepalstock.com", timeout=45000, wait_until="networkidle")
        await asyncio.sleep(2)

        # Check what index is displayed on the page
        try:
            nepse_val_el = await page.query_selector(".index-value, .current-index, span:has-text('NEPSE Index') + span, .market-status")
            if nepse_val_el:
                print("Element text:", await nepse_val_el.inner_text())
        except Exception:
            pass

        with open("scratch/live_indices.json", "w") as f:
            json.dump(indices_data, f, indent=2)

        print("Captured index endpoints:", list(indices_data.keys()))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_indices())
