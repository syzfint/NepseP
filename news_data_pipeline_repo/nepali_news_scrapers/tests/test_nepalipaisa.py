import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
import pytz
import json
from datetime import datetime
from nepali_news_scrapers.scrapers.nepalipaisa.nepalipaisa import NepaliPaisaScraper
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService
from .fixtures import scraper_service, mock_datetime, nepalipaisa_news_list, nepalipaisa_news_details, nepalipaisa_article_html

@pytest.fixture
def scraper(scraper_service):
    return NepaliPaisaScraper(scraper_service)

def test_make_request_url(scraper):
    url = scraper.make_request_url("api/GetNewsList")
    assert url == "https://nepalipaisa.com/api/GetNewsList", "Should create correct URL"

#build payload
def test_build_listing_payload(scraper):
    page = 3
    payload = scraper._build_listing_payload(page)
    assert payload == {
        "dateType": "",
        "dateFrom": "",
        "dateTo": "",
        "sectors": [],
        "companies": [],
        "categoryId": 0,
        "subCategoryId": 0,
        "pageNo": 3,
        "itemsPerPage": 24,
        "pagePerDisplay": 10,
        "newsType": "",
        "sectorGroup": ""
    }


def test_fetch_news_page_success(scraper, scraper_service, nepalipaisa_news_list):
    scraper_service.make_post_request.return_value = nepalipaisa_news_list
    result = scraper.fetch_news_page(2)
    assert result["statusCode"] == 200
    assert len(result["result"]["data"]) == 1
    assert result["result"]["data"][0]["newsData"][0]["newsId"] == 89474

def test_fetch_news_page_empty(scraper, scraper_service):
    scraper_service.make_post_request.return_value = {"statusCode": 200, "result": {"data": []}}
    result = scraper.fetch_news_page(1)
    assert result["statusCode"] == 200
    assert result["result"]["data"] == []

def test_should_continue_scraping(scraper, scraper_service):
    # Valid response
    news_list = {"statusCode": 200, "result": {"data": [{"newsData": []}]}}
    assert scraper.should_continue_scraping(news_list, 1) is True

    # empty response
    news_list = {}
    assert scraper.should_continue_scraping(news_list, 1) is False
    scraper_service.log.info.assert_called_with("Empty response at page 1. Stopping.")

    # Non-200 status
    news_list = {"statusCode": 404}
    assert scraper.should_continue_scraping(news_list, 1) is False
    scraper_service.log.info.assert_called_with("Non-200 status at page 1. Stopping.")

    # No data
    news_list = {"statusCode": 200, "result": {}}
    assert scraper.should_continue_scraping(news_list, 1) is False
    scraper_service.log.info.assert_called_with("No more data at page 1. Stopping.")

#test if it skips old news

def test_old_news_filtering(scraper, scraper_service, mock_datetime, mocker):
    mock_now = datetime(2025, 4, 28, 12, 0, tzinfo=pytz.timezone('Asia/Kathmandu'))
    
    # Patch the datetime module where it is imported in the scraper
    mocked_datetime = mocker.patch('nepali_news_scrapers.scrapers.nepalipaisa.nepalipaisa.datetime')
    mocked_datetime.now.return_value = mock_now
    mocked_datetime.strptime = datetime.strptime  
    mocked_datetime.timedelta = timedelta   

    assert scraper.is_recent_news("2025-04-28") is True
    assert scraper.is_recent_news("2025-04-26") is False
    assert scraper.is_recent_news("2025-04-27 23:59") is True
    assert scraper.is_recent_news("invalid-date") is True


#extract diff news from the listings  api 
def test_extract_news_items(scraper, nepalipaisa_news_list, mocker):
    mocker.patch.object(scraper, 'is_recent_news', return_value=True)
    news_items = list(scraper.extract_news_items(nepalipaisa_news_list))
    assert len(news_items) == 12 
    assert news_items[0]["newsId"] == 89474
    assert news_items[-1]["newsId"] == 89463

    # Test with non-recent news
    mocker.patch.object(scraper, 'is_recent_news', return_value=False)
    news_items = list(scraper.extract_news_items(nepalipaisa_news_list))
    assert len(news_items) == 0

def test_fetch_news_details_success(scraper, scraper_service, nepalipaisa_news_details):
    scraper_service.make_get_request.return_value = json.dumps(nepalipaisa_news_details)
    details = scraper.fetch_news_details(89474)
    assert details["url"] == "https://nepalipaisa.com/news-detail/89474"
    assert details["news_source"] == ""
   

#tesst related with a particular news
def test_fetch_news_details_no_response(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    details = scraper.fetch_news_details(89474)
    assert details is None
    scraper_service.log.error.assert_called_with("Failed to fetch details for news ID 89474")

def test_fetch_news_details_invalid_json(scraper, scraper_service):
    scraper_service.make_get_request.return_value = "invalid json"
    details = scraper.fetch_news_details(89474)
    assert details is None
    scraper_service.log.error.assert_called_with("Invalid JSON for news ID 89474: Expecting value: line 1 column 1 (char 0)")

def test_parse_news_details(scraper, nepalipaisa_news_details):
    result = scraper._parse_news_details(nepalipaisa_news_details["result"], 89466)
    assert result["url"] == "https://nepalipaisa.com/news-detail/89466"
    assert result["news_source"] == ""
    assert "नेपाल सुनचाँदी व्यवसायी महासंघका अनुसार आज सुन ३ हजार रुपैयाँ घटेको छ भने चाँदीको मूल्य ३४० रुपैयाँले ओरालो लागेको छ।" in result["content"]



#test to get all necessary data from listing api and news api
def test_build_article_data(scraper, nepalipaisa_news_list, nepalipaisa_news_details):
    news_item = next(item for item in nepalipaisa_news_list["result"]["data"][0]["newsData"] if item["newsId"] == 89474)
    details = scraper._parse_news_details(nepalipaisa_news_details["result"], 89474)
    article_data = scraper._build_article_data(news_item, details)
    assert article_data["url"] == "https://nepalipaisa.com/news-detail/89474"
    assert article_data["published_date"] == "2026-02-13"


def test_build_article_data_missing_fields(scraper):
    news_item = {"newsId": 83431}  
    details = {"url": "test.com", "content": "test"}
    article_data = scraper._build_article_data(news_item, details)
    assert article_data == {
        "url": "test.com",
        "published_date": "n/a",
        "published_time": "n/a",
        "category": "",
        "author": "NepaliPaisa",
        "title": "",
        "content": "test",
        "image_url": "",
        "company_symbols": []
    }


#test to make sure news data are sent to mini for upload
def test_process_news_item(scraper, scraper_service, nepalipaisa_news_list, nepalipaisa_news_details, mocker):
    news_item = next(item for item in nepalipaisa_news_list["result"]["data"][0]["newsData"] if item["newsId"] == 89474)
    scraper_service.make_get_request.return_value = json.dumps(nepalipaisa_news_details)
    scraper.process_news_item(news_item)
    scraper_service.save_json.assert_called_once()
    args, _ = scraper_service.save_json.call_args
    saved_data = args[0]
    assert saved_data["title"] == "महाशिवरात्रि विशेषः बागमती नदीको बहाव बढाउन धापड्यामबाट पानी छोडियो    "
    assert "स्थानीय बजारमा आज शुक्रबार सुन र चाँदी" in saved_data["content"]


def test_full_scraping_workflow(scraper, scraper_service, mocker):
    # Mock API responses
    scraper_service.make_post_request.side_effect = [
        {  # Page 1
            "statusCode": 200,
            "result": {"data": [{
                "newsDate": "2025-04-28",
                "newsData": [{"newsId": 1, "category": "Market"}]
            }]}
        },
        {  # Page 2
            "statusCode": 200,
            "result": {"data": []}
        }
    ]
    
    # Mock details response
    mocker.patch.object(scraper, 'fetch_news_details', return_value={
        "content": "test", "url": "url", "news_source": "test"
    })
    mocker.patch.object(scraper, 'is_recent_news', return_value=True)
    
    scraper.start()
    
    #verify 2 API calls and 1 article processed
    assert scraper_service.make_post_request.call_count == 2
    scraper_service.save_json.assert_called_once()

