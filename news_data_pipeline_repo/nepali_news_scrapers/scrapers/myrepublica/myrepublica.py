import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import re
import random
import pytz
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class MyRepublicaScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_url = "https://myrepublica.nagariknetwork.com/"
        self.service = scraper_service
        self.listed_urls = set()  # Track processed URLs to avoid duplicates
        self.delay = 3
        self.tz = pytz.timezone('Asia/Kathmandu')
        self.categories = [
            "economy", "politics", "society", "world", "op-ed",
            "republica-watch", "diaspora", "market"
        ]

    def make_request_url(self, relative_url: str) -> str:
        return self.base_url.rstrip("/") + "/" + relative_url.lstrip("/")

    def get_random_user_agent(self) -> str:
        """Return a random User-Agent string."""
        return random.choice(USER_AGENTS)

    def get_request_headers(self) -> dict:
        """Return headers for HTTP requests."""
        return {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.7",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "User-Agent": self.get_random_user_agent(),
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Brave\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\""
        }

    def start(self):
        try:
            self.get_page_category()
        except ScraperError as e:
            self.service.log.error(f"Scraper halted: {e}")

    def get_page_category(self):
        for category in self.categories:
            try:
                self.service.log.info(f"Starting scraping for category: {category}")
                self.get_page_listing(category)
                time.sleep(self.delay)
            except ScraperError as e:
                self.service.log.error(f"Failed to scrape category {category}: {e}")
                continue

    def fetch_page_content(self, url: str, headers: dict = None) -> str:
        content = self.service.make_get_request(url, headers=headers)
        if not content:
            error_msg = f"Failed to fetch page content from {url}"
            self.service.log.error(error_msg)
            raise ScraperError(error_msg)
        if "503 Service Unavailable" in content:
            error_msg = f"Received 503 error for {url}"
            self.service.log.error(error_msg)
            raise ScraperError(error_msg)
        return content

    def get_page_listing(self, category: str):
        page = 1
        while page <= 1:  # Limit to first page for now
            relative_url = f"category/{category}?page={page}"
            page_list_api_endpoint = self.make_request_url(relative_url)
            
            # Process featured sections
            try:
                self.get_featured_sections(page_list_api_endpoint)
            except ScraperError as e:
                self.service.log.error(f"Error in featured sections for {page_list_api_endpoint}: {e}")

            self.service.log.info(f"Fetching page {page} from: {page_list_api_endpoint}")
            page_content = self.fetch_page_content(page_list_api_endpoint)
            time.sleep(self.delay)

            soup = BeautifulSoup(page_content, "html.parser")
            listings = soup.find_all("a", href=re.compile("/news/"))
            if not listings:
                self.service.log.info(f"No more listings found for category '{category}'.")
                break

            for listing in listings:
                news_url = listing.get("href")
                full_news_url = news_url if news_url.startswith("http") else self.make_request_url(news_url)
                if full_news_url in self.listed_urls:
                    continue
                self.listed_urls.add(full_news_url)

                title_elem = listing.find("h3", class_=re.compile("rep-title"))
                title = title_elem.get_text(strip=True) if title_elem else "No Title"
                self.service.log.info(f"Found news: {title} at {full_news_url}")

                news_id_match = re.search(r'-(\d+-\d+)\.html', full_news_url)
                news_id = news_id_match.group(1) if news_id_match else None
                if news_id:
                    self.service.log.info(f"News ID: {news_id}")

                try:
                    self.get_page_details(full_news_url)
                except ScraperError as e:
                    self.service.log.error(f"Error processing {full_news_url}: {e}")
                    continue

                time.sleep(self.delay)
            page += 1
            time.sleep(self.delay)

    def get_featured_sections(self, url: str):
        """Extract and process URLs from featured sections."""
        self.service.log.info(f"Extracting featured sections from: {url}")
        page_content = self.fetch_page_content(url)
        time.sleep(self.delay)

        soup = BeautifulSoup(page_content, "html.parser")
        container_div = soup.find("div", class_="col-span-1 lg:col-span-9")
        if not container_div:
            self.service.log.warning("Featured section container not found.")
            return

        featured_section_links = container_div.find_all("a", href=True)
        urls = [
            tag['href'] for tag in featured_section_links
            if tag['href'].startswith("https://myrepublica.nagariknetwork.com/")
        ]

        for extracted_url in urls:
            if extracted_url in self.listed_urls:
                continue
            self.listed_urls.add(extracted_url)
            try:
                self.get_page_details(extracted_url)
            except ScraperError as e:
                self.service.log.error(f"Error processing featured URL {extracted_url}: {e}")

    def extract_title(self, soup: BeautifulSoup) -> str:
        """Extract the news title from the soup object."""
        news_title_elem = soup.find("h1", {"class": "rep-headline--large"})
        return news_title_elem.get_text(strip=True) if news_title_elem else "No Title"

    def extract_category(self, soup: BeautifulSoup) -> str:
        """Extract the news category from the soup object."""
        category_elems = soup.find_all("span", {"class": "rep-body--small--sans"})
        return category_elems[2].get_text(strip=True) if len(category_elems) >= 3 else "No Category"

    def extract_author(self, soup: BeautifulSoup) -> str:
        """Extract the news author from the soup object."""
        by_span = soup.find("span", {"class": "underline"})
        if by_span:
            a_elem = by_span.find("a")
            return a_elem.get_text(strip=True) if a_elem else "No Author"
        return "No Author"

    def extract_publish_datetime(self, page_text: str) -> tuple:
        """Extract and parse publication date and time."""
        time_date_match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", page_text)
        if time_date_match:
            time_date_str = time_date_match.group(1)
            try:
                publish_datetime = datetime.strptime(time_date_str, "%Y-%m-%dT%H:%M:%S")
                publish_datetime = self.tz.localize(publish_datetime)
                return (
                    publish_datetime.strftime("%Y-%m-%d"),
                    publish_datetime.strftime("%H:%M:%S")
                )
            except Exception as e:
                self.service.log.error(f"Error parsing date/time: {e}")
        return "Unknown", "Unknown"

    def is_news_recent(self, publish_date: str, publish_time: str) -> bool:
        if publish_date == "Unknown" or publish_time == "Unknown":
            return True  # Process if date is unknown to avoid skipping
        try:
            published_datetime_str = f"{publish_date}T{publish_time}"
            published_datetime = datetime.strptime(published_datetime_str, "%Y-%m-%dT%H:%M:%S")
            published_datetime = self.tz.localize(published_datetime)
            current_datetime = datetime.now(self.tz)
            return (current_datetime - published_datetime) <= timedelta(hours=1)
        except Exception as e:
            self.service.log.error(f"Error during datetime comparison: {e}")
            return True  

    def extract_image(self, soup: BeautifulSoup) -> str:
        image_elem = soup.find("img", {"class": "rep-image--full"})
        return image_elem.get("src") if image_elem else "No Image"

    def extract_tags(self, soup: BeautifulSoup) -> list:
        """Extract news tags from the soup object."""
        tags = []
        tag_elems = soup.find_all("span", {"class": "rep-misc__tag"})
        for tag_elem in tag_elems:
            tag_text = tag_elem.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)
        return tags

    def extract_content(self, soup: BeautifulSoup) -> list:
        """Extract the news content as a list of paragraphs."""
        content_div = soup.find("div", {"id": "content"})
        if content_div:
            paragraphs = content_div.find_all("p")
            return [p.get_text(strip=True) for p in paragraphs]
        return []

    def get_page_details(self, url: str):
        """Fetch and process details for a news article."""
        headers = self.get_request_headers()
        self.service.log.info(f"Fetching details for: {url}")
        page_content = self.fetch_page_content(url, headers=headers)
        time.sleep(self.delay)

        soup = BeautifulSoup(page_content, "html.parser")
        news_title = self.extract_title(soup)
        category = self.extract_category(soup)
        author = self.extract_author(soup)
        publish_date, publish_time = self.extract_publish_datetime(page_content)
        
        if not self.is_news_recent(publish_date, publish_time):
            self.service.log.info(f"Skipping news at {url} as it is older than 1 hour")
            return

        image_url = self.extract_image(soup)
        tags = self.extract_tags(soup)
        content = self.extract_content(soup)

        news_data = {
            "url": url,
            "title": news_title,
            "category": category,
            "author": author,
            "published_time": publish_time,
            "published_date": publish_date,
            "content": content,
            "image": image_url,
            "tags": tags
        }

        self.service.save_json(news_data, news_title, "myrepublica")

def main():
    scraper_service = ScraperService()
    scraper = MyRepublicaScraper(scraper_service)
    scraper.start()

if __name__ == "__main__":
    main()