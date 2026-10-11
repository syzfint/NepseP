import time
from typing import Dict
from nepse_scraper import NepseScraper
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService

STATUS_MAPPING = {
    "A": "Active",
    "S": "Suspended",
    "D": "Delisted",
}


class NepalStockScraper:
    def __init__(self, service: ScraperService):
        self.service = service

        self.scraper = NepseScraper(verify_ssl=False)
        self.scraper.register_endpoint(
            name="security_api",
            path="/api/nots/company/list",
            method="GET",
        )

    def start(self, payload: Dict=None):
        payload = payload or {}
        try:
            self.service.log.info("Fetching company data from NEPSE API...")
            company_data = self.scraper.call_endpoint(name="security_api")

            if not company_data:
                self.service.log.error("No company data received from NEPSE API.")
                return

            total_companies = len(company_data)
            self.service.log.info(f"Found {total_companies} companies. Processing...")

            for idx, company in enumerate(company_data, start=1):
                symbol = company.get("symbol")
                sector_name = company.get("sectorName")

                if self.service.db_service.check_nepse_company_exists(symbol):
                    self.service.log.warning(f"[{idx}/{total_companies}] Skipping existing company: {symbol}")
                    continue

                if sector_name and not self.service.db_service.check_nepse_sector_exists(sector_name):
                    self.service.db_service.insert_nepse_sector(sector_name)
                    self.service.log.info(f"[{idx}/{total_companies}] Inserted new sector: {sector_name}")

                db_data = {
                    "id": company.get("id"),
                    "companyName": company.get("companyName"),
                    "symbol": symbol,
                    "securityName": company.get("securityName"),
                    "status": STATUS_MAPPING.get(company.get("status"), "Unknown"),
                    "companyEmail": company.get("companyEmail"),
                    "website": company.get("website"),
                    "sectorName": sector_name,
                    "regulatoryBody": company.get("regulatoryBody"),
                    "instrumentType": company.get("instrumentType"),
                }

                try:
                    self.service.db_service.upsert_nepse_company(db_data)
                    self.service.log.info(f"[{idx}/{total_companies}] Upserted company: {symbol}")
                except Exception as e:
                    self.service.log.error(f"[{idx}/{total_companies}] Failed to upsert company {symbol}: {e}")


            self.service.log.info("Finished processing all companies.")

        except Exception as e:
            self.service.log.error(f"Scraper failed: {e}")

if __name__ == "__main__":
    scraper_service = ScraperService()
    scraper = NepalStockScraper(scraper_service)

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            scraper.start({})
            print("Scraper finished successfully.")
            break  # Exit loop if successful
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                wait_time = attempt * 3
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Scraper failed after maximum retries.")