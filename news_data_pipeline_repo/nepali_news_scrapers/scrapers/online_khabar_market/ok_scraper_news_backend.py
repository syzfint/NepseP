import asyncio
import logging
from datetime import datetime
import requests
from requests.exceptions import RequestException
from cachetools import TTLCache
from threading import Lock

# Initialize logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize the cache, TTL uses LRU and replaces least recently used entry to make space for new ones.
cache = TTLCache(maxsize=200, ttl=60)  # 1-minute expiration
cache_lock = Lock()
cache_hits = 0
cache_misses = 0

class ScraperService:
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124"
        })

    async def fetch_data(self, url):
        """Fetch data from the API and cache it for 1 minutes."""
        global cache_hits, cache_misses
        # Check cache
        with cache_lock:
            current_cache_size = len(cache)
            if url in cache:
                cache_hits += 1
                self.log.info(f"Cache HIT for URL: {url} (Hits: {cache_hits}, Misses: {cache_misses}, Cache Size: {current_cache_size})")
                return cache[url]

        self.log.info(f"Cache MISS for URL: {url} (Hits: {cache_hits}, Misses: {cache_misses}, Cache Size: {current_cache_size})")

        try:
            # Run the request in a thread to keep it async-friendly
            response = await asyncio.to_thread(self.session.get, url, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.log.debug(f"Fetched data from {url}: {data}")
            
            # Store in cache
            with cache_lock:
                cache[url] = data
                cache_misses += 1
                self.log.info(f"Stored new data in cache for {url} (Hits: {cache_hits}, Misses: {cache_misses}, Cache Size: {len(cache)})")
            
            return data
        except RequestException as e:
            self.log.error(f"Failed to fetch data from {url}: {e}")
            return None

class OnlineKhabarMarketScraper:
    def __init__(self, scraper_service):
        self.service = scraper_service
        self.data_cache = TTLCache(maxsize=50, ttl=60)
        self.base_url = "https://www.onlinekhabar.com/smtm/ticker-page"
        self.endpoints = {
            "price_chart": "chart/{symbol}/1d",
            "key_statistics": "ticker-stats",
            "quick_view": "ticker-quick-view",
            "technical_indicators": "ticker-technical-indicator",
            "ticker_info": "ticker-info",
            "market_range": "market-range",
            "market_status": "market-status"
        }
        self.log = logging.getLogger(__name__)

    
    
    async def get_section(self, section_name, symbol):
        url = self._build_url(section_name, symbol)
        self.log.debug(f"Fetching section '{section_name}' for symbol '{symbol}' from {url}")
        data = await self.service.fetch_data(url)
        
        response_data = data.get('response', {}) if data else {}
        
        # Special handling for market_status list response
        if section_name == "market_status" and isinstance(response_data, list):
            return response_data[0] if response_data else {}
        
        return response_data
    
    async def scrape_all(self, symbol):
        symbol_key = symbol.lower()
        with cache_lock:
            if symbol_key in self.data_cache:
                self.log.info(f"Using cached data for symbol '{symbol}'")
                return self.data_cache[symbol_key]

        self.log.info(f"Scraping all sections for symbol '{symbol}'")
        tasks = {
            section: self.get_section(section, symbol)
            for section in self.endpoints
        }
        try:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            processed_results = []
            for section, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    self.log.error(f"Failed to fetch section '{section}' for symbol '{symbol}': {str(result)}")
                    processed_results.append({})
                else:
                    processed_results.append(result)
        except Exception as e:
            self.log.error(f"Scrape failed for symbol '{symbol}': {str(e)}")
            processed_results = [{}] * len(tasks)

        scraped_data = {
            "symbol": symbol,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            **dict(zip(tasks.keys(), processed_results))
        }

        # Ensure ticker_info is a dict and add icon
        if not isinstance(scraped_data.get('ticker_info'), dict):
            scraped_data['ticker_info'] = {}
        scraped_data['ticker_info']['icon'] = f"https://images.smtmcapital.com.np/logos/{symbol.upper()}.png"
        self.log.debug(f"Added icon URL to ticker_info for symbol '{symbol}'")

        with cache_lock:
            self.data_cache[symbol_key] = scraped_data
            self.log.info(f"Stored combined data in cache for symbol '{symbol}'")

        return scraped_data

    def _build_url(self, section, symbol):
        # Normalize symbol to uppercase for consistent cache keys
        symbol = symbol.upper()
        if section == "market_status":
            return "https://www.onlinekhabar.com/smtm/home/market-status"
        endpoint = self.endpoints[section]
        if "{symbol}" in endpoint:
            return f"{self.base_url}/{endpoint.format(symbol=symbol)}"
        return f"{self.base_url}/{endpoint}/{symbol}"