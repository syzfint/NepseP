import re
import json
import time
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError

class MeroLaganiScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_urls = {
            "NP": "http://merolagani.com/",
            "ENG": "http://eng.merolagani.com/",
        }
        self.service = scraper_service
        self.tz = pytz.timezone('Asia/Kathmandu')

    def make_request_url(self, url, lang):
        base_url = self.base_urls.get(lang, self.base_urls["NP"])
        return base_url.rstrip("/") + "/" + url.lstrip("/")

    def start(self):
        for lang in ["NP", "ENG"]:
            try:
                self.get_page_listing(lang)
            except ScraperError as e:
                self.service.log.error(f"Error scraping language {lang}: {e}")

    def fetch_news_list(self, lang, page_num):
        url = self.make_request_url(
            f"/handlers/webrequesthandler.ashx?type=get_news&newsID=0&newsCategoryID=0&symbol=&page={page_num}&pageSize=16&popular=false&includeFeatured=true&news=%23ctl00_ContentPlaceHolder1_txtNews&languageType={lang}",
            lang
        )
        response = self.service.make_get_request(url)
        if not response:
            raise ScraperError(f"Failed to fetch news list from {url}")
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ScraperError(f"Invalid JSON response from {url}: {e}")

    def parse_publication_date(self, date_str):
        try:
            if "." in date_str:
                date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
            return self.tz.localize(date_obj)
        except Exception as e:
            raise ScraperError(f"Error parsing date '{date_str}': {e}")

    def get_page_listing(self, lang):
        page_num = 1
        while page_num <= 3:
            news_list = self.fetch_news_list(lang, page_num)
            for news_item in news_list:
                news_id = news_item.get("newsID")
                news_date_str = news_item.get("newsDateAD")
                if not news_id or not news_date_str:
                    self.service.log.warning(f"Skipping news due to missing data: {news_item}")
                    continue

                date_obj = self.parse_publication_date(news_date_str)
                if datetime.now(self.tz) - date_obj >= timedelta(hours=1):
                    self.service.log.info(f"Skipping news as it is older than the threshold")
                    continue

                details_page_url = self.make_request_url(f"/NewsDetail.aspx?newsID={news_id}", lang)
                try:
                    self.get_page_details(news_id, details_page_url, lang)
                except ScraperError as e:
                    self.service.log.error(f"Error processing newsID {news_id}: {e}")
                    continue
            page_num += 1

    def extract_title(self, soup):
        title_container = soup.find("h4", {"id": "ctl00_ContentPlaceHolder1_newsTitle"})
        if not title_container:
            raise ScraperError("News title not found")
        return title_container.get_text(strip=True)

    def extract_published_date_time(self, soup):
        time_date_container = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_newsDate"})
        if not time_date_container:
            raise ScraperError("News published date not found")
        time_date = time_date_container.text.strip()
        match = re.match(r'([A-Za-z]+ \d{1,2}, \d{4}) (\d{1,2}:\d{2} [APM]+)', time_date)
        if not match:
            raise ScraperError(f"Published date/time format invalid: {time_date}")
        publish_date_str, publish_time_str = match.group(1), match.group(2)
        publish_date = datetime.strptime(publish_date_str, "%b %d, %Y").strftime("%Y-%m-%d")
        publish_time = datetime.strptime(publish_time_str, "%I:%M %p").strftime("%H:%M:%S")
        return publish_date, publish_time

    def extract_source(self, soup):
        news_source_container = soup.find("span", {"id": "ctl00_ContentPlaceHolder1_newsSource"})
        if not news_source_container:
            raise ScraperError("News source not found")
        return news_source_container.text.strip()

    def extract_overview(self, soup):
        news_overview_container = soup.find("div", {"id": "ctl00_ContentPlaceHolder1_newsOverview"})
        return news_overview_container.text.strip() if news_overview_container else ""

    def extract_content(self, soup):
        content_container = soup.find("div", {"id": "ctl00_ContentPlaceHolder1_newsDetail"})
        if not content_container:
            raise ScraperError("News content not found")
        return content_container.text.strip()

    def extract_category(self, soup):
        category_container = soup.find("ul", class_="breadcrumb")
        if category_container:
            breadcrumb_items = category_container.find_all("li")
            return breadcrumb_items[-1].get_text(strip=True) if breadcrumb_items else "Economy"
        return "Uncategorized"

    def get_page_details(self, news_id, url, lang):
        page_content = self.service.make_get_request(url)
        if not page_content:
            raise ScraperError(f"Failed to fetch news details for newsID {news_id} from {url}")
        soup = BeautifulSoup(page_content, "html.parser")

        news_title = self.extract_title(soup)
        publish_date, publish_time = self.extract_published_date_time(soup)
        news_source = self.extract_source(soup)
        news_overview = self.extract_overview(soup)
        content = self.extract_content(soup)
        category = self.extract_category(soup)

        news_data = {
            "url": url,
            "title": news_title,
            "category": category,
            "author": news_source,
            "published_time": publish_time,
            "published_date": publish_date,
            "content": news_overview + " " + content
        }
        self.service.save_json(news_data, news_title, "merolagani")
        # self.service.log.info(f"Saved news: {news_data} ({lang})")

def main():
    scraper_service = ScraperService()
    scraper = MeroLaganiScraper(scraper_service)
    scraper.start()

if __name__ == "__main__":
    main()