import re
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError

class ShareSansarScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_url = "https://www.sharesansar.com/"
        self.service = scraper_service
        self.tz = pytz.timezone('Asia/Kathmandu')

    def make_request_url(self, href):
        return self.base_url.strip().rstrip("/") + "/" + href.strip().lstrip("/")

    def start(self):
        self.get_page_listings()

    def get_page_listings(self):
        categories = [
            "exclusive", "dividend-right-bonus", "latest", "interview",
            "ipo-fpo-news", "share-listed", "expert-speak", 
            "mutual-fund", "weekly-analysis", "company-analysis"
        ]
        for category in categories:
            self.service.log.info(f"Current Category: {category}")
            page_url = self.make_request_url(f"category/{category}")
            self.extract_articles(page_url)

    def extract_articles(self, page_url, depth=1): #scraping only1 page , depth= no. of pages to scrape
        current_depth = 0
        while current_depth < depth:
            try:
                page_content = self.service.make_get_request(page_url)
                if not page_content:
                    break
                soup = BeautifulSoup(page_content, "html.parser")
                links = self.extract_links(soup)
                for link in links:
                    self.get_details(link)
                next_url = self.get_next_page_url(soup, page_url)
                if next_url:
                    page_url = next_url
                    current_depth += 1
                    self.service.log.info(f"Moving to next page: {page_url}")
                else:
                    self.service.log.info("No more pages to scrape.")
                    break
            except ScraperError as e:
                self.service.log.error(f"ScraperError: {e.message}")
            except Exception as e:
                self.service.log.error(f"Unexpected error while processing page {page_url}: {e}")

    def extract_links(self, soup):
        containers = soup.find_all("div", class_="featured-news-list margin-bottom-15")
        unique_links = set()
        pattern = r'<a\s+[^>]*href="(https?://[^"]*newsdetail[^"]*)"'
        for container in containers:
            links = re.findall(pattern, str(container))
            unique_links.update(links)
        return unique_links

    def get_next_page_url(self, soup, current_url):
       
        pagination = soup.find('ul', class_='pagination')
        if pagination:
            for li in pagination.find_all('li', class_='page-item'):
                a_tag = li.find('a', class_='page-link')
                if a_tag and 'next' in a_tag.get('rel', []):
                    return current_url + a_tag['href']
        return None

    def get_details(self, url):
        try:
            page_content = self.service.make_get_request(url)
            if not page_content:
                return
            soup = BeautifulSoup(page_content, "html.parser")
            news_data = self.extract_page_data(soup, url)
            if news_data:
                self.service.save_json(news_data, news_data["title"], "sharesansar")
        except ScraperError as e:
            self.service.log.error(f"ScraperError: {e.message}")
        except Exception as e:
            self.service.log.error(f"Unexpected error in get_details: {e}")

    def extract_page_data(self, soup, url):

        news_title = self.extract_title(soup)
        published_date_time = self.extract_published_date(soup)
        if not published_date_time:
            return None
        published_date, published_time = published_date_time.split(" ")
        categories = self.extract_category(soup)
        author = self.extract_author(soup)
        content = self.extract_content(soup)
        return {
            "url": url,
            "title": news_title,
            "category": categories,
            "author": author,
            "published_date": published_date,
            "published_time": published_time,
            "content": content
        }

    def extract_title(self, soup):
        # Extract news title
        news_container = soup.find("div", class_="detail")
        if news_container:
            header = news_container.find("h1")
            if header:
                return header.text.strip()
        return "N/A"

    def extract_category(self, soup):
        # Extract categories
        categories = []
        category_container = soup.find("h5")
        if category_container:
            anchor_tags = category_container.find_all("a", {"class": "tags"})
            categories = [anchor.get_text() for anchor in anchor_tags]
        return categories

    def extract_author(self, soup):
        author_container = soup.find("a", {"class": "pull-right"})
        return author_container.text.strip() if author_container else "Unknown"

    def extract_content(self, soup):
        content_container = soup.find("div", {"id": "newsdetail-content"})
        return content_container.text.strip() if content_container else "None"

    def extract_published_date(self, soup):
        date_time_container = soup.find("h5")
        if not date_time_container:
            self.service.log.error("Date and time container not found.")
            return None
        date_text = date_time_container.text.strip()
        pattern = r"([A-Za-z]{3},\s[A-Za-z]{3}\s\d{1,2},\s\d{4}\s\d{1,2}:\d{2}\s[APM]{2})|([A-Za-z]+ \d{1,2}, \d{4} \d{1,2}:\d{2} [APM]{2})"
        date_match = re.search(pattern, date_text)
        if date_match:
            if date_match.group(1):  # e.g., "Mon, Apr 28, 2025 4:19 PM"
                extracted_date_time = date_match.group(1)
                date_format = "%a, %b %d, %Y %I:%M %p"
            elif date_match.group(2):  # e.g., "April 28, 2025 4:19 PM"
                extracted_date_time = date_match.group(2)
                date_format = "%B %d, %Y %I:%M %p"
            try:
                date_obj = datetime.strptime(extracted_date_time, date_format)
                date_obj = self.tz.localize(date_obj)
                now = datetime.now(self.tz)
                threshold = 1
                if now - date_obj >= timedelta(hours=threshold):
                    self.service.log.info(
                        f"Skipping {extracted_date_time} as it is older than the threshold."
                    )
                    return None
                return date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                self.service.log.error("Error parsing date.")
                return None
        self.service.log.error("Date pattern not matched.")
        return None

def main():
    scraper_service = ScraperService()
    scraper = ShareSansarScraper(scraper_service)
    scraper.start()

if __name__ == "__main__":
    main()