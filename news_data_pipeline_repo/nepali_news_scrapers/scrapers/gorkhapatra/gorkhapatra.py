import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import re
import pytz
from nepali.date_converter import converter
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError

class GorkhaPatraScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_url = "https://gorkhapatraonline.com"
        self.unique_links = set()
        self.service = scraper_service
        self.tz = pytz.timezone('Asia/Kathmandu')

    def make_request_url(self, url):
        return self.base_url.strip().rstrip("/") + "/" + url.strip().lstrip("/")
    
    def start(self):
        try:
            self.get_page_category()
        except ScraperError as e:
            self.service.log.error(f"Error in starting GorkhaPatraScraper: {e}")
            raise
    
    def get_page_category(self):
        categories = [
            "national", "entertainment", "news-today", "", "economy", "editorial",
            "new-nepal", "health", "international", "corporate", "loksewa", "bank",
            "diaspora", "share", "thoughts", "open", "politics", "tourism",
            "education", "interview", "crime", "koshi", "province-two",
            "province-three", "province-four", "province-five", "province-six",
            "province-seven",
        ]
        for category in categories:
            try:
                if category == "":
                    page_url = self.make_request_url(f"{category}")
                else:
                    page_url = self.make_request_url(f"categories/{category}")
                self.get_page_listings(page_url, category)
            except Exception as e:
                error_msg = f"An error occurred while scraping category '{category}': {e}"
                self.service.log.error(error_msg)
                continue

    def get_page_listings(self, page_url, category):
        if category == "":
            self.service.log.info(f"Scraping homepage: {page_url}")
            page_content = self.service.make_get_request(page_url)
            if not page_content:
                error_msg = f"Failed to retrieve homepage content from {page_url}"
                self.service.log.error(error_msg)
                raise ScraperError(error_msg)
            soup = BeautifulSoup(page_content, "html.parser")
            try:
                links = self.extract_article_links(soup)
            except Exception as e:
                error_msg = f"Failed to extract article links from {page_url}: {e}"
                self.service.log.error(error_msg)
                raise ScraperError(error_msg)
            for link in links:
                if link not in self.unique_links:
                    self.unique_links.add(link)
                    try:
                        self.get_page_details(link, category)
                    except ScraperError as e:
                        self.service.log.error(f"Error processing article {link}: {e}")
                else:
                    self.service.log.debug(f"Skipping duplicate link: {link}")
            return
        
        page_num = 1
        while page_num <= 1:
            current_page_url = f"{page_url}?page={page_num}"
            self.service.log.info(f"Scraping Category '{category}' on Page: {current_page_url}")
            page_content = self.service.make_get_request(current_page_url)
            if not page_content:
                self.service.log.error(f"Failed to retrieve page content from {current_page_url}")
                break
            soup = BeautifulSoup(page_content, "html.parser")
            links = self.extract_article_links(soup)
            if not links:
                self.service.log.warning(f"No articles found on {current_page_url}. Stopping pagination.")
                break
            new_links_found = False
            for link in links:
                if link not in self.unique_links:
                    self.unique_links.add(link)
                    try:
                        self.get_page_details(link, category)
                        new_links_found = True
                    except ScraperError as e:
                        self.service.log.error(f"Error processing article {link}: {e}")
            if not new_links_found:
                self.service.log.info(f"No new links found on page {page_num}. Stopping pagination.")
                break
            page_num += 1   
   


    def extract_article_links(self, soup):
        title_elements = soup.find_all(["h2", "h3", "h4", "h1"], class_="item-title")
        links = []
        for title in title_elements:
            a_tag = title.find("a")
            if a_tag and a_tag.get("href"):
                links.append(a_tag["href"])
        return links

    def extract_title(self, soup):
        title_container = soup.find("h1", {"class": "single-top-title mb-3 sticky-title"})
        if not title_container:
            raise ScraperError("Title container not found")
        return title_container.text.strip()

    def extract_author(self, soup):
        author_container = soup.find("div", {"class": "blog-author"})
        if not author_container:
            raise ScraperError("Author container not found")
        return author_container.text.strip().lstrip("By").strip()

    def parse_time_ago(self, time_str):
        match = re.search(r"(\d+)\s*(सेकेण्ड|मिनेट|घण्टा|दिन|हप्ता|महिना|वर्ष)\s+पहिले", time_str)
        if not match:
            return None
        nepali_amount, unit = match.group(1), match.group(2)
        try:
            english_amount = int(self.service.convert_nepali_to_english(nepali_amount))
        except Exception as e:
            self.service.log.error(f"Error converting Nepali number: {e}")
            return None
        current_time = datetime.now(self.tz)
        delta = {
            "सेकेण्ड": timedelta(seconds=english_amount),
            "मिनेट": timedelta(minutes=english_amount),
            "घण्टा": timedelta(hours=english_amount),
            "दिन": timedelta(days=english_amount),
            "हप्ता": timedelta(weeks=english_amount),
            "महिना": timedelta(days=30 * english_amount),
            "वर्ष": timedelta(days=365 * english_amount)
        }.get(unit)
        if delta:
            return current_time - delta
        return None

    def parse_nepali_date(self, date_str):
        try:
            date_part, _ = date_str.split(",", 1)
            date_part = date_part.strip()
            np_day_str, np_month_str, np_year_str = date_part.split()
            np_day = int(self.service.convert_nepali_to_english(np_day_str))
            nepali_months = {
                 "वैशाख":1,"बैशाख": 1, "जेष्ठ": 2, "अषाढ": 3, "श्रावण": 4, "भदौ": 5,
                "असोज": 6, "कार्तिक": 7, "मंसिर": 8, "पुष": 9, "माघ": 10,
                "फागुन": 11, "चैत्र": 12, "चैत": 12
            }
            np_month = nepali_months.get(np_month_str)
            if not np_month:
                raise ValueError(f"Invalid Nepali month: {np_month_str}")
            np_year = int(self.service.convert_nepali_to_english(np_year_str))
            en_year, en_month, en_day = converter.nepali_to_english(np_year, np_month, np_day)
            return self.tz.localize(datetime(en_year, en_month, en_day))
        except Exception as e:
            self.service.log.error(f"Error parsing Nepali date: {e}")
            return None

    def extract_datetime(self, soup):
        date_container = soup.find("span", {"class": "mr-3 font-size-16"})
        if not date_container:
            raise ScraperError("Date container not found")
        date_str = date_container.text.strip()
        published_time_containers = soup.find_all("span", {"class": "mr-3 font-size-16"})
        if len(published_time_containers) >= 2:
            time_ago_str = published_time_containers[1].text.strip()
            actual_time = self.parse_time_ago(time_ago_str)
            if actual_time:
                return actual_time
        if date_str:
            actual_time = self.parse_nepali_date(date_str)
            if actual_time:
                return actual_time
        return datetime.now(self.tz)

    def extract_content(self, soup):
        content_containers = soup.find_all("div", {"class": "blog-details"})
        if len(content_containers) > 3:
            para_container = content_containers[3]
            para_text = para_container.text.strip()
            return para_text.replace("\t", "").replace("\n", "").replace("                            ", "")
        raise ScraperError("Content container not found or insufficient")

    def get_page_details(self, url, category):
        page_content = self.service.make_get_request(url)
        if not page_content:
            error_msg = f"Failed to retrieve article page content from {url}"
            self.service.log.error(error_msg)
            raise ScraperError(error_msg)
        self.service.log.info(f"Fetching article details from {url}")
        soup = BeautifulSoup(page_content, "html.parser")
        
        try:
            news_title = self.extract_title(soup)
            author = self.extract_author(soup)
            actual_time = self.extract_datetime(soup)
            contents_str = self.extract_content(soup)
        except ScraperError as e:
            self.service.log.error(f"Error extracting data from {url}: {e}")
            raise
        
        current_datetime = datetime.now(self.tz)
        if current_datetime - actual_time > timedelta(hours=1):
            self.service.log.info(f"Skipping article {url} as it is older than 1 hour: {actual_time}")
            return
        
        if category == "":
            category = "homepage"
        
        news_data = {
            "url": url,
            "category": category,
            "title": news_title,
            "published_date": actual_time.strftime("%Y-%m-%d"),
            "published_time": actual_time.strftime("%H:%M:%S"),
            "author": author,
            "content": contents_str,
        }
        self.service.save_json(news_data, news_title, "gorkhapatra")

   
def main():
    scraper_service = ScraperService()
    scraper = GorkhaPatraScraper(scraper_service)
    scraper.start()

if __name__ == "__main__":
    main()