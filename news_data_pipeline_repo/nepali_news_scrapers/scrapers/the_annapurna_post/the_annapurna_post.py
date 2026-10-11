import os
import requests
from bs4 import BeautifulSoup
import json
import time 
from datetime import datetime, timedelta
import re
import pytz
from nepali.date_converter import converter
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError

class TheAnnapurnaPostScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_url = "https://annapurnapost.com"
        self.service = scraper_service
        self.unique_links = set()
        self.threshold_days = 1
        self.tz = pytz.timezone('Asia/Kathmandu')  # Initialize timezone
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/133.0.0.0 Safari/537.36",
        }

    def make_request_url(self, url):
        return self.base_url.rstrip("/") + "/" + url.lstrip("/")

    def start(self):
        try:
            self.get_page_category()
        except ScraperError as e:
            self.service.log.error(f"Scraper failed to start: {e}")

    def get_page_category(self):
        categories = ['latest-news']
        for category in categories:
            self.scrape_category(category)

    def scrape_category(self, category):
        try:
            self.service.log.info(f"Scraping Category: {category}")
            for i in range(self.threshold_days):
                target_date = datetime.now(self.tz) - timedelta(days=i)  # Offset-aware
                date_str = target_date.strftime("%Y-%m-%d")
                page_url = self.make_request_url(f"category/{category}")
                self.get_page_listings(page_url)
        except Exception as e:
            self.service.log.error(f"Request failed for category {category}: {e}")

    def get_page_listings(self, page_url):
        page_num = 1
        while page_num <= 2:
            current_page_url = f"{page_url}/?page={page_num}"
            self.service.log.info(f"Scraping page: {current_page_url}")
            page_content = self.service.make_get_request(current_page_url, self.headers)
            if not page_content:
                break

            soup = BeautifulSoup(page_content, "html.parser")
            self.process_page_links(soup)
            page_num += 1

    def process_page_links(self, soup):
        # Process first story link
        first_story_link = soup.find('h3', class_='card__title').find('a')['href']
        full_story_link = self.make_request_url(first_story_link)  
        if full_story_link not in self.unique_links:
            self.unique_links.add(full_story_link)
            self.get_page_details(full_story_link)

        # Process grid cards
        grid_cards = soup.find_all("div", class_="grid__card")
        new_links_found = False
        for card in grid_cards:
            anchors = card.find_all("a")
            for a in anchors:
                href = a.get("href")
                if href and "category" not in href:
                    full_link = self.make_request_url(href)
                    if full_link not in self.unique_links:
                        self.unique_links.add(full_link)
                        self.get_page_details(full_link)
                        new_links_found = True

        if not new_links_found:
            return

    def get_page_details(self, url,current_time=None):
        page_content = self.service.make_get_request(url)
        if not page_content:
            return

        soup = BeautifulSoup(page_content, "html.parser")
        title = self.get_title(soup)
        date_part, time_part = self.get_date_time(soup, url)
        if not date_part:
            return False

        article_datetime = self.get_article_datetime(date_part, time_part, url)
        if not article_datetime:
            return False

        if self.is_article_older_than_threshold(article_datetime, url,current_time):
            return False

        author = self.get_author(soup)
        content = self.get_content(soup)
        category = self.get_category(soup)

        news_data = {
            "url": url,
            "category": category,
            "title": title,
            "time_date": article_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "published_date": article_datetime.strftime("%Y-%m-%d"),  
            "published_time": article_datetime.strftime("%H:%M:%S"), 
            "author": author,
            "content": content
        }

        self.service.save_json(news_data, title, "annapurna_post")

    def get_title(self, soup):
        title_container = soup.find('h1', class_='news__title')
        return title_container.text.strip() if title_container else ""

    def get_date_time(self, soup, url):
        time_date_container = soup.find('p', class_='date')
        time_date = time_date_container.text.strip() if time_date_container else ""
        date_part, time_part = "", ""
        if time_date:
            try:
                date_part, time_part = time_date.rsplit(' ', 1)
            except ValueError:
                self.service.log.warning(f"Unable to split date and time for URL: {url}")
        return date_part, time_part

    def get_article_datetime(self, date_part, time_part, url):
        try:
            nepali_month_mapping = {
                'वैशाख': 1, 'बैशाख': 1, 'जेठ': 2, 'असार': 3, 'साउन': 4, 'भदौ': 5, 'असोज': 6,
                'कात्तिक': 7, 'मंसिर': 8, 'पुष': 9, 'माघ': 10, 'फागुन': 11, 'चैत': 12
            }

            date_components = date_part.split()
            nepali_month_str = date_components[0]
            nepali_date_str = date_components[1].strip(',')
            nepali_year_str = date_components[2]

            nepali_month = nepali_month_mapping.get(nepali_month_str)
            if nepali_month is None:
                raise ValueError(f"Invalid Nepali month: {nepali_month_str}")

            nepali_date_str_eng = self.service.convert_nepali_to_english(nepali_date_str)
            nepali_year_str_eng = self.service.convert_nepali_to_english(nepali_year_str)
            nepali_time_str_eng = self.service.convert_nepali_to_english(time_part)

            nepali_date = int(nepali_date_str_eng)
            nepali_year = int(nepali_year_str_eng)
            nepali_hour, nepali_minute, nepali_second = map(int, nepali_time_str_eng.split(':'))

            en_year, en_month, en_date = converter.nepali_to_english(nepali_year, nepali_month, nepali_date)

            article_datetime = datetime(en_year, en_month, en_date, nepali_hour, nepali_minute, nepali_second)
            article_datetime = self.tz.localize(article_datetime)  # Make offset-aware
            return article_datetime
        except (ValueError, IndexError, AttributeError) as e:
            self.service.log.error(f"Error parsing date or time for URL {url}: {e}")
            return None

    def is_article_older_than_threshold(self, article_datetime, url, current_time=None):
        if current_time is None:
            current_time = datetime.now(self.tz)  # Offset-aware
        if current_time - article_datetime >= timedelta(hours=1):
            self.service.log.info(f"Skipping {url} as it is older than the threshold time/date value")
            return True
        return False

    def get_author(self, soup):
        author_container = soup.find("p", {"class": "author__name"})
        return author_container.text.strip() if author_container else ""

    def get_content(self, soup):
        content_container = soup.find("div", {"class": "news__details"})
        return content_container.text.strip() if content_container else ""

    def get_category(self, soup):
        category_div = soup.find('div', class_='card__category')
        if category_div:
            category_link = category_div.find('a')
            if category_link and 'href' in category_link.attrs:
                match = re.search(r'/category/([^/]+)/', category_link['href'])
                if match:
                    return match.group(1)
        return None    

if __name__ == "__main__":
    scraper_service = ScraperService()
    scraper = TheAnnapurnaPostScraper(scraper_service)
    scraper.start()