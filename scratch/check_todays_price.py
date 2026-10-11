from nepse_client import NepseClient
import json

c = NepseClient()
c.setTLSVerification(False)

# Check if NepseClient has a method or test requestPOSTAPI for todays_price
tp_url = c.api_end_points.get('todays_price')
print("todays_price endpoint:", tp_url)

# In NepseClient, what method gets today's price?
for attr in dir(c):
    if 'today' in attr.lower() or 'price' in attr.lower():
        print("Matching method:", attr)

# Let's test calling today's price if available
try:
    if hasattr(c, 'getTodaysPrice'):
        tp = c.getTodaysPrice()
        print(f"getTodaysPrice returned: {type(tp)}, length: {len(tp) if tp else 0}")
        if tp:
            print("First item:", tp[0])
except Exception as e:
    print("getTodaysPrice error:", e)

# Test POST request to todays_price
try:
    # Check payload generator for todays_price
    for gen in [c.getPOSTPayloadIDForScrips, c.getPOSTPayloadIDForFloorSheet]:
        try:
            res = c.requestPOSTAPI(url=f"{tp_url}?size=500", payload_generator=gen)
            print(f"Calling {tp_url} with {gen.__name__}: returned {type(res)}, length: {len(res) if res else 0}")
            if res:
                print("Sample:", res[0] if isinstance(res, list) else list(res.keys()))
                if isinstance(res, dict) and 'content' in res:
                    print("Content length:", len(res['content']), "Sample:", res['content'][0])
                break
        except Exception as e2:
            print(f"Error with {gen.__name__}: {e2}")
except Exception as e:
    print("General error:", e)
