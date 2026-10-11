import json
import time
import logging
from typing import Optional
from nepali_news_scrapers.services.db_service import DbService
from pydantic import BaseModel
from nepali_news_scrapers.services.rabbitmq_listener_service.listener import (
    start_listener,
    establish_rabbitmq_connection,
)
import asyncio
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)


class ScraperRequest(BaseModel):
    name: str
    username: Optional[str] = None


def wait_for_rabbitmq(max_retries=20, delay=15):
    for attempt in range(max_retries):
        try:
            connection = establish_rabbitmq_connection()
            logger.info("RabbitMQ connection established on attempt %s.", attempt + 1)
            return connection
        except Exception:
            logger.warning(
                "RabbitMQ not ready (Attempt %s/%s). Retrying in %s seconds...",
                attempt + 1,
                max_retries,
                delay,
            )
            time.sleep(delay)
    raise Exception("RabbitMQ connection failed after multiple attempts.")


def trigger_scrapers_loop():
    scrapers = [
        "nepse",
        "kantipur",
        "instagram",
        "kathmandupost",
        "annapurna",
        "nepalitimes",
        "setopati",
        "nepalipaisa",
        "merolagani",
        "gorkhapatra",
        "republica",
        "nrb",
        "sharesansar",
        "icra",
    ]
    connection = wait_for_rabbitmq()
    tz = pytz.timezone("Asia/Kathmandu")

    try:
        channel = connection.channel()
        channel.queue_declare(queue="scraper_tasks")
        for scraper in scrapers:
            # Skip NEPSE if it ran within the last 7 days
            if scraper == "nepse":
                last_run = DbService().get_last_run(scraper)
                now = datetime.now(tz)
                if last_run and (now - last_run) < timedelta(days=7):
                    logger.info("Skipping NEPSE scraper; last run was %s", last_run)
                    continue

            try:
                logger.info("Triggering scraper: %s", scraper)
                channel.basic_publish(
                    exchange="",
                    routing_key="scraper_tasks",
                    body=json.dumps({"scraper_name": scraper}),
                )
                logger.info("Triggered scraper: %s", scraper)

                # Update last run timestamp for NEPSE
                if scraper == "nepse":
                    DbService().set_last_run(scraper, datetime.now(tz))

                time.sleep(1)
            except Exception as e:
                logger.exception("Failed to trigger scraper %s: %s", scraper, e)
        logger.info("All scrapers triggered successfully")
    except Exception as e:
        logger.exception("Error while triggering scrapers: %s", e)
    finally:
        if connection.is_open:
            connection.close()


async def start_scrapers():
    trigger_scrapers_loop()


if __name__ == "__main__":
    asyncio.run(start_scrapers())
