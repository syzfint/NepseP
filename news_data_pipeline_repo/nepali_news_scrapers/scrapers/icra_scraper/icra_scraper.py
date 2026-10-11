import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pdfplumber
from io import BytesIO
import time
import random
import re
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError
from ...services.minio_service.minio_service import upload_json_to_minio

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
]

class IcraScraper:
    def __init__(self, scraper_service: ScraperService):
        self.service = scraper_service
        self.base_url = "https://www.icranepal.com/releases/"
        self.processed_urls = set()  
        self.delay = 2  

    def make_request_url(self, url):
        return self.base_url.strip().rstrip("/") + "/" + url.strip().lstrip("/")
    
    def get_random_user_agent(self):
        return random.choice(USER_AGENTS)

    def start(self):
        self.get_page_listing()

    def get_page_listing(self):
        page = 1
        while page < 2:  #scrape 1 page only
            release_url = f"page/{page}/"
            page_url = self.make_request_url(release_url)
            pdf_links = self.extract_pdf_links(page_url)
            if not pdf_links:
                break
            for pdf_link in pdf_links:
                self.process_pdf_link(pdf_link)
                time.sleep(self.delay)
            page += 1
            time.sleep(self.delay)

    def extract_pdf_links(self, page_url):
        """Extract PDF links from a page."""
        headers = {"User-Agent": self.get_random_user_agent()}
        try:
            page_content = self.service.make_get_request(page_url, headers=headers)
            if not page_content:
                return []
            soup = BeautifulSoup(page_content, "html.parser")
            pdf_links_container = soup.find("ul", class_="list pdf-bullet all-section")
            if not pdf_links_container:
                return []
            return [
                {"title": anchor.text.strip(), "url": anchor["href"].strip()}
                for li in pdf_links_container.find_all("li")
                if (anchor := li.find("a", class_="name")) and anchor.get("href")
            ]
        except Exception as e:
            self.service.log.error(f"Error fetching page content: {e}")
            return []
    
    def process_pdf_link(self, pdf_link):
        """Process a single PDF link."""
        pdf_url = pdf_link["url"]
        pdf_title = pdf_link["title"]

        if pdf_url in self.processed_urls:
            self.service.log.info(f"Skipping {pdf_url}, already processed.")
            return
        self.processed_urls.add(pdf_url)

        if self.service.db_service.check_if_event_exists(pdf_url):
            self.service.log.info(f"Skipping {pdf_url}, already exists in the events table.")
            return

        try:
            self.service.log.info(f"Processing PDF: {pdf_title}")
            pdf_text = self.get_pdf_details(pdf_url)
            if not pdf_text:
                self.service.log.error(f"Failed to extract text from PDF: {pdf_url}")
                return

            date = self.extract_date_from_text(pdf_text)
            if not date:
                self.service.log.warning("No date found in the text.")

            event_id = self.service.db_service.add_event(
                title=pdf_title, url=pdf_url, published_date=date, content=pdf_text
            )
            if event_id:
                json_data = {
                    "event_id": event_id,
                    "title": pdf_title,
                    "url": pdf_url,
                    "content": pdf_text,
                    "published_date": date,
                }
                upload_json_to_minio(f"icra_{event_id}.json", json_data)
                self.service.log.info(f"Saved event with ID: {event_id}")
            else:
                self.service.log.error("Failed to save event.")
        except ScraperError as e:
            self.service.log.error(f"Error processing {pdf_url}: {e}")


    def get_pdf_details(self, pdf_url, max_retries=3):
        """Fetches PDF and extracts text with retry logic."""
        self.service.log.info(f"Fetching PDF: {pdf_url}")

        headers = {"User-Agent": self.get_random_user_agent()}
        retries = 0
        while retries < max_retries:
            try:
                response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
                if response.status_code != 200:
                    self.service.log.warning(f"Failed to fetch PDF (Status {response.status_code}), retrying...")
                    retries += 1
                    time.sleep(5)  # Add a fixed delay (e.g., 5 seconds)
                    continue
                
                # Stream the PDF content in chunks
                pdf_bytes = BytesIO()
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        pdf_bytes.write(chunk)
                pdf_bytes.seek(0)  # Reset the stream position

                text = ""
                with pdfplumber.open(pdf_bytes) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"

                self.service.log.info("PDF extraction complete.")
                return text.strip() if text else "No text extracted."

            except requests.exceptions.RequestException as e:
                self.service.log.error(f"Request error: {e}, retrying...")
                retries += 1
                time.sleep(5)  # Add a fixed delay

        self.service.log.error("Failed to retrieve PDF after retries.")
        return None  # Return None instead of crashing

    def extract_date_from_text(self, text):

        #regex pattern for the date
        date_pattern = r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b"
        
        match = re.search(date_pattern, text)
        
        # Return the matched date if found, oth`erwise return None
        return match.group(0) if match else None

if __name__ == "__main__":
    scraper_service = ScraperService()
    icra_scraper = IcraScraper(scraper_service)
    
    # Start scraping
    icra_scraper.start()

