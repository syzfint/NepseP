import asyncio
import json
import pandas as pd
from playwright.async_api import async_playwright

async def fetch_full_today():
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

        page.on("request", on_request)

        print("Navigating to https://nepalstock.com/today-price...")
        await page.goto("https://nepalstock.com/today-price", timeout=45000, wait_until="networkidle")
        await asyncio.sleep(2)

        token = headers_captured.get("auth", "")
        print(f"Token captured: {token[:30]}...")

        # Fetch today's all pages
        all_today_records = []
        for page_idx in range(20):
            fetch_script = f"""
            async () => {{
                const res = await fetch('/api/nots/nepse-data/today-price?page={page_idx}&size=100', {{
                    headers: {{
                        'Authorization': '{token}',
                        'Accept': 'application/json, text/plain, */*'
                    }}
                }});
                return await res.json();
            }}
            """
            data = await page.evaluate(fetch_script)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("content", [])
            else:
                items = []

            if not items:
                break
            all_today_records.extend(items)
            print(f"Page {page_idx}: fetched {len(items)} items. Total so far: {len(all_today_records)}")
            if isinstance(data, dict) and data.get("last", False):
                break
            if len(items) < 100:
                break

        print(f"\nTotal securities fetched for today ({all_today_records[0].get('businessDate') if all_today_records else 'N/A'}): {len(all_today_records)}")
        
        df_today = pd.DataFrame(all_today_records)
        df_today.to_csv("scratch/today_price_2026_10_06.csv", index=False)
        print("Saved scratch/today_price_2026_10_06.csv")

        # Let's also check market summary / index level for today
        index_script = f"""
        async () => {{
            const res = await fetch('/api/nots/nepse-data/market-summary', {{
                headers: {{
                    'Authorization': '{token}',
                    'Accept': 'application/json, text/plain, */*'
                }}
            }});
            return await res.json();
        }}
        """
        try:
            idx_summary = await page.evaluate(index_script)
            with open("scratch/today_market_summary.json", "w") as f:
                json.dump(idx_summary, f, indent=2)
            print("Market summary:", idx_summary)
        except Exception as e:
            print("Error fetching market summary:", e)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(fetch_full_today())
