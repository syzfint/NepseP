import asyncio
from playwright.async_api import async_playwright

async def capture_auth_headers():
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
                if "authorization" in headers:
                    headers_captured["auth"] = headers["authorization"]
                    print("[TOKEN CAPTURED]:", headers["authorization"][:40] + "...")

        page.on("request", on_request)

        print("Navigating to https://nepalstock.com/floor-sheet...")
        await page.goto("https://nepalstock.com/floor-sheet", timeout=45000, wait_until="networkidle")
        await asyncio.sleep(2)
        
        # Test evaluate with captured token
        if "auth" in headers_captured:
            token = headers_captured["auth"]
            test_fetch = f"""
            async () => {{
                const res = await fetch('/api/nots/nepse-data/floorsheet?&sort=contractId,desc', {{
                    headers: {{
                        'Authorization': '{token}',
                        'Accept': 'application/json, text/plain, */*'
                    }}
                }});
                return await res.json();
            }}
            """
            data = await page.evaluate(test_fetch)
            print("Evaluated floorsheet with token: total trades =", len(data.get("floorsheets", {}).get("content", [])))
            print("Total amount =", data.get("totalAmount"))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_auth_headers())
