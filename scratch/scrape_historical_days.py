import asyncio
import json
import pandas as pd
from playwright.async_api import async_playwright

async def scrape_dates():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        captured_by_date = {}

        async def on_response(response):
            if "today-price" in response.url and response.request.method == "POST":
                try:
                    data = await response.json()
                    content = data.get("content", [])
                    if content:
                        bdate = content[0].get("businessDate")
                        print(f"[CAPTURED]: Date {bdate} -> {len(content)} items (Total: {data.get('totalElements')})")
                        captured_by_date[bdate] = content
                except Exception:
                    pass

        page.on("response", on_response)

        await page.goto("https://nepalstock.com/today-price", timeout=45000, wait_until="networkidle")
        await asyncio.sleep(2)

        # Look at input elements on the page
        inputs = await page.query_selector_all("input")
        print(f"Found {len(inputs)} input elements.")
        for inp in inputs:
            itype = await inp.get_attribute("type")
            iplace = await inp.get_attribute("placeholder")
            iname = await inp.get_attribute("name")
            print(f"Input: type={itype}, name={iname}, placeholder={iplace}")

        # Try to select dates: 2026-10-04 and 2026-10-05
        # Also check datepicker or date input
        for target_date in ["2026-10-05", "2026-10-04"]:
            date_input = await page.query_selector("input[type='date'], input.dp-picker-input, input[placeholder*='Date']")
            if date_input:
                await date_input.fill(target_date)
                print(f"Filled date input with {target_date}")
                await asyncio.sleep(1)

                # Select 500
                selects = await page.query_selector_all("select")
                for s in selects:
                    options = await s.query_selector_all("option")
                    opt_texts = [await opt.inner_text() for opt in options]
                    if "500" in opt_texts:
                        await s.select_option(value="500")

                # Click filter
                buttons = await page.query_selector_all("button")
                for b in buttons:
                    txt = (await b.inner_text()).strip()
                    if "Filter" in txt:
                        await b.click()
                        await asyncio.sleep(4)
                        break

        for bdate, content in captured_by_date.items():
            if bdate:
                clean_date = bdate.replace("-", "_")
                out_path = f"nepse_data_all/{clean_date}.csv"
                pd.DataFrame(content).to_csv(out_path, index=False)
                print(f"Successfully saved {len(content)} records to {out_path}!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_dates())
