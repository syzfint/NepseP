import logging
import threading
import time

from dotenv import load_dotenv

from nepali_news_scrapers.logging_config import configure_logging

load_dotenv()
configure_logging()

from nepali_news_scrapers.services.rabbitmq_listener_service.listener import start_listener  # Import listener function
from nepali_news_scrapers.services.schedule_service import start_scheduler

logger = logging.getLogger(__name__)
# def main(name, listen):
#     if listen:
#     elif name:
#         try:
#             scraper_instance = ScraperRunner.get_scraper_instance(name)
#             scraper_instance.start()
#         except ValueError as e:
#             print(f"Error: {e}")
#             sys.exit(2)  # Special exit code for invalid scrapers
#     else:
#         print("Use --listen to start the listener or --name to run a scraper")


def main():
    logger.info("Starting both scheduler and listener in separate threads...")

    # Start schdler in a thread
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    # start listner in a thread
    listener_thread = threading.Thread(target=start_listener, daemon=True)
    listener_thread.start()

    # Keep the main thread alive
    while True:
        time.sleep(10)

if __name__ == "__main__":
    # start_listener()
    main()
