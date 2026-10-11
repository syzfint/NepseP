import pytest
from unittest.mock import Mock, MagicMock
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from pytest_mock import mocker
from nepali_news_scrapers.scrapers.myrepublica.myrepublica import MyRepublicaScraper, USER_AGENTS
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService, ScraperError
from .fixtures import republica_article_html, republica_page_listings, scraper_service, mock_datetime

@pytest.fixture
def scraper(scraper_service):
    return MyRepublicaScraper(scraper_service)

@pytest.fixture
def article_soup(republica_article_html):
    try:
        return BeautifulSoup(republica_article_html, 'lxml')
    except ImportError:
        return BeautifulSoup(republica_article_html, 'html.parser')

@pytest.fixture
def listings_soup(republica_page_listings):
    try:
        return BeautifulSoup(republica_page_listings, 'lxml')
    except ImportError:
        return BeautifulSoup(republica_page_listings, 'html.parser')

#helper functions /utilities tests
def test_make_request_url(scraper):
    result = scraper.make_request_url("/category/economy?page=1")
    assert result == "https://myrepublica.nagariknetwork.com/category/economy?page=1", "Should construct correct URL"

def test_get_random_user_agent(scraper):
    user_agent = scraper.get_random_user_agent()
    assert user_agent in USER_AGENTS, "Should return a valid User-Agent"

def test_get_request_headers(scraper):
    headers = scraper.get_request_headers()
    assert "User-Agent" in headers, "Headers should include User-Agent"
    assert headers["Accept"] == "*/*", "Headers should include correct Accept value"

#site cnnectivity tests
def test_republica_site_down(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    content = scraper_service.make_get_request("https://myrepublica.nagariknetwork.com")
    assert content is None, "Should return None when the site is down"

def test_republica_site_running(scraper, scraper_service, republica_article_html):
    scraper_service.make_get_request.return_value = republica_article_html
    content = scraper_service.make_get_request("https://myrepublica.nagariknetwork.com")
    assert content is not None, "Should return content when the site is running"
    assert "republica" in content.lower(), "Should contain expected site identifier from real HTML"

#tests for extracting diff fields
def test_fetch_page_content_success(scraper, scraper_service, republica_article_html):
    scraper_service.make_get_request.return_value = republica_article_html
    content = scraper.fetch_page_content("https://myrepublica.nagariknetwork.com/news/xyz-news123-abc")
    assert content == republica_article_html, "Should return page content"


def test_fetch_page_content_no_response(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    with pytest.raises(ScraperError, match="Failed to fetch page content"):
        scraper.fetch_page_content("https://myrepublica.nagariknetwork.com/news/xyz-news123-abc")

def test_fetch_page_content_503_error(scraper, scraper_service):
    scraper_service.make_get_request.return_value = "503 Service Unavailable"
    with pytest.raises(ScraperError, match="Received 503 error"):
        scraper.fetch_page_content("https://myrepublica.nagariknetwork.com/news/xyz-news123-abc")


def test_extract_title(scraper, article_soup):
    title = scraper.extract_title(article_soup)
    assert title is not None, "Should extract title"
    assert title != "No Title", "Should extract a valid title from real HTML"
    assert title == "India and Pakistan troops exchange fire in Kashmir", "Should extract correct title"

def test_extract_title_no_title(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    title = scraper.extract_title(soup)
    assert title == "No Title", "Should return default title if missing"

def test_extract_category(scraper, article_soup):
    category = scraper.extract_category(article_soup)
    assert category is not None, "Should extract category"
    assert category != "No Category", "Should extract a valid category from real HTML"
    assert category == "WORLD", "Should extract correct category"

def test_extract_category_no_category(scraper):
    html = "<html><body><span class='rep-body--small--sans'>1</span></html>"
    soup = BeautifulSoup(html, 'html.parser')
    category = scraper.extract_category(soup)
    assert category == "No Category", "Should return default category if missing"

def test_extract_author(scraper, article_soup):
    author = scraper.extract_author(article_soup)
    assert author is not None, "Should extract author"
    assert author == "AFP/RSS", "Should extract correct author"

def test_extract_author_no_author(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    author = scraper.extract_author(soup)
    assert author == "No Author", "Should return default author if missing"

def test_extract_publish_datetime(scraper, republica_article_html):
    date, time = scraper.extract_publish_datetime(republica_article_html)
    assert date != "Unknown" or time != "Unknown", "Should extract valid date/time from real HTML"
    assert date == "2025-04-27", "Should extract correct date"
    assert time == "12:40:00", "Should extract correct time"

def test_extract_publish_datetime_invalid(scraper):
    page_text = "<html>No date here</html>"
    date, time = scraper.extract_publish_datetime(page_text)
    assert date == "Unknown", "Should return Unknown date if invalid"
    assert time == "Unknown", "Should return Unknown time if invalid"


def test_extract_tags(scraper, article_soup):
    tags = scraper.extract_tags(article_soup)
    assert isinstance(tags, list), "Should return a list of tags"

def test_extract_tags_no_tags(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    tags = scraper.extract_tags(soup)
    assert tags == [], "Should return empty list if no tags"

def test_extract_content(scraper, article_soup):
    content = scraper.extract_content(article_soup)
    assert isinstance(content, list), "Should return a list of paragraphs"
    assert content, "Should extract at least one paragraph from real HTML"
    assert any('supporting "cross-border terrorism" after gunmen' in para for para in content), "Should contain expected text"

def test_extract_content_no_content(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    content = scraper.extract_content(soup)
    assert content == [], "Should return empty list if no content"

#tests for page listings and featuredsection withing page listing
def test_get_page_listing_no_listings(scraper, scraper_service):
    html = "<html><body></body></html>"
    scraper_service.make_get_request.return_value = html
    scraper.get_page_listing("economy")
    scraper_service.log.info.assert_called_with("No more listings found for category 'economy'.")

def test_get_page_listing_with_real_html(scraper, scraper_service, republica_page_listings, mocker):
    scraper_service.make_get_request.return_value = republica_page_listings
    mock_get_page_details = mocker.patch.object(scraper, 'get_page_details')
    scraper.get_page_listing("economy")
    expected_url = "https://myrepublica.nagariknetwork.com/news/bagmati-province-govt-spends-32-of-budget-in-nine-months-of-current-fy-49-27.html"
    mock_get_page_details.assert_any_call(expected_url)
    scraper_service.log.info.assert_any_call(mocker.ANY)
    scraper.listed_urls.add(expected_url)
    mock_get_page_details.reset_mock()
    scraper.get_page_listing("economy")
    assert not any(expected_url in call[0][0] for call in mock_get_page_details.call_args_list), "Should not process duplicate URL"

def test_get_featured_sections_no_container(scraper, scraper_service):
    html = "<html><body></body></html>"
    scraper_service.make_get_request.return_value = html
    scraper.get_featured_sections("https://myrepublica.nagariknetwork.com/category/economy")
    scraper_service.log.warning.assert_called_with("Featured section container not found.")

def test_get_featured_sections_with_urls(scraper, scraper_service, republica_page_listings, mocker):

    scraper_service.make_get_request.return_value = republica_page_listings
    mock_get_page_details = mocker.patch.object(scraper, 'get_page_details')
    scraper.get_featured_sections("https://myrepublica.nagariknetwork.com/category/economy")
    assert mock_get_page_details.called, "Should call get_page_details for featured URLs"
    mock_get_page_details.assert_any_call(
        "https://myrepublica.nagariknetwork.com/news/poultry-farmers-hike-egg-price-70-42.html"
    )

# integration tests
def test_get_page_details_with_real_html(scraper, scraper_service, republica_article_html, mocker):
    scraper_service.make_get_request.return_value = republica_article_html
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    mock_current_time = datetime(2025, 4, 27, 13, 0, 0, tzinfo=kathmandu_tz)
    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = mock_current_time
    mocker.patch('nepali_news_scrapers.scrapers.myrepublica.myrepublica.datetime', mock_datetime_class)
    url = "https://myrepublica.nagariknetwork.com/news/xyz-news123-abc"
    scraper.get_page_details(url)
    scraper_service.save_json.assert_called_once()
    args, _ = scraper_service.save_json.call_args
    news_data = args[0]
    assert news_data["url"] == url, "URL should match"
    assert news_data["title"] == "India and Pakistan troops exchange fire in Kashmir", "Title should match"
    assert news_data["category"] == "WORLD", "Category should match"
    assert news_data["author"] == "AFP/RSS", "Author should match"
    assert news_data["published_date"] == "2025-04-27", "Date should match HTML"
    assert news_data["published_time"] == "12:40:00", "Time should match HTML"
    assert isinstance(news_data["content"], list), "Content should be a list"
    assert len(news_data["content"]) > 0, "Content should not be empty"
    assert any(
        'India has accused Pakistan' in para for para in news_data["content"]
    ), "Content should contain expected text"
    
    assert isinstance(news_data["tags"], list), "Tags should be a list"


#skip old news test
def test_get_page_details_skip_old_news(scraper, scraper_service, mocker, republica_article_html):
    scraper_service.make_get_request.return_value = republica_article_html
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    mock_current_time = datetime(2025, 4, 27, 14, 0, 0, tzinfo=kathmandu_tz)
    mock_datetime_class = MagicMock(wraps=datetime)

    mock_datetime_class.now.return_value = mock_current_time
    mocker.patch('nepali_news_scrapers.scrapers.myrepublica.myrepublica.datetime', mock_datetime_class)
    url = "https://myrepublica.nagariknetwork.com/news/some-news"
    scraper.get_page_details(url)
    scraper_service.save_json.assert_not_called()
    scraper_service.log.info.assert_called_with(f"Skipping news at {url} as it is older than 1 hour")

#test to process news
def test_get_page_details_process_recent_news(scraper, scraper_service, mocker, republica_article_html):
    scraper_service.make_get_request.return_value = republica_article_html
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    mock_current_time = datetime(2025, 4, 27, 13, 0, 0, tzinfo=kathmandu_tz)
    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = mock_current_time
    mocker.patch('nepali_news_scrapers.scrapers.myrepublica.myrepublica.datetime', mock_datetime_class)
    url = "https://myrepublica.nagariknetwork.com/news/some-news"
    scraper.get_page_details(url)
    scraper_service.save_json.assert_called_once()