import asyncio
import json
from playwright.async_api import async_playwright

async def intercept_today():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        api_responses = {}

        async def on_response(response):
            url = response.url
            if "/api/nots/" in url:
                try:
                    data = await response.json()
                    api_responses[url] = data
                    print(f"[API INTERCEPTED]: {url} -> {type(data)} (len: {len(data) if isinstance(data, (list, dict)) else 1})")
                except Exception:
                    pass

        page.on("response", on_response)

        print("Navigating to https://nepalstock.com/today-price...")
        await page.goto("https://nepalstock.com/today-price", timeout=45000, wait_until="networkidle")
        await asyncio.sleep(3)

        with open("scratch/intercepted_today_price.json", "w", encoding="utf-8") as f:
            json.dump(api_responses, f, indent=2)

        print(f"Total API endpoints captured: {len(api_responses)}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(intercept_today())
