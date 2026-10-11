import re
import time
import logging
import requests
from requests.exceptions import ReadTimeout, ConnectionError, HTTPError, RequestException
from abc import ABC, abstractmethod
from nepali_news_scrapers.services.minio_service.minio_service import upload_json_to_minio
from nepali_news_scrapers.services.db_service import DbService
from enum import Enum
from datetime import datetime
import pytz


class ScraperResult(Enum):
    success = 0
    invalid = 2


class Scraper(ABC):
    """Interface to be implemented by every scraper."""

    @abstractmethod
    def start(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_details(self, url: str, *args, **kwargs):
        pass


class ScraperError(Exception):
    """Custom exception for scraper errors."""
    def __init__(self, message, *args):
        self.message = message
        super().__init__(f"{message}")


class ScraperService:
    """Scraper Service class to have all the common functionalities needed for scraping tasks"""

    def __init__(self):
        self.db_service=DbService()
        self.log = logging.getLogger(__name__)

    def make_get_request(self, url, headers=None, retries=3, backoff=2):
        return self._make_request("GET", url, headers=headers, retries=retries, backoff=backoff)

    def make_post_request(self, url, data=None, headers=None, retries=3, backoff=2):
        return self._make_request("POST", url, data=data, headers=headers, retries=retries, backoff=backoff)

    def _make_request(self, method, url, data=None, headers=None, retries=3, backoff=2):
       
        attempt = 0
        while attempt < retries:
            try:
                if method == "GET":
                    response = requests.get(url, headers=headers, timeout=10)
                    response.encoding = 'utf-8'
                elif method == "POST":
                    response = requests.post(url, data=data, headers=headers, timeout=10)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                if response.status_code == 403:
                    self.log.error(f"Forbidden (403) for URL: {url}")
                    raise ScraperError(f"Access forbidden for URL: {url}")
                elif response.status_code == 503:
                    self.log.warning(f"Service Unavailable (503) for URL: {url}. Retrying...")
                else:
                    response.raise_for_status()

                return response.json() if method == "POST" else response.text

            except (ReadTimeout, ConnectionError) as e:
                self.log.warning(f"Network error for URL: {url}: {e}")
            except HTTPError as e:
                self.log.error(f"HTTP error for URL: {url}: {e}")
            except RequestException as e:
                self.log.error(f"Request error for URL: {url}: {e}")

            attempt += 1
            sleep_duration = backoff * attempt
            self.log.info(f"Retrying in {sleep_duration} seconds...")
            time.sleep(sleep_duration)  # Exponential backoff

        raise ScraperError(f"Failed to retrieve content from {url} after {retries} attempts.")

    def save_json(self, data, title, filename_prefix):
        ktm_tz = pytz.timezone('Asia/Kathmandu')
        timestamp = datetime.now(ktm_tz).strftime("%Y%m%d-%H%M%S")
        title_slug = re.sub(r"\W+", "_", title)[:10]
        filename = f"{timestamp}_{filename_prefix}_{title_slug}.json"

        try:
            uploaded = upload_json_to_minio(filename, data)
            if uploaded:
                self.log.info(f" Uploaded JSON to MinIO: {filename}")
            else:
                self.log.info(f" Skipped uploading JSON to MinIO: {filename} (embeddings already exists.")
        except Exception as e:
            self.log.error(f" Error uploading to MinIO: {e}")

            
    @staticmethod
    def convert_nepali_to_english(nepali_number):
        """Convert Nepali digits to English digits."""
        nepali_digits = "०१२३४५६७८९"
        english_digits = "0123456789"
        translation_table = str.maketrans(nepali_digits, english_digits)
        return nepali_number.translate(translation_table)


class ScraperRunner:
    """Scraper Runner to get instances of scrapers."""

    @classmethod
    def get_scraper_instance(cls, scraper_name):
        from nepali_news_scrapers.scrapers import scrapers

        scraper_class = scrapers.get(scraper_name)

        if scraper_class:
            scraper_service = ScraperService()
            return scraper_class(scraper_service)
        else:
            raise ValueError(f"Invalid scraper name: '{scraper_name}'")
