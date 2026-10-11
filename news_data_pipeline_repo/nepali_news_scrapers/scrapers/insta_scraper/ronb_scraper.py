import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import random
import pytz
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError
from ...services.llm.factory import get_llm_provider

self_llm = None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 OPR/77.0.4054.203",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
]

class InstagramScraper:
    def __init__(self, scraper_service: ScraperService):
        self.service = scraper_service
        self.category = "social_media"
        self.tz = pytz.timezone('Asia/Kathmandu')  # Initialize timezone

    def get_random_user_agent(self) -> str:
        """Returns a random user agent from the USER_AGENTS list."""
        return random.choice(USER_AGENTS)

    def get_random_headers(self) -> Dict:
        """Generates and returns a dictionary of HTTP headers with a random user agent."""
        return {
            "x-ig-app-id": "936619743392459",
            "User-Agent": self.get_random_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "*/*",
            "Referer": "https://www.instagram.com/",
            "Origin": "https://www.instagram.com",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def fetch_user_profile(self, username: str) -> Optional[Dict]:
        """Fetches the Instagram user profile data for the given username."""
        url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers = self.get_random_headers()
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.service.log.error(f"Failed to fetch user profile: {e}")
            return None

    def extract_posts(self, profile_data: Dict, max_posts: int = 10) -> List[Dict]:
        """Extracts a list of posts from the profile data, limited to max_posts."""
        posts = profile_data.get("data", {}).get("user", {}).get("edge_owner_to_timeline_media", {}).get("edges", [])
        return posts[:max_posts]

    def process_post(self, node: Dict, username: str, current_time: datetime) -> Optional[Dict]:
        """Processes a single post node and returns its information if valid."""
        timestamp = node.get("taken_at_timestamp", None)
        if not timestamp:
            self.service.log.info(f"Skipping post {node.get('id')} due to missing timestamp.")
            return None

        published_date = datetime.fromtimestamp(timestamp, tz=self.tz).strftime("%Y-%m-%d")
        published_time = datetime.fromtimestamp(timestamp, tz=self.tz).strftime("%H:%M:%S")
        post_datetime = self.tz.localize(datetime.strptime(f"{published_date} {published_time}", "%Y-%m-%d %H:%M:%S"))

        time_difference = current_time - post_datetime
        if time_difference > timedelta(hours=1):
            self.service.log.info(f"Skipping post {node.get('id')} as it is older than 1 hour.")
            return None

        post_info = {
            "id": node.get("id", "N/A"),
            "content": "",
            "likes_count": node.get("edge_media_preview_like", {}).get("count", 0),
            "comments_count": node.get("edge_media_to_comment", {}).get("count", 0),
            "title": f"post by {username}",
            "author": username,
            "published_date": published_date,
            "published_time": published_time,
            "category": self.category,
            "url": f"https://www.instagram.com/p/{node.get('shortcode', '')}",
        }

        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        if caption_edges:
            post_info["content"] = caption_edges[0].get("node", {}).get("text", "")

        if not post_info["content"]:
            self.service.log.info(f"Skipping post {node.get('id')} due to empty content.")
            return None

        return post_info

    def start(self, payload: Dict, max_posts: int = 10):
        try:
            if not payload:
                username = "routineofnepalbanda"
            else:
                username = payload.get("username")
                if not username:
                    self.service.log.error("No username provided in the payload.")
                    return

            profile_data = self.fetch_user_profile(username)
            if not profile_data:
                return

            posts = self.extract_posts(profile_data, max_posts)
            if not posts:
                self.service.log.info("No posts found for this user.")
                return

            current_time = datetime.now(self.tz)

            for edge in posts:
                node = edge.get("node", {})
                post_info = self.process_post(node, username, current_time)
                if not post_info:
                    continue

                if self.service.db_service.check_if_embeddings_exist(post_info["url"]):
                    self.service.log.info(f"Skipping {post_info['url']}, already exists in the table.")
                    continue

                try:
                    self_llm.summarize_and_score(
                        post_info["content"]
                    )
                except Exception as e:
                    self.service.log.error(f"Failed to summarize and score article: {e}")
                    continue

                self.service.save_json(post_info, f"instagram_{username}", f"post_{post_info['id']}")

                time.sleep(2)

        except Exception as e:
            self.service.log.error(f"Error scraping Instagram posts: {e}")

if __name__ == "__main__":
    scraper_service = ScraperService()
    insta_scraper = InstagramScraper(scraper_service)
    payload = {"username": "routineofnepalbanda"}
    insta_scraper.start(payload=payload)