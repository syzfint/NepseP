import asyncio
import json
import pandas as pd
from playwright.async_api import async_playwright

async def get_all_today_prices_500():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        today_prices = []

        async def on_response(response):
            if "today-price" in response.url and response.request.method == "POST":
                try:
                    data = await response.json()
                    content = data.get("content", [])
                    print(f"[TODAY-PRICE RESPONSE]: received {len(content)} items! (Total in DB: {data.get('totalElements')})")
                    if len(content) > len(today_prices):
                        today_prices.clear()
                        today_prices.extend(content)
                except Exception as e:
                    pass

        page.on("response", on_response)

        print("Navigating to https://nepalstock.com/today-price...")
        await page.goto("https://nepalstock.com/today-price", timeout=45000, wait_until="networkidle")
        await asyncio.sleep(2)

        # Select 500 in dropdown
        selects = await page.query_selector_all("select")
        for s in selects:
            options = await s.query_selector_all("option")
            opt_texts = [await opt.inner_text() for opt in options]
            if "500" in opt_texts:
                await s.select_option(value="500")
                print("Selected 500 in dropdown.")
                await asyncio.sleep(1)

        # Click Filter button
        buttons = await page.query_selector_all("button")
        for b in buttons:
            txt = (await b.inner_text()).strip()
            print(f"Button found: '{txt}'")
            if "Filter" in txt or "Search" in txt:
                print(f"Clicking button: '{txt}'")
                await b.click()
                await asyncio.sleep(4)
                break

        print(f"Total items captured: {len(today_prices)}")
        if today_prices:
            df = pd.DataFrame(today_prices)
            out_file = "nepse_data_all/2026_10_06.csv"
            df.to_csv(out_file, index=False)
            print(f"SUCCESS: Saved {len(df)} records for 2026-10-06 to {out_file}!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_all_today_prices_500())
