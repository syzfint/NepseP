import os
import re
import requests
import time
import json
import logging
from bs4 import BeautifulSoup
import pytz
from datetime import datetime, timedelta
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError

class KathmanduPostScraper:
    def __init__(self, scraper_service: ScraperService):
        self.base_url = "https://kathmandupost.com"
        self.service = scraper_service
        self.unique_links = set()
        self.tz = pytz.timezone('Asia/Kathmandu')

    def make_request_url(self, url):
        return self.base_url.strip().rstrip("/") + "/" + url.strip().lstrip("/")

    def start(self):
        self.service.log.info("Starting KathmanduPostScraper...")
        try:
            self.get_page_listings(self.make_request_url("/latest"))
        except ScraperError as e:
            self.service.log.error(f"Scraper failed to start: {e}")
        except Exception as e:
            self.service.log.error(f"Unexpected error in start: {e}")
        self.service.log.info("Scraper finished.")

    def get_page_listings(self, page_url):
        self.service.log.info(f"Fetching page listings from {page_url}")
        page_content = self.service.make_get_request(page_url)
        if not page_content:
            self.service.log.error("Failed to retrieve page listings.")
            raise ScraperError("Failed to retrieve page listings.")

        soup = self._parse_html(page_content, page_url)
        if not soup:
            return

        links = self.extract_links(soup)
        if links:
            self.service.log.info("New links found. Fetching page details...")
            for link in links.copy():
                if not link or not isinstance(link, str):
                    self.service.log.warning(f"Skipping invalid link: {link}")
                    continue
                article_url = self.make_request_url(link)
                self.service.log.info(f"Processing article: {article_url}")
                try:
                    self.get_page_details(article_url)
                except Exception as e:
                    self.service.log.error(f"Failed to process {article_url}: {e}")
        else:
            self.service.log.info("No new links found.")

    def extract_links(self, soup):
        links = set()
        # Extract from trending lists
        trending_lists = soup.find_all("ul", class_="trending-topics-list")
        for trending_list in trending_lists:
            for a_tag in trending_list.find_all("a"):
                href = a_tag.get("href")
                if href:
                    links.add(href)
                    self.unique_links.add(href)
        # Extract from article listings
        for a_tag in soup.select("div.block--morenews article.article-image a"):
            href = a_tag.get("href")
            if href:
                links.add(href)
                self.unique_links.add(href)
        return links

    def get_page_details(self, url):
        self.service.log.info(f"Fetching details for {url}")
        page_content = self.service.make_get_request(url)
        if not page_content:
            raise ScraperError(f"Failed to retrieve article details for {url}.")

        soup = self._parse_html(page_content, url)
        if not soup:
            return False

        dt_obj = self.extract_date_time(soup)
        if not self.is_recent(dt_obj):
            self.service.log.info(f"Skipping {url} as it is older than the threshold")
            return False

        category = self.extract_category(soup)
        title = self.extract_title(soup)
        author = self.extract_author(soup)
        content = self.extract_content(soup)

        news_data = {
            "url": url,
            "title": title if title else "Untitled",
            "category": category if category else "Unknown",
            "author": author if author else "Unknown",
            "published_time": dt_obj.strftime("%H:%M:%S") if dt_obj else "00:00:00",
            "published_date": dt_obj.strftime("%Y-%m-%d") if dt_obj else "n/a",
            "content": content if content else "No content available"
        }

        self.service.save_json(news_data, title or "Untitled", "the_kathmandu_post")
        return True

    def _parse_html(self, content, url):
        try:
            return BeautifulSoup(content, "html.parser")
        except Exception as e:
            self.service.log.error(f"Failed to parse HTML content for {url}: {e}")
            return None

    def extract_category(self, soup):
        category_container = soup.find("h4", {"class": "title--line__red"})
        if category_container:
            anchor = category_container.find("a")
            if anchor:
                return anchor.text.strip()
        return None

    def extract_title(self, soup):
        title_tag = soup.find("title")
        return title_tag.text.strip() if title_tag else None

    def extract_date_time(self, soup):
        date_time_containers = soup.find_all("div", {"class": "updated-time"})
        if not date_time_containers:
            return None

        # Prioritize updated time if available
        if len(date_time_containers) > 1:
            updated_text = date_time_containers[1].text.strip()
            match = re.search(r'Updated at : (\w+ \d{1,2}, \d{4}(?: \d{2}:\d{2})?)', updated_text)
            if match:
                dt_str = match.group(1)
                try:
                    if len(dt_str.split()) > 3:
                        dt_obj = datetime.strptime(dt_str, "%B %d, %Y %H:%M")
                    else:
                        dt_obj = datetime.strptime(dt_str, "%B %d, %Y")
                    return self.tz.localize(dt_obj)
                except ValueError:
                    pass

        # Fallback to published time
        published_text = date_time_containers[0].text.strip()
        match = re.search(r'Published at : (\w+ \d{1,2}, \d{4})', published_text)
        if match:
            dt_str = match.group(1)
            try:
                dt_obj = datetime.strptime(dt_str, "%B %d, %Y")
                return self.tz.localize(dt_obj)
            except ValueError:
                pass
        return None

    def is_recent(self, dt_obj):
        if not dt_obj:
            return False
        now = datetime.now(self.tz)
        return (now - dt_obj) <= timedelta(hours=1)

    def extract_author(self, soup):
        author_container = soup.find('h5', class_='text-capitalize')
        if author_container:
            self.service.log.debug(f"Found h5 tag: {author_container}")
            author_link = author_container.find('a', href=re.compile(r'.*/author.*'))
            if author_link:
                self.service.log.debug(f"Found author link: {author_link}")
                return author_link.text.strip()
            else:
                self.service.log.debug("No <a> tag with /author in href found in h5")
        else:
            self.service.log.debug("No h5 tag with class 'text-capitalize' found")
        return None

    def extract_content(self, soup):
        content_container = soup.find("section", {"class": "story-section"})
        return content_container.text.strip() if content_container else None

def main():
    scraper_service = ScraperService()
    scraper_service.log.setLevel(logging.DEBUG)
    scraper = KathmanduPostScraper(scraper_service)
    scraper.start()

if __name__ == "__main__":
    main()