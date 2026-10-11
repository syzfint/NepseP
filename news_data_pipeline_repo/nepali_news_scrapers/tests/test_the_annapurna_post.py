import pytest
import re
from unittest.mock import Mock,MagicMock
import pytz
from bs4 import BeautifulSoup
from datetime import datetime,timedelta
from nepali_news_scrapers.scrapers.the_annapurna_post.the_annapurna_post import TheAnnapurnaPostScraper
from nepali_news_scrapers.services.scraper_service import ScraperService
from .fixtures import scraper_service, annapurna_article_html,annapurna_page_listings


#annapurna post specific fixtures

@pytest.fixture
def scraper(scraper_service):
    return TheAnnapurnaPostScraper(scraper_service)

@pytest.fixture
def article_soup(annapurna_article_html):
    try:
        return BeautifulSoup(annapurna_article_html, 'lxml')
    except ImportError:
        return BeautifulSoup(annapurna_article_html, 'html.parser')

@pytest.fixture
def listings_soup(annapurna_page_listings):
    try:
        return BeautifulSoup(annapurna_page_listings, 'lxml')
    except ImportError:
        return BeautifulSoup(annapurna_page_listings, 'html.parser')



#test url construction
def test_make_request_url(scraper):
    result = scraper.make_request_url("/category/latest-news/")
    assert result == "https://annapurnapost.com/category/latest-news/", "Should construct full URL correctly"



#test for site availability
def test_annapurna_site_down(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    content = scraper_service.make_get_request("https://annapurnapost.com")
    assert content is None, "Should return None when site is down"

def test_annapurna_site_running(scraper, scraper_service):
    scraper_service.make_get_request.return_value = "<html><body>Annapurna Post</body></html>"
    content = scraper_service.make_get_request("https://annapurnapost.com")
    assert content is not None, "Should return content when site is running"


#test for page listings with real html
def test_get_page_listings(scraper, scraper_service, mocker, annapurna_page_listings):
    listing_url = "https://annapurnapost.com/category/latest-news/"
    scraper_service.make_get_request.return_value = annapurna_page_listings
    mock_get_details = mocker.patch.object(scraper, 'get_page_details')

    scraper.get_page_listings(listing_url)

    # Extract expected links from the category HTML
    soup = BeautifulSoup(annapurna_page_listings, 'html.parser')
    first_story_link = soup.find('h3', class_='card__title')
    expected_links = set()
    if first_story_link:
        expected_links.add(scraper.make_request_url(first_story_link.find('a')['href']))
    grid_cards = soup.find_all("div", class_="grid__card")
    for card in grid_cards:
        anchors = card.find_all("a")
        for a in anchors:
            href = a.get("href")
            if href and "category" not in href:
                expected_links.add(scraper.make_request_url(href))

    #verify that get_page_details was called for each unique link
    for link in expected_links:
        mock_get_details.assert_any_call(link)
    assert scraper.unique_links == expected_links, "Should collect all unique article links"


#tests for title
def test_get_title(scraper, article_soup):
    title = scraper.get_title(article_soup)
    assert title == "प्रतिनिधिसभाको बैठक सुरू", "Should extract the correct title"

def test_get_title_no_title(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    title = scraper.get_title(soup)
    assert title == "", "Should return empty string if title not found"




#tests for author

def test_get_author(scraper, article_soup):
    author = scraper.get_author(article_soup)
    assert author == "अन्नपूर्ण", "Should extract the correct author"

def test_get_author_no_author(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    author = scraper.get_author(soup)
    assert author == "", "Should return empty string if author not found"

#tests for category

def test_get_category(scraper, article_soup):
    category = scraper.get_category(article_soup)
    assert category == "politics", "Should extract the correct category"

def test_get_category_no_category(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    category = scraper.get_category(soup)
    assert category is None, "Should return None if category not found"

def test_get_category_no_anchor(scraper):
    html = '<div class="card__category"></div>'
    soup = BeautifulSoup(html, 'html.parser')
    category = scraper.get_category(soup)
    assert category is None, "Should return None if anchor tag is missing"

def test_get_category_no_href(scraper):
    html = '<div class="card__category"><a>Link</a></div>'
    soup = BeautifulSoup(html, 'html.parser')
    category = scraper.get_category(soup)
    assert category is None, "Should return None if href is missing"

# test for get_content
def test_get_content(scraper, article_soup):
    content = scraper.get_content(article_soup)
    assert "बैठकले भन्सार विधेयक पारित गर्ने कार्यसूची छ" in content, "Should contain specific content"

def test_get_content_no_content(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    content = scraper.get_content(soup)
    assert content == "", "Should return empty string if content not found"



#tests for datetime split logic
def test_get_date_time(scraper, article_soup):
    date_part, time_part = scraper.get_date_time(article_soup, "test_url")
    assert date_part == "वैशाख १६, २०८२ मंगलबार", "Should extract correct date part"
    assert time_part == "११:८:५२", "Should extract correct time part"

def test_get_date_time_no_date(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    date_part, time_part = scraper.get_date_time(soup, "test_url")
    assert date_part == "", "Should return empty string if date not found"
    assert time_part == "", "Should return empty string if time not found"



#test for article skip(older article) or process(recent article)
def test_get_page_details_within_threshold(scraper, scraper_service, mocker, annapurna_article_html):
    url = "https://annapurnapost.com/newsstory/12345"
    scraper_service.make_get_request.return_value = annapurna_article_html

    # mock Nepali to English date conversion for "वैशाख १६, २०८२" -> 2025-04-29
    mocker.patch(
        'nepali_news_scrapers.scrapers.the_annapurna_post.the_annapurna_post.converter.nepali_to_english',
        return_value=(2025, 4, 29)
    )

    # Mock convert_nepali_to_english for Nepali digits
    scraper_service.convert_nepali_to_english.side_effect = lambda x: {
        '१६': '16',
        '२०८२': '2082',
        '११:८:५२': '11:08:52'
    }[x]

    #set current time to 2025-04-29 11:30:00 (21 minutes later, within 1 hour)
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    current_time = kathmandu_tz.localize(datetime(2025, 4, 29, 11, 30, 0))

    scraper.get_page_details(url, current_time=current_time)

    # Verify that save_json was called
    assert scraper_service.save_json.call_count == 1, "Should process article within threshold"
    args, _ = scraper_service.save_json.call_args
    saved_data = args[0]
    assert saved_data["url"] == url, "URL should match"
    assert saved_data["title"] == "प्रतिनिधिसभाको बैठक सुरू", "Title should be extracted"
    assert saved_data["published_date"] == "2025-04-29", "Published date should match"
    assert saved_data["published_time"] == "11:08:52", "Published time should match"


# Test for article outside threshold
def test_get_page_details_outside_threshold(scraper, scraper_service, mocker, annapurna_article_html):
    url = "https://annapurnapost.com/newsstory/12345"
    scraper_service.make_get_request.return_value = annapurna_article_html

    # Mock Nepali to English date conversion for "वैशाख १६, २०८२" -> 2025-04-29
    mocker.patch(
        'nepali_news_scrapers.scrapers.the_annapurna_post.the_annapurna_post.converter.nepali_to_english',
        return_value=(2025, 4, 29)
    )

    # Mock convert_nepali_to_english for Nepali digits
    scraper_service.convert_nepali_to_english.side_effect = lambda x: {
        '१६': '16',
        '२०८२': '2082',
        '११:८:५२': '11:08:52'
    }[x]

    # Set current time to 2025-04-29 12:30:00 (1 hour 21 minutes later, outside threshold)
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    current_time = kathmandu_tz.localize(datetime(2025, 4, 29, 12, 30, 0))

    scraper.get_page_details(url, current_time=current_time)

    # Verify that save_json was not called
    assert scraper_service.save_json.call_count == 0, "Should skip article outside threshold"

# test for invalid date format
def test_get_page_details_invalid_date(scraper, scraper_service, mocker, annapurna_article_html):
    url = "https://annapurnapost.com/newsstory/12345"
    soup = BeautifulSoup(annapurna_article_html, 'html.parser')
    date_container = soup.find('p', class_='date')
    if date_container:
        date_container.string = "Invalid Date Format"
    modified_html = str(soup)
    scraper_service.make_get_request.return_value = modified_html

    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    current_time = kathmandu_tz.localize(datetime(2025, 4, 29, 11, 30, 0))
    scraper.get_page_details(url, current_time=current_time)

    assert scraper_service.save_json.call_count == 0, "Should not save article with invalid date"



def test_get_page_details_invalid_month(scraper, scraper_service, mocker, annapurna_article_html):
    url = "https://annapurnapost.com/newsstory/12345"
    soup = BeautifulSoup(annapurna_article_html, 'html.parser')
    date_container = soup.find('p', class_='date')
    if date_container:
        date_container.string = "रहउह १६, २०८२ मंगलबार ११:८:५२"  # Invalid month
    modified_html = str(soup)
    scraper_service.make_get_request.return_value = modified_html

    scraper_service.convert_nepali_to_english.side_effect = lambda x: {
        '१६': '16',
        '२०८२': '2082',
        '११:८:५२': '11:08:52'
    }[x]

    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    current_time = kathmandu_tz.localize(datetime(2025, 4, 29, 11, 30, 0))
    mock_log = mocker.patch.object(scraper_service.log, 'error')

    scraper.get_page_details(url, current_time=current_time)

    assert scraper_service.save_json.call_count == 0, "Should not save article with invalid month"
    mock_log.assert_called_with(f"Error parsing date or time for URL {url}: Invalid Nepali month: रहउह")