import json
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
import time
import pytz
import traceback
from bs4 import BeautifulSoup
from nepali_news_scrapers.services.scraper_service import ScraperService, ScraperError
from nepali.date_converter import converter

class EkantipurScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_url = "https://ekantipur.com"
        self.unique_links = set()
        self.service = scraper_service
        self.threshold_days = 1
        self.tz = pytz.timezone('Asia/Kathmandu')
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
        }

    def make_request_url(self, href):
        return urljoin(self.base_url, href)

    def start(self):
        try:
            current_date = datetime.now(self.tz)
            current_year = current_date.year
            date_today = current_date.strftime("%Y-%m-%d")
            url = self.make_request_url(
                f"/search/{current_year}/?txtSearch=&year={current_year}&date-from={date_today}&date-to={date_today}"
            )
            self.service.log.info(f"Constructed search URL: {url}")
            self.get_page_listings(url)
        except ScraperError as e:
            self.service.log.error(f"Scraper failed to start: {e}")
            traceback.print_exc()

    def get_page_listings(self, listing_url):
        soup = self.get_soup(listing_url)
        if not soup:
            return
        
        search_container = soup.find("div", class_="search-content-wrapper")
        if search_container:
            self.extract_articles(search_container)
            return
        
        # Fallback for category pages
        blocks = soup.find("div", class_="blocksLayout")
        if blocks:
            self.extract_articles(blocks)
        else:
            self.extract_articles(soup)

    def extract_articles(self, container):
        if not container:
            return
        
        items = container.find_all(["article", "div"], class_=lambda x: x == "news-list" or x is None)
        
        self.service.log.info(f"Found {len(items)} potential items in container.")

        for item in items:
            for a in item.find_all("a"):
                href = a.get("href")
                if href and "/author" not in href and "/2026/" in href:
                    self.process_article(href)

    def process_article(self, href):
        full_url = self.make_request_url(href)
        if full_url not in self.unique_links:
            self.unique_links.add(full_url)
            try:
                self.get_details(full_url)
            except ScraperError as e:
                self.service.log.error(f"Error processing article {full_url}: {e}")
                traceback.print_exc()

    def get_details(self, url):
        self.service.log.info(f"Fetching details for article: {url}")
        soup = self.get_soup(url)
        if not soup:
            self.service.log.error(f"Failed to fetch soup for {url} after retries")
            return

        # 1. Precise Date Extraction (JSON-LD first)
        published_datetime = self.extract_published_date(soup, url)
        if not published_datetime:
            self.service.log.warning(f"Skipping: No date found for {url}")
            return

        # Localize to Nepal
        if published_datetime.tzinfo is None:
            published_datetime = self.tz.localize(published_datetime)

        # 2. 1-Hour Rule Check (Using the precise seconds from JSON-LD)
        current_time = datetime.now(self.tz)
        diff_minutes = (current_time - published_datetime).total_seconds() / 60
        
        if diff_minutes > 65 or diff_minutes < -5:
            self.service.log.info(f"Skipping old article: {diff_minutes:.0f} mins old.")
            return

        # 3. Data Extraction using new Selectors
        news_data = {
            "url": url,
            "title": self.extract_title(soup),
            "category": self.extract_category(soup),
            "author": self.extract_author(soup),
            "published_date": published_datetime.strftime("%Y-%m-%d"),
            "published_time": published_datetime.strftime("%H:%M:%S"),
            "content": self.extract_content(soup),
        }

        if news_data["title"] == "Untitled" or not news_data["content"]:
            return
        self.service.save_json(news_data, news_data["title"], "ekantipur")

    def get_soup(self, url):
        for attempt in range(3):
            page_content = self.service.make_get_request(url, self.headers)
            if page_content:
                return BeautifulSoup(page_content, "html.parser")
                # return BeautifulSoup(page_content, "lxml")
            self.service.log.warning(f"Failed to retrieve content from {url}, attempt {attempt + 1}/3")
            time.sleep(2)
        return None

    def extract_category(self, soup):
        cat_div = soup.find("div", class_="category-name")
        if cat_div:
            return cat_div.get_text(strip=True)
        return "News"


    def extract_title(self, soup):
        section = soup.find("section", class_="news-section-wrap")
        if section:
            title_tag = section.find("h2")
            if title_tag:
                return title_tag.get_text(strip=True)
        # Fallback to standard h1 if section isn't found
        return soup.find("h1").get_text(strip=True) if soup.find("h1") else "Untitled"



    def extract_author(self, soup):
        author_section = soup.find("section", class_="author-list")
        if author_section:
            author_tag = author_section.find("p", class_="inter")
            if author_tag and author_tag.find("span"):
                return [author_tag.find("span").get_text(strip=True)]
        
        # Fallback to the small author link in the date bar
        author_date = soup.find("div", class_="author-date")
        if author_date and author_date.find("a"):
            return [author_date.find("a").get_text(strip=True)]
            
        return ["Unknown"]

    def extract_published_date(self, soup, url):
        """
        Primary: Extract from JSON-LD (precise time).
        Secondary: Fallback to HTML UI parsing.
        """
        # --- Method 1: JSON-LD (Highly Accurate) ---
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                # JSON-LD blocks can be lists or single objects
                data = json.loads(script.string)
                
                # If it's a list, look for the NewsArticle type
                if isinstance(data, list):
                    item = next((i for i in data if i.get("@type") == "NewsArticle"), None)
                elif isinstance(data, dict) and data.get("@type") == "NewsArticle":
                    item = data
                else:
                    item = None

                if item and "datePublished" in item:
                    date_str = item["datePublished"] # Expected: "2026-02-13 22:03:35"
                    # Ekantipur uses "YYYY-MM-DD HH:MM:SS" in their JSON-LD
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue

        # --- Method 2: Fallback to HTML UI (Nepali Text) ---
        self.service.log.info(f"JSON-LD date failed for {url}, trying HTML fallback.")
        
        # Check in .author-date or .published-at
        date_container = soup.find("div", class_="author-date") or soup.find("span", class_="published-at")
        if not date_container:
            return None

        try:
            date_text = date_container.get_text(strip=True).replace("प्रकाशित :", "").replace("अद्यावधिक :", "").strip()
            
            # Use rsplit only if time is detected (contains ':')
            if ":" in date_text:
                date_part, time_part = date_text.rsplit(" ", 1)
            else:
                date_part, time_part = date_text, "00:00"

            date_part_eng = ScraperService.convert_nepali_to_english(date_part)
            time_part_eng = ScraperService.convert_nepali_to_english(time_part)
            
            return self.convert_nepali_date_to_english(date_part_eng, time_part_eng, url)
        except Exception as e:
            self.service.log.warning(f"Fallback date parsing failed for {url}: {e}")
            return None
        
    def convert_nepali_date_to_english(self, date_part_eng, time_part_eng, url):
        parts = date_part_eng.split()
        if len(parts) < 3:
            self.service.log.warning(f"Unexpected date format for {url}")
            return None
        nepali_months = {
            "वैशाख": 1, "बैशाख": 1, "जेष्ठ": 2, "अषाढ": 3, "श्रावण": 4, "भदौ": 5,
            "असोज": 6, "कार्तिक": 7, "मंसिर": 8, "पुष": 9, "माघ": 10,
            "फाल्गुन": 11, "फागुन": 11, "चैत्र": 12,
        }
        np_month = nepali_months.get(parts[0], None)
        if not np_month:
            self.service.log.warning(f"Invalid Nepali month found in date: {url}")
            return None
        np_day = int(parts[1].replace(",", ""))
        np_year = int(parts[2])
        en_year, en_month, en_day = converter.nepali_to_english(np_year, np_month, np_day)
        hour, minute = map(int, time_part_eng.split(":"))
        return datetime(en_year, en_month, en_day, hour, minute)

    def extract_content(self, soup):
        story = soup.find("section", class_="news-section-wrap-story")
        if story:
            paragraphs = story.find_all("p")
            return "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        return ""


        

def main():
    scraper_service = ScraperService()
    scraper = EkantipurScraper(scraper_service)
    scraper.start()

if __name__ == "__main__":
    main()