import pytest
from unittest.mock import Mock
from datetime import datetime
import pytz
from nepali_news_scrapers.scrapers.nepali_times.nepali_times import NepaliTimesScraper
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService
from .fixtures import graphql_response , nepalitimes_article_html,scraper_service
from datetime import timedelta

@pytest.fixture
def scraper(scraper_service):
    return NepaliTimesScraper(scraper_service)

#test makerequest
def test_make_request_url(scraper):
    url = scraper.make_request_url("news/a-new-architecture-for-nepals-tourism")
    assert url == "https://nepalitimes.com/news/a-new-architecture-for-nepals-tourism", "Should make a complete url"

#graphql response test
def test_fetch_articles_success(scraper,scraper_service,graphql_response):
    scraper_service.make_post_request.return_value = graphql_response
    articles= scraper.fetch_articles(40) #40 is routeId of a cateogry
    assert articles[0]["id"]==8131
    assert articles[1]["id"]== 8108

def test_fetch_articles_empty(scraper,scraper_service):
    scraper_service.make_post_request.return_value = {"data": {"items": []}}
    articles= scraper.fetch_articles(40) #40 is routeId of a cateogry
    assert articles== []


#date parsing test
def test_parse_published_date_valid(scraper):
    dt = scraper.parse_published_date("2025-04-21T02:18:11")
    ktm_tz = pytz.timezone('Asia/Kathmandu')
    expected_naive = datetime(2025, 4, 21, 2, 18, 11)
    expected = ktm_tz.localize(expected_naive)
    assert dt == expected

def test_parse_published_date_invalid(scraper, scraper_service):
    dt = scraper.parse_published_date("invalid-date")
    assert dt is None
    scraper_service.log.error.assert_called()

def test_is_recent_with_actual_json_time(scraper, graphql_response, mocker):
    article = graphql_response["data"]["items"][0]
    published_dt = scraper.parse_published_date(article["published_at"])
    assert published_dt is not None, "Failed to parse the publication date from JSON"

    ktm_tz = pytz.timezone('Asia/Kathmandu')
    scraper.tz = ktm_tz

    #checks if the parsed dt is skipped or not
    now_recent = published_dt 
    mock_datetime = mocker.patch('nepali_news_scrapers.scrapers.nepali_times.nepali_times.datetime')
    mock_datetime.now.return_value = now_recent
    assert scraper.is_recent(published_dt) is True, "Article should be considered recent (within 24 hours)"

    #adds 2 days to parsed dt and checks if it skipped or not
    now_old = published_dt + timedelta(days=2)
    mock_datetime.now.return_value = now_old
    assert scraper.is_recent(published_dt) is False, "Article should not be considered recent (older than 24 hours)"


#test for extracting content from html
def test_get_details_success(scraper, scraper_service, nepalitimes_article_html):
    scraper_service.make_get_request.return_value = nepalitimes_article_html
    content = scraper.get_details("https://nepalitimes.com/news/a-new-architecture-for-nepals-tourism")
    assert "Esteva was in Kathmandu with his " in content

def test_get_details_no_body(scraper, scraper_service):
    scraper_service.make_get_request.return_value = "<html><body></body></html>"
    content = scraper.get_details("https://nepalitimes.com/news/a-new-architecture-for-nepals-tourism")
    assert content is None
    scraper_service.log.warning.assert_called_with("Article body not found in HTML")


def test_get_details_no_response(scraper, scraper_service):

    scraper_service.make_get_request.return_value = None
    content = scraper.get_details("https://nepalitimes.com/news/a-new-architecture-for-nepals-tourism")

    assert content is None
    scraper_service.log.error.assert_called_with(
        "Failed to fetch article content from https://nepalitimes.com/news/a-new-architecture-for-nepals-tourism"
    )



#esting process_article
def test_process_article_recent(scraper, scraper_service, graphql_response, nepalitimes_article_html, mocker):
    article = graphql_response["data"]["items"][0]
    mocker.patch.object(scraper, 'is_recent', return_value=True)
    scraper_service.make_get_request.return_value = nepalitimes_article_html
    scraper.process_article(article, "news")
    scraper_service.save_json.assert_called_once()
    args, _ = scraper_service.save_json.call_args
    data = args[0]
    assert data["id"] == 8131
    assert data["category"] == "news"
    assert data["title"] == "A new architecture for Nepal's tourism"
    assert "Esteva was in Kathmandu" in data["content"]


#integration test
def test_full_workflow(scraper, scraper_service, graphql_response, nepalitimes_article_html, mocker):
    scraper.categories = {"news": 8}  
    scraper_service.make_post_request.return_value = graphql_response
    mocker.patch.object(scraper, 'is_recent', return_value=True)
    scraper_service.make_get_request.return_value = nepalitimes_article_html
    scraper.start()
    assert scraper_service.save_json.call_count >1  # Expect more than 1 article from graphql_response
    # Check all calls to save_json
    saved_articles = [call[0][0] for call in scraper_service.save_json.call_args_list]
    saved_ids = [article["id"] for article in saved_articles]
    assert saved_ids == [8131, 8108], f"Expected article IDs [8131, 8108], got {saved_ids}"
    
    assert saved_articles[0]["content"], "Content should not be empty"