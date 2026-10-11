import json
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService


class NepaliPaisaScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_url = "https://nepalipaisa.com"
        self.service = scraper_service
        self.tz = pytz.timezone('Asia/Kathmandu')
        self.headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,ne;q=0.7,pt;q=0.6",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/news",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }

    def make_request_url(self, path):
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def start(self):
        self.scrape_news_listings()

    def scrape_news_listings(self):
        page = 1
        max_pages = 2 
        while page <= max_pages:
            self.service.log.info(f"Fetching page {page}")
            news_list = self.fetch_news_page(page)
            self.service.log.info(f"Received response for page {page}: status {news_list.get('statusCode') if news_list else 'None'}")

            if not self.should_continue_scraping(news_list, page):
                self.service.log.info(f"Stopping scraping at page {page}")
                break
            
            has_recent = False
            for news_item in self.extract_news_items(news_list):
                has_recent = True
                self.process_news_item(news_item)
            
            if not has_recent:
                self.service.log.info(f"No recent articles on page {page}. Stopping.")
                break
            
            page += 1
        
        if page > max_pages:
            self.service.log.info(f"Reached maximum page limit ({max_pages}). Stopping.")

    def fetch_news_page(self, page_number):
        payload = self._build_listing_payload(page_number)
        endpoint = self.make_request_url("api/GetNewsList")
        return self.service.make_post_request(endpoint, data=json.dumps(payload), headers=self.headers)

    def _build_listing_payload(self, page_number):
        return {
            "dateType": "",
            "dateFrom": "",
            "dateTo": "",
            "sectors": [],
            "companies": [],
            "categoryId": 0,
            "subCategoryId": 0,
            "pageNo": page_number,
            "itemsPerPage": 24,
            "pagePerDisplay": 10,
            "newsType": "",
            "sectorGroup": "",
        }

    def should_continue_scraping(self, news_list, page):
        if not news_list:
            self.service.log.info(f"Empty response at page {page}. Stopping.")
            return False
        
        if news_list.get("statusCode") != 200:
            self.service.log.info(f"Non-200 status at page {page}. Stopping.")
            return False
            
        if not news_list.get("result", {}).get("data"):
            self.service.log.info(f"No more data at page {page}. Stopping.")
            return False
            
        return True

    def extract_news_items(self, news_list):
        for news_group in news_list.get("result", {}).get("data", []):
            if not self.is_recent_news(news_group.get("newsDate")):
                continue
                
            yield from news_group.get("newsData", [])

    def is_recent_news(self, news_date):
        if not news_date:
            return True  # If no date, process anyway
            
        try:
            date_obj = datetime.strptime(news_date, "%Y-%m-%d")
            date_obj = self.tz.localize(date_obj)
            return (datetime.now(self.tz) - date_obj) <= timedelta(days=1)
        except ValueError as e:
            self.service.log.warning(f"Invalid date format {news_date}: {e}")
            return True  # Process anyway if date parsing fails

    def process_news_item(self, news_item):
        news_id = news_item.get("newsId")
        if not news_id:
            self.service.log.warning("No newsId found in news_item")
            return

        self.service.log.info(f"Fetching details for news ID {news_id}")   
        details = self.fetch_news_details(news_id)
        self.service.log.info(f"Received details for news ID {news_id}")
        if not details:
            self.service.log.warning(f"No details fetched for news ID {news_id}")
            return
            
        article_data = self._build_article_data(news_item, details)
        self.service.save_json(article_data, article_data["title"], "nepalipaisa")

    def fetch_news_details(self, news_id):
        api_url = self.make_request_url(f"api/GetNews?newsId={news_id}")
        response = self.service.make_get_request(api_url)
        
        if not response:
            self.service.log.error(f"Failed to fetch details for news ID {news_id}")
            return None
            
        try:
            data = json.loads(response)
            return self._parse_news_details(data.get("result", {}), news_id)
        except json.JSONDecodeError as e:
            self.service.log.error(f"Invalid JSON for news ID {news_id}: {e}")
            return None

    def _parse_news_details(self, result, news_id):
        content_parts = []
        for desc in result.get("descriptions", []):
            soup = BeautifulSoup(desc.get("description", ""), "html.parser")
            content_parts.append(soup.get_text(separator="\n", strip=True))
            
        return {
            "content": "\n\n".join(content_parts),
            "url": self.make_request_url(f"news-detail/{news_id}"),
            "news_source": result.get("newsSource", "")
        }

    def _build_article_data(self, news_item, details):
        return {
            "url": details["url"],
            "published_date": news_item.get("newsDate", "n/a"),
            "published_time": "n/a",
            "category": news_item.get("category", ""),
            "author": "NepaliPaisa",
            "title": news_item.get("newsTitle", ""),
            "content": details["content"],
            "image_url": news_item.get("imageUrl", ""),
            "company_symbols": [c["stockSymbol"] for c in news_item.get("companies", [])]
        }


def main():
    scraper_service = ScraperService()
    scraper = NepaliPaisaScraper(scraper_service)
    scraper.start()


if __name__ == "__main__":
    main()

# steps:  inspect -> network -> "Load More" -> check for api -> right click -> copy -> copy as curl

# curl 'https://www.nepalipaisa.com/api/GetNewsList' \
#   -H 'Accept: application/json, text/javascript, */*; q=0.01' \
#   -H 'Accept-Language: en-US,en;q=0.9,fr;q=0.8,ne;q=0.7,pt;q=0.6' \
#   -H 'Connection: keep-alive' \
#   -H 'Content-Type: application/json; charset=UTF-8' \
#   -H 'Origin: https://www.nepalipaisa.com' \
#   -H 'Referer: https://www.nepalipaisa.com/news' \
#   -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36' \
#   -H 'X-Requested-With: XMLHttpRequest' \

#   --data-raw '{"dateType":"","dateFrom":"","dateTo":"","sectors":[],"companies":[],"categoryId":0,"subCategoryId":0,"pageNo":2,"itemsPerPage":12,"pagePerDisplay":10,"newsType":"","sectorGroup":""}'