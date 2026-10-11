import pytest
import re
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from nepali_news_scrapers.scrapers.sharesansar.sharesansar import ShareSansarScraper
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService
from .fixtures import scraper_service, sharesansar_article_html, sharesansar_page_listings

@pytest.fixture
def scraper(scraper_service):
    return ShareSansarScraper(scraper_service)

@pytest.fixture
def article_soup(sharesansar_article_html):
    try:
        return BeautifulSoup(sharesansar_article_html, 'lxml')
    except ImportError:
        return BeautifulSoup(sharesansar_article_html, 'html.parser')

@pytest.fixture
def listings_soup(sharesansar_page_listings):
    try:
        return BeautifulSoup(sharesansar_page_listings, 'lxml')
    except ImportError:
        return BeautifulSoup(sharesansar_page_listings, 'html.parser')

# Test make_request_url
def test_make_request_url(scraper):
    url = scraper.make_request_url("category/exclusive")
    assert url == "https://www.sharesansar.com/category/exclusive", "Should construct a complete URL"

# Test site availability
def test_sharesansar_site_running(scraper, scraper_service):
    scraper_service.make_get_request.return_value = "<html><body>ShareSansar</body></html>"
    content = scraper_service.make_get_request("https://www.sharesansar.com/")
    assert content is not None, "Should return content if site is running"

def test_sharesansar_site_down(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    content = scraper_service.make_get_request("https://www.sharesansar.com/")
    assert content is None, "Should return None if site is down"

#test individual field extraction
def test_extract_title(scraper, article_soup):
    expected_title = "Bonus Share of Green Ventures Limited Listed in NEPSE"
    assert scraper.extract_title(article_soup) == expected_title, "Should extract the correct title"

def test_extract_title_no_title(scraper):
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert scraper.extract_title(soup) == "N/A", "Should return 'N/A' if title is missing"

def test_extract_author(scraper, article_soup):
    expected_author = "-ShareSansar"
    assert scraper.extract_author(article_soup) == expected_author, "Should extract the correct author"

def test_extract_author_no_author(scraper):
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert scraper.extract_author(soup) == "Unknown", "Should return 'Unknown' if author is missing"

def test_extract_category(scraper, article_soup):
    expected_categories = ["Latest", "NEPSE News"]  
    categories = scraper.extract_category(article_soup)
    assert categories == expected_categories, "Should extract the correct categories"
    assert isinstance(categories, list), "Categories should be a list"
    assert all(isinstance(cat, str) for cat in categories), "All categories should be strings"

def test_extract_category_no_category(scraper):
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert scraper.extract_category(soup) == [], "Should return empty list if categories are missing"

def test_extract_content(scraper, article_soup):
    content = scraper.extract_content(article_soup)
    assert content is not None, "Content should be extracted"
    assert "The company convened its 5th AGM on 5th " in content, "Should contain specific content"  

def test_extract_content_no_content(scraper):
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert scraper.extract_content(soup) == "None", "Should return 'None' if content is missing"


def test_extract_published_date(scraper, article_soup, scraper_service, mocker):
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    mock_now = datetime(2025, 4, 28, 17, 0, 0, tzinfo=kathmandu_tz)  # 41 minutes after 16:19

    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = mock_now
    mocker.patch('nepali_news_scrapers.scrapers.sharesansar.sharesansar.datetime', mock_datetime_class)

    expected_date_time_str = "2025-04-28 16:19:00"
    published_date_time = scraper.extract_published_date(article_soup)

    assert published_date_time is not None, "extract_published_date returned None unexpectedly."
    assert published_date_time == expected_date_time_str, f"Expected '{expected_date_time_str}', got '{published_date_time}'"

    #split and check date time separately
    if published_date_time:
        date, time = published_date_time.split(" ")
        assert date == "2025-04-28", "Should extract the correct date"
        assert time == "16:19:00", "Should extract the correct time"

# Add a test specifically for the threshold logic if needed
def test_extract_published_date_threshold_skip(scraper, article_soup, scraper_service, mocker):
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')

    # Mock 'now' to be much later than the article date
    mock_now = datetime(2025, 4, 28, 18, 0, 0, tzinfo=kathmandu_tz) # 1 hour 41 mins after 16:19

    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = mock_now
    # Ensure patching the correct datetime instance the scraper uses
    mocker.patch('nepali_news_scrapers.scrapers.sharesansar.sharesansar.datetime', mock_datetime_class)

    published_date_time = scraper.extract_published_date(article_soup)

    assert published_date_time is None, "Should return None because article is older than threshold"
    scraper_service.log.info.assert_called_with(
        "Skipping Mon, Apr 28, 2025 4:19 PM as it is older than the threshold."
    )


def test_extract_published_date_threshold_pass(scraper, article_soup, scraper_service, mocker):
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')

    # Mock 'now' to be shortly after the article date (within threshold)
    mock_now = datetime(2025, 4, 28, 17, 0, 0, tzinfo=kathmandu_tz) # 41 mins after 16:19

    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = mock_now
    # Ensure patching the correct datetime instance the scraper uses
    mocker.patch('nepali_news_scrapers.scrapers.sharesansar.sharesansar.datetime', mock_datetime_class)

    expected_date_time_str = "2025-04-28 16:19:00"
    published_date_time = scraper.extract_published_date(article_soup)

    assert published_date_time is not None, "Should not return None as article is within threshold"
    assert published_date_time == expected_date_time_str




def test_extract_published_date_missing(scraper, scraper_service):
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    published_date_time = scraper.extract_published_date(soup)
    assert published_date_time is None, "Should return None if date container is missing"
    scraper_service.log.error.assert_called_with("Date and time container not found.")

def test_extract_published_date_invalid_format(scraper, scraper_service):
    soup = BeautifulSoup("<html><h5>Invalid Date</h5></html>", "html.parser")
    published_date_time = scraper.extract_published_date(soup)
    assert published_date_time is None, "Should return None if date format is invalid"
    scraper_service.log.error.assert_called_with("Date pattern not matched.")



# helper function to extract expected URLs from listings HTML
def extract_expected_hrefs(html, scraper):
    soup = BeautifulSoup(html, 'html.parser')
    containers = soup.find_all("div", class_="featured-news-list margin-bottom-15")
    unique_links = set()
    pattern = r'<a\s+[^>]*href="(https?://[^"]*newsdetail[^"]*)"'
    for container in containers:
        links = re.findall(pattern, str(container))
        unique_links.update(links)
    return unique_links

#test get_details with real HTML
def test_get_details_real_html(scraper, scraper_service, article_soup, mocker):
    url = "https://www.sharesansar.com/newsdetail/sample-article"
    scraper_service.make_get_request.return_value = str(article_soup)
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    test_datetime = datetime # Keep a reference

    # Adjust mock_now to be *after* the article date but within the threshold
    mock_now = test_datetime(2025, 4, 28, 17, 0, 0, tzinfo=kathmandu_tz) # 41 mins after article time

    mock_datetime_class = MagicMock(wraps=test_datetime)
    mock_datetime_class.now.return_value = mock_now

    # *** APPLY THE CORRECT PATCH TARGET ***
    mocker.patch('nepali_news_scrapers.scrapers.sharesansar.sharesansar.datetime', mock_datetime_class)

    scraper.get_details(url)

    scraper_service.save_json.assert_called_once()
    args, _ = scraper_service.save_json.call_args
    saved_data = args[0]
    assert saved_data["url"] == url, "URL should match"
    assert saved_data["category"] == ["Latest", "NEPSE News"], "Categories should match"  
    assert saved_data["title"] == "Bonus Share of Green Ventures Limited Listed in NEPSE", "Title should match" 
    assert saved_data["author"] == "-ShareSansar", "Author should match" 
    assert "31,25,000 unit bonus shares" in saved_data["content"], "Content should contain specific text" 
    assert saved_data["published_date"] == "2025-04-28", "Date should match" 
    assert saved_data["published_time"] == "16:19:00", "Time should match" 


#test get_page_listings with real HTML
def test_get_page_listings_success(scraper, scraper_service, listings_soup, mocker):
    listing_url = "https://www.sharesansar.com/category/exclusive"
    scraper_service.make_get_request.return_value = str(listings_soup)
    expected_hrefs = extract_expected_hrefs(str(listings_soup), scraper)
    mock_get_details = mocker.patch.object(scraper, 'get_details')
    
    scraper.extract_articles(listing_url)
    for href in expected_hrefs:
        mock_get_details.assert_any_call(href)
    assert mock_get_details.call_count == len(expected_hrefs), "Should call get_details for each article URL"

#test get_page_listings with no articles
def test_get_page_listings_no_articles(scraper, scraper_service, mocker):
    listing_url = "https://www.sharesansar.com/category/exclusive"
    no_articles_html = "<html><body></body></html>"
    scraper_service.make_get_request.return_value = no_articles_html
    mock_get_details = mocker.patch.object(scraper, 'get_details')
    
    scraper.extract_articles(listing_url)
    mock_get_details.assert_not_called(), "get_details should not be called when no articles are found"
