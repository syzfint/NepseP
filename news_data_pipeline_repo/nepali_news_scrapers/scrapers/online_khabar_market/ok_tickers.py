import time
import json
from datetime import datetime
import argparse
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError


class OnlineKhabarMarketScraper:
    def __init__(self, scraper_service: ScraperService, company_symbol: str):
        self.api_base_url = "https://www.onlinekhabar.com/smtm/ticker-page"
        self.service = scraper_service
        self.company_symbol = company_symbol.upper()
        self.api_urls = {
            "quick_view": f"{self.api_base_url}/ticker-quick-view/{self.company_symbol}",
            "technical_indicators": f"{self.api_base_url}/ticker-technical-indicator/{self.company_symbol}",
            "market_range": f"{self.api_base_url}/market-range/{self.company_symbol}",
            "ticker_info": f"{self.api_base_url}/ticker-info/{self.company_symbol}",
            "ticker_stats": f"{self.api_base_url}/ticker-stats/{self.company_symbol}",
            "chart": f"{self.api_base_url}/chart/{self.company_symbol}/1d",
            "market_status":"https://www.onlinekhabar.com/smtm/home/market-status"
        }

    def start(self):
        self.service.log.info(f"Starting API scraper for OnlineKhabar Ticker: {self.company_symbol}")
        try:
            self.get_data_from_apis()
        except ScraperError as e:
            self.service.log.error(f"API Scraper failed for {self.company_symbol}: {e}")
        except Exception as e:
            self.service.log.error(f"Unexpected error during scraping {self.company_symbol}: {e}", exc_info=True)

    def _fetch_and_parse_api(self, api_name, url):
        self.service.log.info(f"Fetching {api_name} data from: {url}")
        try:
            response_text = self.service.make_get_request(url)
            if not response_text:
                self.service.log.warning(f"Empty response for {api_name} at {url}")
                return None
            data = json.loads(response_text)
            if isinstance(data, dict) and "response" in data:
                return data["response"]
            self.service.log.warning(f"Unexpected JSON format for {api_name}. Data: {data}")
            return None
        except json.JSONDecodeError as e:
            self.service.log.error(f"JSON decode error for {api_name} at {url}: {e}. Response: {response_text[:200]}...")
            return None
        except ScraperError:
            return None
        except Exception as e:
            self.service.log.error(f"Exception fetching {api_name} at {url}: {e}", exc_info=True)
            return None

    def get_data_from_apis(self):
        quick_view_data = self._fetch_and_parse_api("Quick View", self.api_urls["quick_view"])
        technical_indicators_data = self._fetch_and_parse_api("Technical Indicators", self.api_urls["technical_indicators"])
        market_range_data = self._fetch_and_parse_api("Market Range", self.api_urls["market_range"])
        ticker_info_data = self._fetch_and_parse_api("Ticker Info", self.api_urls["ticker_info"])
        ticker_stats_data = self._fetch_and_parse_api("Ticker Stats", self.api_urls["ticker_stats"])
        chart_data = self._fetch_and_parse_api("Chart", self.api_urls["chart"])
        market_status= self._fetch_and_parse_api("Market Status",self.api_urls["market_status"])

        print("\n" + "=" * 50)
        print(f"API Data for {self.company_symbol}")
        print(f"Scraped Timestamp (UTC): {datetime.utcnow().isoformat()}Z")
        print("=" * 50)

        def print_data(title, data):
            print(f"\n--- {title} ---")
            if data:
                if isinstance(data, list):
                    for item in data:
                        print(json.dumps(item, indent=2))
                elif isinstance(data, dict):
                    for key, value in data.items():
                        print(f"{key}: {value if value is not None else 'N/A'}")
                else:
                    print(data)
            else:
                print("Data not available or failed to fetch.")

        print_data("Quick View (API)", quick_view_data)
        print_data("Technical Indicators (API)", technical_indicators_data)
        print_data("Market Range (API)", market_range_data)
        print_data("Ticker Info (API)", ticker_info_data)
        print_data("Ticker Stats (API)", ticker_stats_data)
        print_data("Market Status (API)", market_status)

        print("\n--- Chart (API) ---")
        if chart_data:
            print(f"Ticker: {chart_data.get('ticker', 'N/A')}")
            print(f"Percentage Change: {chart_data.get('percentageChange', 'N/A')}")
            print("Chart Data (last 10 entries):")
            for point in chart_data.get("chartData", []):  # Show only latest 10 points
                print(f"  - {point['timestamp']} => {point['value']}")
        else:
            print("Chart data not available.")

        print("\n" + "=" * 50 + "\n")

        if any([quick_view_data, technical_indicators_data, market_range_data, ticker_info_data, ticker_stats_data, chart_data]):
            self.service.log.info(f"Successfully fetched and printed all available data for {self.company_symbol}")
        else:
            self.service.log.warning(f"No valid data found for {self.company_symbol}")


# --- How to use it ---
if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Scrape OnlineKhabar market data for given company symbols using APIs.")
    parser.add_argument(
        'symbols',
        metavar='SYMBOL',
        type=str,
        nargs='+', # Accepts one or more symbols
        help='One or more NEPSE company ticker symbols (e.g., MKJC BPCL NABIL)'
    )

    # Parse arguments
    args = parser.parse_args()
    company_symbols_to_scrape = args.symbols # Get the list of symbols from arguments

    try:
        # Instantiate the service
        scraper_service = ScraperService()

        print(f"--- Starting scraper for symbols: {', '.join(company_symbols_to_scrape)} ---")

        # Use the symbols obtained from command line
        for symbol in company_symbols_to_scrape:
            ok_scraper = OnlineKhabarMarketScraper(scraper_service, symbol)
            ok_scraper.start()
            # Keep the delay between scraping different symbols
            print(f"--- Waiting 1 second before next symbol ---")
            time.sleep(1)

        print(f"--- Finished scraping all symbols ---")

   
    except Exception as e:
        # Catch broad exceptions during setup or looping
        print(f"An error occurred in the main execution block: {e}")
        # Use basic logging if service logger might not be initialized
        import logging
        logging.exception("Error in main execution block")