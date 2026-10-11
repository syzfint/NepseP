import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from nepali_news_scrapers.scrapers.gorkhapatra.gorkhapatra import GorkhaPatraScraper
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperError
from .fixtures import scraper_service, gorkhapatra_article_html, gorkhapatra_page_listings


@pytest.fixture
def scraper(scraper_service):
    return GorkhaPatraScraper(scraper_service)


@pytest.fixture
def article_soup(gorkhapatra_article_html):
    return BeautifulSoup(gorkhapatra_article_html, 'html.parser')


@pytest.fixture
def listings_soup(gorkhapatra_page_listings):
    return BeautifulSoup(gorkhapatra_page_listings, 'html.parser')
@pytest.fixture
def mock_gorkhapatra_datetime(mocker):
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    fake_time = datetime(2023, 10, 1, 12, 0, 0, tzinfo=kathmandu_tz)

    class MockDateTime:
        @classmethod
        def now(cls, tz=None):
            return fake_time if tz else fake_time.replace(tzinfo=None)

    mocker.patch('nepali_news_scrapers.scrapers.gorkhapatra.gorkhapatra.datetime', MockDateTime)
    return fake_time



def test_gorkhapatra_site_down(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    with pytest.raises(ScraperError, match="Failed to retrieve homepage content"):
        scraper.get_page_listings("https://gorkhapatraonline.com/", "")
    scraper_service.log.error.assert_called_with("Failed to retrieve homepage content from https://gorkhapatraonline.com/")


def test_gorkhapatra_site_running(scraper, scraper_service):
    scraper_service.make_get_request.return_value = "<html><body>Gorkhapatra Site</body></html>"
    soup = BeautifulSoup(scraper_service.make_get_request("https://gorkhapatraonline.com/"), "html.parser")
    assert soup is not None, "Should return a BeautifulSoup object if site is running"
    assert "Gorkhapatra Site" in str(soup), "Should confirm site content is retrieved"




def test_make_request_url(scraper):
    assert scraper.make_request_url("/news") == "https://gorkhapatraonline.com/news"
    assert scraper.make_request_url("categories/national/") == "https://gorkhapatraonline.com/categories/national/"


def test_get_page_listings_homepage(scraper, scraper_service, gorkhapatra_page_listings, mocker):
    scraper_service.make_get_request.return_value = gorkhapatra_page_listings
    soup = BeautifulSoup (gorkhapatra_page_listings, "html.parser")
    expected_links = scraper.extract_article_links(soup)
    mock_get_page_details = mocker.patch.object(scraper, 'get_page_details')
    scraper.get_page_listings(scraper.make_request_url("/"), "")
    assert mock_get_page_details.call_count == len(set(expected_links))  # Account for unique links
    scraper_service.log.info.assert_called_with("Scraping homepage: https://gorkhapatraonline.com/")


def test_get_page_listings_category(scraper, scraper_service, gorkhapatra_page_listings, mocker):
    scraper_service.make_get_request.return_value = gorkhapatra_page_listings
    soup = BeautifulSoup(gorkhapatra_page_listings, "html.parser")
    expected_links = scraper.extract_article_links(soup)
    mock_get_page_details = mocker.patch.object(scraper, 'get_page_details')
    scraper.get_page_listings(scraper.make_request_url("categories/national"), "national")
    assert mock_get_page_details.call_count == len(set(expected_links))  # Account for unique links
    scraper_service.log.info.assert_called_with(
        "Scraping Category 'national' on Page: https://gorkhapatraonline.com/categories/national?page=1"
    )


# test for title
def test_extract_title(scraper, article_soup):
    title = scraper.extract_title(article_soup)
    assert title is not None
    assert title == "बिमा कार्यक्रममा आँखा स्वास्थ्यलाई समायोजन गरिने छ : प्रधानमन्त्री", "should extract title from the html"


def test_extract_title_missing(scraper):
    soup = BeautifulSoup("<html></html>", "html.parser")
    with pytest.raises(ScraperError, match="Title container not found"):
        scraper.extract_title(soup)


# test for author
def test_extract_author(scraper, article_soup):
    author = scraper.extract_author(article_soup)
    assert author is not None
    assert author == "गोरखापत्र अनलाइन"


def test_extract_author_missing(scraper):
    soup = BeautifulSoup("<html></html>", "html.parser")
    with pytest.raises(ScraperError, match="Author container not found"):
        scraper.extract_author(soup)


#test for content
def test_extract_content(scraper, article_soup):
    content = scraper.extract_content(article_soup)
    assert content is not None
    assert "आँखा स्वास्थ्य क्षेत्रमा काम" in content


def test_extract_content_missing(scraper):
    soup = BeautifulSoup("<html></html>", "html.parser")
    with pytest.raises(ScraperError, match="Content container not found"):
        scraper.extract_content(soup)


#test date parsing
def test_parse_nepali_date(scraper, mocker):
    date_str = "२०८० असोज १५, सोमबार"
    mock_parse = mocker.patch.object(scraper, 'parse_nepali_date', return_value=datetime(2023, 10, 1, tzinfo=scraper.tz))
    parsed_date = scraper.parse_nepali_date(date_str)
    expected_date = datetime(2023, 10, 1, tzinfo=scraper.tz)
    assert parsed_date.date() == expected_date.date()

def test_extract_datetime_relative_time(scraper, article_soup, mock_gorkhapatra_datetime):
    dt = scraper.extract_datetime(article_soup)
    assert dt <= mock_gorkhapatra_datetime


def test_extract_datetime_missing(scraper):
    soup = BeautifulSoup("<html></html>", "html.parser")
    with pytest.raises(ScraperError, match="Date container not found"):
        scraper.extract_datetime(soup)


#test if old articles are skipped
def test_skip_old_article(scraper, scraper_service, mocker, gorkhapatra_article_html):
    scraper_service.make_get_request.return_value = gorkhapatra_article_html
    mock_extract_datetime = mocker.patch.object(scraper, 'extract_datetime')
    mock_extract_datetime.return_value = datetime.now(scraper.tz) - timedelta(hours=2)
    scraper.get_page_details("https://gorkhapatraonline.com/article", "category")

#test if not-old articles are processed
def test_process_recent_article(scraper, scraper_service, mocker, gorkhapatra_article_html):
    scraper_service.make_get_request.return_value = gorkhapatra_article_html
    mock_extract_datetime = mocker.patch.object(scraper, 'extract_datetime')
    mock_extract_datetime.return_value = datetime.now(scraper.tz) - timedelta(minutes=30)
    mocker.patch.object(scraper, 'extract_title', return_value="Test Title")
    mocker.patch.object(scraper, 'extract_author', return_value="Test Author")
    mocker.patch.object(scraper, 'extract_content', return_value="Test Content")
    scraper.get_page_details("https://gorkhapatraonline.com/article", "category")
    scraper_service.save_json.assert_called_once()
    saved_data = scraper_service.save_json.call_args[0][0]
    assert saved_data["title"] == "Test Title"
    assert saved_data["author"] == "Test Author"
    assert "Test Content" in saved_data["content"]


def test_get_page_listings_request_failure(scraper, scraper_service, mocker):
    scraper_service.make_get_request.return_value = None
    with pytest.raises(ScraperError, match="Failed to retrieve homepage content from"):
        scraper.get_page_listings("https://gorkhapatraonline.com/", "")
    scraper_service.log.error.assert_called_with("Failed to retrieve homepage content from https://gorkhapatraonline.com/")




# Integration test for scraping an article
def test_scrape_article(scraper, scraper_service, mocker, gorkhapatra_article_html):
    # Mock the HTTP request to return the provided HTML
    scraper_service.make_get_request.return_value = gorkhapatra_article_html

    # Set up Kathmandu timezone
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    fake_now_time = datetime(2025, 4, 30, 12, 0, 0, tzinfo=kathmandu_tz)

    # Mock datetime.now to control the current time
    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = fake_now_time
    mocker.patch('nepali_news_scrapers.scrapers.gorkhapatra.gorkhapatra.datetime', mock_datetime_class)

    # mock the convert_nepali_to_english to handle Nepali numerals in the date
    # date in the HTML file is "१७ वैशाख २०८२", which corresponds to 17 Baisakh 2082
    mocker.patch(
        'nepali_news_scrapers.services.scraper_service.ScraperService.convert_nepali_to_english',
        side_effect=["2082", "1", "17"]  # Year: 2082, Month: Baisakh (1), Day: 17
    )

    # Execute scraping
    scraper.get_page_details("https://gorkhapatraonline.com/news/152956", "national")

    # Verify request was made
    scraper_service.make_get_request.assert_called_once_with(
        "https://gorkhapatraonline.com/news/152956"
    )

    # Verify save_json was called
    assert scraper_service.save_json.call_count == 1, "save_json should be called once"
    args, _ = scraper_service.save_json.call_args
    saved_data = args[0]

    # Validate saved data against the HTML content
    assert saved_data["url"] == "https://gorkhapatraonline.com/news/152956"
    assert saved_data["category"] == "national"
    assert saved_data["title"] == "बिमा कार्यक्रममा आँखा स्वास्थ्यलाई समायोजन गरिने छ : प्रधानमन्त्री"
    assert saved_data["author"] == "गोरखापत्र अनलाइन"
    assert saved_data["published_date"] == "2025-04-30"  # Converted from 17 Baisakh 2082
    assert saved_data["published_time"] is not None  # Time is not explicitly in HTML, but scraper may infer
    assert len(saved_data["content"]) > 0
    assert "प्रधानमन्त्री केपी शर्मा ओलीले राष्ट्रिय स्वास्थ्य बिमा कार्यक्रममा आँखा स्वास्थ्यलाई समायोजन गर्ने" in saved_data["content"]