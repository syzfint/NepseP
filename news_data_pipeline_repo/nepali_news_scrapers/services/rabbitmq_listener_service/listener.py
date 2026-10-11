import pika
import json
import time
import os
import ssl
import logging
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperRunner, Scraper,ScraperService
from nepali_news_scrapers.scrapers.insta_scraper.ronb_scraper import InstagramScraper

logger = logging.getLogger(__name__)

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        scraper_name = message.get("scraper_name")
        payload = message.get("payload", {})

        if not scraper_name:
            logger.warning("Invalid message: Missing scraper_name")
            ch.basic_ack(delivery_tag=method.delivery_tag) #acknowldege invalid message
            return
        
    

        # Acknowledge the message early
        ch.basic_ack(delivery_tag=method.delivery_tag)

        try:
            scraper_instance = ScraperRunner.get_scraper_instance(scraper_name)
            if isinstance(scraper_instance, InstagramScraper):
                scraper_instance.start(payload=payload)  # Ensure payload is passed
            else:
                scraper_instance.start()
        except ValueError as e:
            logger.error("Invalid scraper name: %s", e)
            return

        # scraper_instance.start()
        logger.info("Scraper %s succeeded", scraper_name)

    except json.JSONDecodeError:
        logger.warning("Invalid message format: Not valid JSON")
        ch.basic_ack(delivery_tag=method.delivery_tag)  # Avoid retrying bad messages

    except Exception as e:
        logger.exception("Callback error: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def establish_rabbitmq_connection():
    try:
        # Create an SSL context for secure connection.
        context = ssl.create_default_context()
        # For testing purposes only. For production, remove these two lines and use proper certificate validation.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST"),
                port=int(os.getenv("RABBITMQ_PORT")),
                virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
                credentials=pika.PlainCredentials(
                    os.getenv("RABBITMQ_USER"),
                    os.getenv("RABBITMQ_PASSWORD")
                ),
                ssl_options=pika.SSLOptions(context, os.getenv("RABBITMQ_HOST"))
            )
        )
        return connection
    except Exception as e:
        raise Exception(f"RabbitMQ Connection Error: {str(e)}")


def start_listener():
    while True:
        try:
            logger.info("Connecting to RabbitMQ...")
            # Create an SSL context
            context = ssl.create_default_context()
            # For testing, disable hostname checking and certificate verification.
            # For production, remove these two lines and use valid CA certificates.
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            connection = establish_rabbitmq_connection()
            channel = connection.channel()
            logger.info("Connected to RabbitMQ")

            channel.queue_declare(queue="scraper_tasks")
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="scraper_tasks", on_message_callback=callback)
            logger.info("Listening for messages...")
            channel.start_consuming()

        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
            logger.warning("Connection error: %s. Reconnecting in 5 seconds...", e)
            time.sleep(5)
        except pika.exceptions.ChannelWrongStateError as e:
            logger.warning("Channel error: %s. Attempting to reconnect...", e)
            time.sleep(5)
        except Exception as e:
            logger.exception("Unexpected listener error: %s. Exiting...", e)
            break

if __name__ == "__main__":
    start_listener()
