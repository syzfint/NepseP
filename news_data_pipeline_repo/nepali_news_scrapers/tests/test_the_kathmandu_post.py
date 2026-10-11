import pytest
from unittest.mock import Mock,MagicMock
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
import re
from nepali_news_scrapers.scrapers.the_kathmandu_post.the_kathmandu_post import KathmanduPostScraper
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperError
from .fixtures import scraper_service,kathmandu_post_article_html,kathmandu_post_page_listings,mock_kathmandu_datetime


@pytest.fixture
def scraper(scraper_service):
    return KathmanduPostScraper(scraper_service)


@pytest.fixture
def article_soup(kathmandu_post_article_html):
    return BeautifulSoup(kathmandu_post_article_html, 'html.parser')

@pytest.fixture
def listings_soup(kathmandu_post_page_listings):
    return BeautifulSoup(kathmandu_post_page_listings, 'html.parser')



def test_site_running(scraper, scraper_service,kathmandu_post_page_listings):
    scraper_service.make_get_request.return_value = kathmandu_post_page_listings
    result = scraper.service.make_get_request("https://kathmandupost.com/latest")
    assert result is not None
    scraper_service.log.error.assert_not_called()



def test_site_down(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    with pytest.raises(ScraperError):
        scraper.get_page_listings("https://kathmandupost.com/latest")
    
    scraper_service.log.error.assert_called_with(
        "Failed to retrieve page listings."
    )


def test_make_request_url(scraper):
    url = scraper.make_request_url("/latest")
    assert url == "https://kathmandupost.com/latest"



#test to check if scraper extracts href-links from listing page
def test_extract_links_real_html(scraper, listings_soup):
    links = scraper.extract_links(listings_soup)
    assert len(links) > 0, "Should extract at least one link"


#category test
def test_extract_category(scraper, article_soup):
    category = scraper.extract_category(article_soup)
    assert category == "Sudurpaschim Province", "Should extract the correct category"

def test_extract_category_missing(scraper):
    html = '<html></html>'
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_category(soup) is None, "Should return None when category elements are missing"


#title test
def test_extract_title(scraper, article_soup):
    title = scraper.extract_title(article_soup)
    assert title == "Nepal’s shamans join campaign against practice of banishing menstruating women to hut", "Should extract the exact title"

def test_extract_title_missing(scraper):
    html = '<html></html>'
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_title(soup) is None, "Should return None when title is missing"


#date-time extractiont et
def test_extract_date_time(scraper, article_soup):
    dt_obj = scraper.extract_date_time(article_soup)
    containers = article_soup.find_all("div", {"class": "updated-time"})
    if containers:
        assert dt_obj is not None, "Should extract datetime "
        assert isinstance(dt_obj, datetime), "Should return a datetime object"
        assert dt_obj.tzinfo is not None, "Should be timezone-aware"
    else:
        assert dt_obj is None, "Should return None if no date-time containers "

def test_extract_date_time_missing(scraper):
    html = '<html></html>'
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_date_time(soup) is None, "Should return None when date-time elements are missing"


#author testing

def test_extract_author(scraper, article_soup):
    author = scraper.extract_author(article_soup)
    assert author == "Menuka Dhungana", "Should extract the author correctly"

def test_extract_author_missing(scraper):
    html = '<html></html>'
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_author(soup) is None, "Should return None when author is missing"

#test for content 
def test_extract_content(scraper, article_soup):
    content = scraper.extract_content(article_soup)
    assert "Religious leaders and shamans" in content, "Shuld contain the specific text"

def test_extract_content_missing(scraper):
    html = '<html></html>'
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_content(soup) is None, "Should return None when content is missing"



#test to check if all the details are corectly extracted from article
def test_get_page_details(scraper, scraper_service, mocker, 
                         kathmandu_post_article_html, mock_kathmandu_datetime):
    url = "https://kathmandupost.com/test-article"
    scraper_service.make_get_request.return_value = kathmandu_post_article_html
    
    # Mock HTML parsing
    mocker.patch.object(
        BeautifulSoup, 
        'find',
        side_effect=lambda *args, **kwargs: MagicMock(text="Mocked Content")
    )
    
    result = scraper.get_page_details(url)
    
    assert result is True
    scraper_service.save_json.assert_called_once()
    
    saved_data = scraper_service.save_json.call_args[0][0]
    assert saved_data["url"] == url
    assert "published_date" in saved_data
    assert "published_time" in saved_data



def test_get_page_listings(scraper, scraper_service, mocker, listings_soup):
    page_url = "https://kathmandupost.com/latest"
    scraper_service.make_get_request.return_value = str(listings_soup)
    mock_get_page_details = mocker.patch.object(scraper, 'get_page_details')

    scraper.get_page_listings(page_url)
    assert mock_get_page_details.call_count > 0, "Should call get_page_details for each extracted link"


def test_get_page_listings_no_links(scraper, scraper_service):
    page_url = "https://kathmandupost.com/latest"
    html = '<html><body></body></html>'
    scraper_service.make_get_request.return_value = html
    scraper.get_page_listings(page_url)
    scraper_service.log.info.assert_any_call("No new links found.")