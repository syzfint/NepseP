import requests
from bs4 import BeautifulSoup
import pdfplumber
from io import BytesIO
import time
from nepali_news_scrapers.services.scraper_service import ScraperService
from nepali_news_scrapers.services.minio_service.minio_service import upload_json_to_minio

class NRBScraper:
    def __init__(self, service: ScraperService):
        self.service = service
        self.base_url = "https://www.nrb.org.np"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.processed_urls = set()  # Track processed URLs

    def make_request_url(self, url):
        return self.base_url.strip().rstrip("/") + "/" + url.strip().lstrip("/")

    def start(self):
        self.get_macroeconomic_situation()

    def get_macroeconomic_situation(self):
        try:
            response = self._fetch_page(self.base_url)
            if not response:
                return

            soup = BeautifulSoup(response, "html.parser")
            macro_block = self._find_macroeconomic_block(soup)
            if not macro_block:
                return

            self._process_macroeconomic_block(macro_block)

        except Exception as e:
            self.service.log.error(f"Error in getting macroeconomic situation: {str(e)}")

    def _fetch_page(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.service.log.error(f"Error fetching page {url}: {str(e)}")
            return None

    def _find_macroeconomic_block(self, soup):
        """find the macroeconomic situation block in the homepage"""
        macro_blocks = soup.find_all("div", class_="main-block-card")
        if not macro_blocks or len(macro_blocks) < 2:
            self.service.log.error("Failed to find macroeconomic situation block!")
            return None

        macro_block = macro_blocks[1]  # Target block
        title = macro_block.find("div", class_="card-title mb-2")
        if not title or "Current Macro-Economic and Financial Situation" not in title.text:
            self.service.log.error("Macroeconomic block title not found!")
            return None

        return macro_block

    def _process_macroeconomic_block(self, macro_block):
        """Process the macroeconomic block and extract reports"""
        report_list = macro_block.find("ul", class_="arrowed-list arrowed-list--border")
        if not report_list:
            self.service.log.error("Found macroeconomic block, but no report list inside!")
            return

        for item in report_list.find_all("li"):
            self._process_report_item(item)

    def _process_report_item(self, item):
        """Process a single report item"""
        try:
            link_tag = item.find("a")
            if not link_tag:
                return

            title = link_tag.text.strip()
            url = link_tag.get('href', '').strip()
            if not url:
                return

            if 'English' not in title:
                return

            full_url = url if url.startswith('http') else self.make_request_url(url)
            if full_url in self.processed_urls:
                return

            self._process_english_report(item, title, full_url)

        except Exception as e:
            self.service.log.error(f"Error processing report: {str(e)}")

    def _process_english_report(self, item, title, full_url):
        """Process an English report"""
        published_date = self._extract_published_date(item)
        
        if self.service.db_service.check_nrb_report_exists(full_url):
            self.service.log.info(f"Skipping {full_url}, already exists in nrb_macroeconomic_reports.")
            return

        pdf_url = full_url if full_url.lower().endswith('.pdf') else self.find_pdf_from_page(full_url)
        if not pdf_url:
            self.service.log.error("No PDF found for this report")
            return

        pdf_text = self.extract_pdf_text(pdf_url)
        if not pdf_text:
            self.service.log.error("Failed to extract PDF content")
            return

        self._store_report_data(title, full_url, pdf_url, published_date, pdf_text)
        self.processed_urls.add(full_url)

    def _extract_published_date(self, item):
        """Extract published date from report item"""
        published_date = item.find("span", class_="mr-3 text-muted")
        return published_date.text.strip() if published_date else None

    def _store_report_data(self, title, url, pdf_url, published_date, content):
        """Store report data in database and create event"""
        report_id = self.service.db_service.upsert_nrb_report(
            title=title,
            url=url,
            pdf_url=pdf_url,
            published_date=published_date,
            content=content
        )
        if not report_id:
            self.service.log.error("Failed to store NRB report")
            return

        event_id = self.service.db_service.add_event(
            title=title,
            url=url,
            published_date=published_date,
            content=content
        )
        if not event_id:
            self.service.log.error("Failed to create event for NRB report")
            return

        self._upload_to_minio(event_id, title, url, content, published_date)

    def _upload_to_minio(self, event_id, title, url, content, published_date):
       
        json_data = {
            "event_id": str(event_id),
            "title": title,
            "url": url,
            "content": content,
            "published_date": published_date
        }
        file_name = f"nrb_{event_id}.json"
        success = upload_json_to_minio(file_name, json_data)
        if success:
            self.service.log.info(f"Successfully processed embedding and summary for {file_name}")
        else:
            self.service.log.error(f"Failed to process embedding and summary for {file_name}")

    def find_pdf_from_page(self, page_url):
        """Visit the linked page and find the PDF URL"""
        try:
            head_response = requests.head(page_url, headers=self.headers, 
                                    allow_redirects=True, timeout=10)
            
            if head_response.url.lower().endswith('.pdf') or \
           'application/pdf' in head_response.headers.get('content-type', '').lower():
                return head_response.url
                
            if 'text/html' in head_response.headers.get('content-type', '').lower():
                response = requests.get(page_url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link.get('href', '')
                    if href.lower().endswith('.pdf'):
                        return href if href.startswith('http') else self.make_request_url(href)
            
            return None
        except Exception as e:
            self.service.log.error(f"Error fetching PDF from page {page_url}: {str(e)}")
            return None

    def extract_pdf_text(self, pdf_url, max_retries=3):
        """Download PDF and extract text with retry logic"""
        retries = 0
        while retries < max_retries:
            try:
                response = requests.get(pdf_url, stream=True, timeout=30, headers=self.headers)
                response.raise_for_status()
                
                pdf_bytes = BytesIO()
                for chunk in response.iter_content(chunk_size=8192):
                    pdf_bytes.write(chunk)
                pdf_bytes.seek(0)
                
                text = ""
                with pdfplumber.open(pdf_bytes) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                
                return text.strip() if text else None
                
            except Exception as e:
                retries += 1
                self.service.log.warning(f"Retry {retries}/{max_retries} failed: {str(e)}")
                if retries >= max_retries:
                    self.service.log.error(f"Failed to extract PDF text after {max_retries} attempts")
                    return None
                time.sleep(2 ** retries)
                
if __name__ == "__main__":
    scraper_service = ScraperService()
    nrb_scraper = NRBScraper(scraper_service)
    nrb_scraper.start()