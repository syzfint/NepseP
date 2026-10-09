import asyncio
import json
from playwright.async_api import async_playwright

async def inspect_requests():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        requests_info = []

        async def on_request(request):
            if "today-price" in request.url:
                requests_info.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": request.headers,
                    "post_data": request.post_data
                })
                print(f"[REQUEST]: {request.method} {request.url}")
                print(f"Post data: {request.post_data}")

        page.on("request", on_request)

        await page.goto("https://nepalstock.com/today-price", timeout=45000, wait_until="networkidle")
        await asyncio.sleep(2)

        with open("scratch/today_price_requests.json", "w") as f:
            json.dump(requests_info, f, indent=2)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_requests())
