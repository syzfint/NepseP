import asyncio
from playwright.async_api import async_playwright

async def test_nepse_headless():
    print("Launching Chromium...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        intercepted_apis = []
        
        async def on_response(response):
            url = response.url
            if "api" in url or "socket" in url:
                intercepted_apis.append({
                    "url": url,
                    "status": response.status,
                    "content_type": response.headers.get("content-type", "")
                })
                print(f"[INTERCEPT] {response.status} -> {url[:90]}")

        page.on("response", on_response)
        
        print("Navigating to https://nepalstock.com...")
        try:
            await page.goto("https://nepalstock.com", timeout=30000, wait_until="domcontentloaded")
            print("Page title:", await page.title())
            await asyncio.sleep(5) # Allow dynamic tokens / APIs to load
        except Exception as e:
            print("Navigation error:", e)
        finally:
            await browser.close()
            
    print(f"\nTotal APIs intercepted: {len(intercepted_apis)}")

if __name__ == "__main__":
    asyncio.run(test_nepse_headless())
