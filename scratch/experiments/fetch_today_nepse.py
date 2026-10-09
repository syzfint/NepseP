import asyncio
import json
from playwright.async_api import async_playwright

async def capture_live_today():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        headers_captured = {}

        async def on_request(request):
            url = request.url
            if "/api/nots/" in url:
                headers = request.headers
                if "authorization" in headers and "auth" not in headers_captured:
                    headers_captured["auth"] = headers["authorization"]
                    print("[TOKEN CAPTURED]:", headers["authorization"][:30] + "...")

        page.on("request", on_request)

        print("Navigating to https://nepalstock.com/today-price...")
        await page.goto("https://nepalstock.com/today-price", timeout=45000, wait_until="networkidle")
        await asyncio.sleep(2)
        
        # Check today's price / market summary
        token = headers_captured.get("auth", "")
        test_fetch = f"""
        async () => {{
            const headers = {{
                'Authorization': '{token}',
                'Accept': 'application/json, text/plain, */*'
            }};
            const r1 = await fetch('/api/nots/nepse-data/today-price?page=0&size=500', {{ headers }});
            const d1 = await r1.json();
            const r2 = await fetch('/api/nots/nepse-data/market-open', {{ headers }});
            const d2 = await r2.json();
            return {{ today_price: d1, market_open: d2 }};
        }}
        """
        data = await page.evaluate(test_fetch)
        
        with open("scratch/today_live_fetch.json", "w") as f:
            json.dump(data, f, indent=2)
            
        print("Market Open info:", data.get("market_open"))
        tp = data.get("today_price", {})
        if isinstance(tp, dict):
            items = tp.get("content", [])
            print(f"Today price items count: {len(items)}")
            if items:
                print("First item sample:", items[0])
        elif isinstance(tp, list):
            print(f"Today price list count: {len(tp)}")
            if tp:
                print("First item sample:", tp[0])

        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_live_today())
