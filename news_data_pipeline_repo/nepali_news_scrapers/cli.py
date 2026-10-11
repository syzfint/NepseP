import sys
import argparse
import logging
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

from nepali_news_scrapers.logging_config import configure_logging
from nepali_news_scrapers.scrapers import scrapers
from nepali_news_scrapers.services.scraper_service import ScraperService
from nepali_news_scrapers.services.db_service import DbService
from nepali_news_scrapers.services.schedule_service import generate_and_store_trending_topics

load_dotenv()
configure_logging()

logger = logging.getLogger(__name__)

def run_scraper(scraper_name):
    if scraper_name not in scrapers:
        logger.error(f"Unknown scraper: {scraper_name}. Available: {list(scrapers.keys())}")
        sys.exit(2)

    db_service = DbService()
    tz = pytz.timezone("Asia/Kathmandu")
    
    # NEPSE 7-day logic
    if scraper_name == "nepse":
        last_run = db_service.get_last_run(scraper_name)
        now = datetime.now(tz)
        if last_run:
            if last_run.tzinfo is None:
                last_run = tz.localize(last_run)
            if (now - last_run) < timedelta(days=7):
                logger.info(f"Skipping NEPSE: Last run was {last_run} (7-day rule).")
                return 

    service = ScraperService()
    ScraperClass = scrapers[scraper_name]

    logger.info(f"Starting scraper: {scraper_name}")
    scraper = ScraperClass(service)

    if scraper_name == "instagram":
        scraper.start(payload={"username": "routineofnepalbanda"})
    else:
        scraper.start()

    if scraper_name == "nepse":
        db_service.set_last_run(scraper_name, datetime.now(tz))
        logger.info("Updated last run timestamp for NEPSE")

    logger.info(f"Finished scraper: {scraper_name}")

def run_trending():
    logger.info("Starting Trending Topics Generation...")
    success = generate_and_store_trending_topics()
    if success:
        logger.info("Trending topics generated and stored successfully.")
    else:
        logger.info("No trending topics generated (insufficient new data or already updated recently).")

def main():
    parser = argparse.ArgumentParser(description="Nepali News Scrapers CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: scrape <name>
    scrape_parser = subparsers.add_parser("scrape", help="Run a specific scraper")
    scrape_parser.add_argument("name", help="The key name of the scraper")

    # Command: trending
    subparsers.add_parser("trending", help="Generate trending topics from recent news")

    args = parser.parse_args()

    if args.command == "scrape":
        run_scraper(args.name)
    elif args.command == "trending":
        run_trending()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()