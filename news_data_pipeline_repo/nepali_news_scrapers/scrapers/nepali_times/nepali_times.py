import os
import json
import time
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from nepali_news_scrapers.services.scraper_service.scraper_service import Scraper, ScraperService

class NepaliTimesScraper(Scraper):
    def __init__(self, scraper_service: ScraperService):
        self.service = scraper_service
        self.graphql_url = "https://nepalitimes-hasura.superdesk.org/v1/graphql"
        self.base_url = "https://nepalitimes.com"
        self.headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/133.0.0.0 Safari/537.36",
        }
        self.tz = pytz.timezone('Asia/Kathmandu')  # Initialize timezone
        self.categories = {
            "news": 8,
            "multimedia": 40,
            "here-now": 41,  # features
            "editorial": 43,
            "opinion": 12,
            "opinion/missmotivation": 65,
            "opinion/angrezi": 71,
            "iwitness": 69,
            "review": 11,
            "business": 9,
            "margins": 68,
        }

    def make_request_url(self, url: str) -> str:
        return self.base_url.strip().rstrip("/") + "/" + url.strip().lstrip("/")

    def start(self):
        try:
            for category, route_id in self.categories.items():
                self.service.log.info(f"Scraping Category: {category}")
                articles = self.fetch_articles(route_id)
                self.service.log.info(f"Fetched {len(articles)} articles for category '{category}'.")
                for article in articles:
                    self.process_article(article, category)
        except Exception as e:
            self.service.log.error(f"Error scraping Nepali Times: {str(e)}")

    def fetch_articles(self, route_id: int) -> list:
        payload = {
            "query": """
            query getArticles($routeId: Int) {
                items: swp_article(offset: 0, limit: 50, order_by: {published_at: desc}, where: {route_id: {_eq: $routeId}}) {
                    id
                    title
                    published_at
                    slug
                    swp_route { staticprefix }
                }
            }
            """,
            "variables": {"routeId": route_id},
        }
        response = self.service.make_post_request(
            self.graphql_url, data=json.dumps(payload), headers=self.headers
        )
        if not response:
            self.service.log.error(f"GraphQL request failed for route ID {route_id}")
            return []
        return response.get("data", {}).get("items", [])

    def parse_published_date(self, published_at_str: str) -> datetime | None:
        try:
            dt = datetime.fromisoformat(published_at_str)
            if dt.tzinfo is None:
                return self.tz.localize(dt)  
            return dt.astimezone(self.tz)  # Convert to Kathmandu timezone if already timezone-aware
        except Exception as e:
            self.service.log.error(f"Date parsing error: {e}")
            return None

    def is_recent(self, dt: datetime) -> bool:
        if dt is None:
            return False
        now = datetime.now(self.tz)
        return now - dt < timedelta(days=1)

    def process_article(self, article, category: str):
        news_id = article.get("id")
        title = article.get("title")
        published_at_str = article.get("published_at")
        slug = article.get("slug")
        staticprefix = article.get("swp_route", {}).get("staticprefix", "")
        article_link = f"{self.base_url}{staticprefix}/{slug}"

        dt = self.parse_published_date(published_at_str)
        if not self.is_recent(dt):
            self.service.log.info(f"Skipping old article: {title}")
            return

        content = self.get_details(article_link)
        if content:
            article_data = {
                "id": news_id,
                "title": title,
                "published_date": dt.strftime("%Y-%m-%d"),
                "published_time": dt.strftime("%H:%M:%S"),
                "url": article_link,
                "category": category,
                "content": content,
            }
            self.service.save_json(article_data, title, "NepaliTimes")
        else:
            self.service.log.error(f"Failed to retrieve details for article: {article_link}")

    def get_details(self, url: str) -> str | None:
        response = self.service.make_get_request(url, headers=self.headers)
        if not response:
            self.service.log.error(f"Failed to fetch article content from {url}")
            return None
        try:
            return self.parse_article_html(response)
        except Exception as e:
            self.service.log.error(f"Error parsing HTML for {url}: {e}")
            return None

    def parse_article_html(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        subheading = soup.find("span", class_="article__subhead")
        article_body = soup.find("div", class_="article__text")
        if not article_body:
            self.service.log.warning(f"Article body not found in HTML")
            return None
        for tag in article_body.find_all(["script", "style", "iframe", "nav", "footer", "aside", "figure"]):
            tag.decompose()
        content = ""
        if subheading:
            content += subheading.get_text(strip=True) + "\n\n"
        content += article_body.get_text("\n", strip=True)
        return content.strip()

def main():
    scraper_service = ScraperService()
    scraper = NepaliTimesScraper(scraper_service)
    scraper.start()

if __name__ == "__main__":
    main()



# curl --insecure "https://nepalitimes-hasura.superdesk.org/v1/graphql" -H "accept: */*" -H "accept-language: en-US,en;q=0.6" -H "content-type: application/json" -H "origin: https://nepalitimes.com" -H "priority: u=1, i" -H "referer: https://nepalitimes.com/" -H "sec-ch-ua: \"Brave\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"" -H "sec-ch-ua-mobile: ?0" -H "sec-ch-ua-platform: \"Windows\"" -H "sec-fetch-dest: empty" -H "sec-fetch-mode: cors" -H "sec-fetch-site: cross-site" -H "sec-gpc: 1" -H "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36" --data-raw "{\"query\":\"query getArticles($tenant_code: String = \\\"\\\", $routeId: Int, $limit: Int = 10, $offset: Int = 0) { metadata: swp_article_aggregate(where: {tenant_code: {_eq: $tenant_code}, route_id: {_eq: $routeId}}) { aggregate { totalCount: count } } items: swp_article(limit: $limit, offset: $offset, order_by: {published_at: desc}, where: {tenant_code: {_eq: $tenant_code}, route_id: {_eq: $routeId}}) { id comments_count lead paywall_secured published_at slug title body swp_article_authors { swp_author { name role avatar_url slug biography } } swp_article_extra { embed field_name value } swp_article_feature_media { renditions: swp_image_renditions { name width height image: swp_image { asset_id file_extension variants } } } swp_slideshows { id } swp_route { id staticprefix name description } swp_article_metadata { profile byline } } }\",\"variables\":{\"tenant_code\":\"epz639\",\"routeId\":8,\"limit\":10,\"offset\":10}}"