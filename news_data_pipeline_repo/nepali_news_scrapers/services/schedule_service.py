import schedule
import time
import threading
import traceback
from datetime import timedelta, datetime
import pytz
from nepali_news_scrapers.services.trigger_scraper_service import trigger_scrapers_loop
import logging
from nepali_news_scrapers.services.db_service import DbService
from nepali_news_scrapers.services.llm.factory import get_llm_provider

TARGET_TIMEZONE = "Asia/Kathmandu"
last_scrape_trending_topics = []
db_service = DbService()

def generate_and_store_trending_topics():
    max_attempts = 3
    tz = pytz.timezone(TARGET_TIMEZONE)
    now = datetime.now(tz)
    logging.info(f"Starting generate_and_store_trending_topics at {now}")

    latest_topics_info = db_service.get_trending_topics_with_timestamp()
    if latest_topics_info:
        latest_timestamp = latest_topics_info.get("created_at")
        logging.info(f"Latest timestamp: {latest_timestamp}")

        if latest_timestamp.tzinfo is None:
            latest_timestamp = tz.localize(latest_timestamp)
        freshness_threshold = now - timedelta(minutes=20)
        logging.info(f"Freshness threshold: {freshness_threshold}")
        try:
            if latest_timestamp >= freshness_threshold:
                logging.info(f"Skipping generation: Recent topics from {latest_timestamp}")
                return True
        except TypeError as e:
            logging.error(f"TypeError in timestamp comparison: {e}, latest_timestamp: {latest_timestamp}, freshness_threshold: {freshness_threshold}")
            traceback.print_exc()
            return False

    for attempt in range(max_attempts):
        try:
            one_hour_ago = now - timedelta(hours=1)
            logging.info(f"Generating topics for time range: {one_hour_ago} to {now}")
            llm = get_llm_provider()
            logging.info("Fetching articles from last hour")

            articles = db_service.get_articles_last_hour()
            if not articles:
                logging.warning("No articles found")
                return False
            logging.info(f"Found {len(articles)} articles")

            valid_articles = [a for a in articles if a.get("summary")]
            if not valid_articles:
                logging.warning("No valid articles with summaries found")
                return False

            trending_topics = llm.get_trending_topics(valid_articles)
            if trending_topics:
                success = db_service.add_trending_topics(trending_topics)
                if success:
                    logging.info(f"Successfully stored trending topics: {trending_topics}")
                    return True
            logging.warning("Failed to generate trending topics")
            return False
        except Exception as e:
            if attempt < max_attempts - 1:
                logging.error(f"Attempt {attempt + 1} failed: {e}. Retrying in 5 seconds")
                time.sleep(5)
            else:
                logging.error(f"Failed after {max_attempts} attempts: {e}")
                return False

def safe_trigger_scrapers():
    global last_scrape_trending_topics
    try:
        tz = pytz.timezone(TARGET_TIMEZONE)
        now = datetime.now(tz)
        logging.info(f"Starting safe_trigger_scrapers at {now}")

        # Skip runs between 11 PM and 8 AM
        if now.hour >= 23 or now.hour < 8:
            logging.info(f"Skipping run: Between 11 PM and 8 AM in {TARGET_TIMEZONE}")
            return

        logging.info(f"Running scrapers at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        if last_scrape_trending_topics:
            logging.info("Trending topics from last scrape: %s", last_scrape_trending_topics)
        else:
            logging.info("No trending topics from last scrape")

        logging.info("Triggering scrapers")
        trigger_scrapers_loop()

        # Schedule trending topics generation
        def schedule_trending_topics():
            logging.info("Waiting 1 hour before generating trending topics")
            time.sleep(3600)  # Wait 1 hour
            logging.info("Running first attempt to generate trending topics")
            success = generate_and_store_trending_topics()
            if not success:
                logging.info("First attempt failed, waiting 5 minutes for retry")
                time.sleep(300)  # Wait 5 minutes
                logging.info("Running second attempt to generate trending topics")
                success = generate_and_store_trending_topics()
                if not success:
                    logging.info("Second attempt failed, waiting 5 minutes for final retry")
                    time.sleep(300)  # Wait 5 minutes
                    logging.info("Running final attempt to generate trending topics")
                    generate_and_store_trending_topics()
            else:
                logging.info("Trending topics generated successfully, skipping retries")

        threading.Thread(target=schedule_trending_topics, daemon=True).start()

        last_scrape_trending_topics = db_service.get_trending_topics()

    except Exception as e:
        logging.error(f"Exception during scraper run: {e}")
        traceback.print_exc()

def schedule_scrapers():
    logging.info("Scheduler loop started")
    # Run immediately on start
    threading.Thread(target=safe_trigger_scrapers, daemon=True).start()

    def run_in_thread():
        threading.Thread(target=safe_trigger_scrapers, daemon=True).start()

    schedule.every(1).hours.do(run_in_thread)
    while True:
        schedule.run_pending()
        time.sleep(1)

def start_scheduler():
    logging.info("Starting scheduler in a thread")
    scheduler_thread = threading.Thread(target=schedule_scrapers, daemon=True)
    scheduler_thread.start()