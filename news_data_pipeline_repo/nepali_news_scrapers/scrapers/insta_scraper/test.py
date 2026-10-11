import requests
import json


headers = {
    "x-ig-app-id": "936619743392459",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "*/*",
}


def scrape_user(username: str):
    """Scrape Instagram user's data"""
    result = requests.get(
        f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
        headers=headers,
    )

    data = result.text

    with open("./1.json", "w", encoding="utf-8") as f:
        f.write(data)

    data = json.loads(data)
    print(data)
    # return data["data"]["user"]


print(scrape_user("routineofnepalbanda"))
