import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pytz
from nepali.date_converter import converter
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError

class SetoPatiScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_url = "https://www.setopati.com"
        self.unique_links = set()
        self.service = scraper_service
        self.tz = pytz.timezone('Asia/Kathmandu')
        self.nepali_months = {
            "बैशाख": 1, "वैशाख": 1, "जेष्ठ": 2, "अषाढ": 3, "श्रावण": 4,
            "भदौ": 5, "असोज": 6, "कार्तिक": 7, "मंसिर": 8,
            "पुस": 9, "माघ": 10, "फागुन": 11, "चैत्र": 12, "चैत": 12
        }

    def make_request_url(self, url):
        return self.base_url.strip().rstrip("/") + "/" + url.strip().lstrip("/")

    def start(self):
        url = self.make_request_url("/search?&page=")
        self.get_page_listings(url)

    def get_page_listings(self, page_url):
        page_num = 1
        while page_num <= 2:
            current_page_url = f"{page_url}{page_num}"
            try:
                page_content = self.service.make_get_request(current_page_url)
                if not page_content:
                    break

                soup = BeautifulSoup(page_content, "html.parser")
                new_links_found = False

                # Get featured article links
                banner_article_links = soup.find_all("div", class_="big-feature col-md-12")
                if banner_article_links:
                    anchors = []
                    for item in banner_article_links:
                        anchors.extend(item.find_all("a"))
                    href_links = [a['href'] for a in anchors if 'href' in a.attrs]
                    for link in href_links:
                        if self.is_valid_article_link(link):
                            self.unique_links.add(link)
                            new_links_found = True

                # Get other news links from the category page
                div_tags = soup.find_all('div', class_='items')
                href_links = [div.find('a')['href'] for div in div_tags if div.find('a') and 'href' in div.find('a').attrs]
                for link in href_links:
                    if self.is_valid_article_link(link):
                        self.unique_links.add(link)
                        new_links_found = True

                # Process each new link
                if new_links_found:
                    for link in self.unique_links:
                        self.get_page_details(link)

                page_num += 1

            except ScraperError as e:
                self.service.log.error(f"ScraperError: {e.message}")
            except Exception as e:
                self.service.log.error(f"Unexpected error while processing page {page_num}: {e}")

    def is_valid_article_link(self, link):
        # Exclude links that contain 'photo-detail' or 'author'
        if "photo-detail" in link or "author" in link:
            return False
        # Ensure the link ends with digits
        return bool(re.search(r'\d+$', link))

    def extract_title(self, soup):
        """Extract the article title from the BeautifulSoup object."""
        title_container = soup.find("h1", class_="news-big-title")
        return title_container.get_text(strip=True) if title_container else "N/A"

    def extract_author(self, soup):
        """Extract the article author from the BeautifulSoup object."""
        author = "N/A"
        media_body = soup.find("div", class_="media-body")
        if media_body:
            author_container = media_body.find("h2", class_="main-title")
            if author_container:
                author = author_container.get_text(strip=True)
        return author

    def extract_content(self, soup):
        """Extract the article content from the BeautifulSoup object."""
        content_text = []
        content_body = soup.find("div", class_="editor-box")
        if content_body:
            content_container = content_body.find_all("p")
            for paragraph in content_container:
                content_text.append(paragraph.get_text(strip=True))
        return " ".join(content_text)

    def extract_category(self, url):
        """Extract the category from the article URL."""
        match = re.search(r"https?://www\.setopati\.com/([^/]+)/", url)
        return match.group(1) if match else None

    def extract_published_date(self, soup):
        """Extract the published date and time from the BeautifulSoup object."""
        date_time_container = soup.find("div", class_="published-date col-md-6")
        if not date_time_container:
            self.service.log.error("Date and time container not found.")
            return None, None

        date_time_text = date_time_container.text.strip()
        if not date_time_text:
            self.service.log.error("Date and time text is empty.")
            return None, None

        cleaned_text = date_time_text.replace('\xa0', ' ')
        date_match = re.search(r',\s*([^,]+ \d{1,2}, \d{4})', cleaned_text)
        time_match = re.search(r'(\d{1,2}:\d{2})', cleaned_text)
        if not date_match or not time_match:
            self.service.log.error("Could not extract date or time from the text.")
            return None, None

        date_t = date_match.group(1)
        time_t = self.service.convert_nepali_to_english(time_match.group(1))

        if len(time_t.split(':')) == 2:  # Check if it’s only HH:MM
            time_t = f"{time_t}:00"

        try:
            np_month_str, np_day_str, np_year_str = date_t.split()
        except Exception as e:
            self.service.log.error(f"Error splitting date text '{date_t}': {e}")
            return None, None

        np_day_str = np_day_str.strip(',')

        np_month = self.nepali_months.get(np_month_str)
        if np_month is None:
            self.service.log.error(f"Unrecognized Nepali month: {np_month_str}")
            return None, None

        en_year, en_month, en_day = converter.nepali_to_english(
            int(self.service.convert_nepali_to_english(np_year_str)),
            np_month,
            int(self.service.convert_nepali_to_english(np_day_str))
        )

        return f"{en_year}-{en_month:02d}-{en_day:02d}", time_t

    def get_page_details(self, url):
        try:
            page_content = self.service.make_get_request(url)
            if not page_content:
                return

            self.service.log.info(f"\nArticle url {url}")
            soup = BeautifulSoup(page_content, "html.parser")

            # Extract all fields using modular methods
            news_title = self.extract_title(soup)
            author = self.extract_author(soup)
            full_content = self.extract_content(soup)
            published_date, published_time = self.extract_published_date(soup)
            category = self.extract_category(url)

            if published_date is None or published_time is None:
                return  # Skip processing if date extraction fails

            try:
                article_datetime = datetime.strptime(f"{published_date} {published_time}", "%Y-%m-%d %H:%M:%S")
                article_datetime = self.tz.localize(article_datetime)  # Make offset-aware
                current_datetime = datetime.now(self.tz)  # Offset-aware
                self.service.log.debug(f"Comparing {current_datetime} - {article_datetime}")
                if current_datetime - article_datetime > timedelta(hours=1):
                    self.service.log.info(f"Skipping {url} as it is older than 1 hour")
                    return
            except ValueError as e:
                self.service.log.error(f"Date parsing failed for {published_date} {published_time}: {e}")
                return

            news_data = {
                "url": url,
                "category": category,
                "title": news_title,
                "published_date": published_date,
                "published_time": published_time,
                "author": author,
                "content": full_content,
            }
            self.service.log.debug(f"Final news_data: {news_data}")

            self.service.save_json(news_data, news_title, "setopati")

        except ScraperError as e:
            self.service.log.error(f"ScraperError: {e.message}")
        except Exception as e:
            self.service.log.error(f"Unexpected error in get_page_details: {e}")

def main():
    scraper_service = ScraperService()
    scraper = SetoPatiScraper(scraper_service)
    scraper.start()

if __name__ == "__main__":
    main()