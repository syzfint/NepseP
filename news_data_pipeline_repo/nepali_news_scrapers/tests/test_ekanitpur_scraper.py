import pytest
from unittest.mock import MagicMock, Mock
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from urllib.parse import urljoin
from nepali_news_scrapers.scrapers.ekantipur.ekanitpur import EkantipurScraper
from nepali_news_scrapers.services.scraper_service import ScraperService
from .fixtures import scraper_service, ekantipur_article_html,ekantipur_page_listings

#set up EkantipurScraper
@pytest.fixture 
def scraper(scraper_service):
    return EkantipurScraper(scraper_service)



#test the  URL construction
def test_make_request_url(scraper):
    result = scraper.make_request_url("/news/2025/test-news")
    assert result == "https://ekantipur.com/news/2025/test-news", "Should make full URL"

   #check if kantipur site is down  
def test_ekantipur_site_down(scraper, scraper_service):
    #mocking a failed get request to ekantipur site base url
    scraper_service.make_get_request.return_value = None
    soup = scraper.get_soup("https://ekantipur.com")
    assert soup is None, "Should return None if site is down"


def test_ekantipur_site_running(scraper, scraper_service):
    #mocking a successfull get request to ekantipur site base url
    scraper_service.make_get_request.return_value = "<html><body>Ekantipur Site</body></html>"
    soup = scraper.get_soup("https://ekantipur.com")
    assert soup is not None, "Should return a BeautifulSoup object if site is running"
    assert "Ekantipur Site" in str(soup), "Should confirm site content is retrieved"


#test title extraction
def test_extract_title(scraper):
    html = "<h1 class='eng-text-heading'>Test News Title</h1>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_title(soup) == "Test News Title", "Should extract title"

def test_extract_title_no_title(scraper):
    html = "<html></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_title(soup) == "Untitled", "Should return Untitled"

#test author extraction
def test_extract_author_info(scraper):
    html = """
    <section class="author-list">
        <p class="inter"><span>कान्तिपुर संवाददाता</span></p>
    </section>
    """
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_author(soup) == ["कान्तिपुर संवाददाता"], "Should find author from new selector"


def test_extract_published_date_json_ld(scraper):
    json_ld_html = """
    <script type="application/ld+json">
    {
        "@type": "NewsArticle",
        "datePublished": "2026-02-13 22:03:35"
    }
    </script>
    """
    soup = BeautifulSoup(json_ld_html, 'html.parser')
    result = scraper.extract_published_date(soup, "https://test.com")
    assert result == datetime(2026, 2, 13, 22, 3, 35)

def test_extract_author_no_author(scraper):
    html = "<html><body>No author here</body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_author(soup) == ["Unknown"], "Should return Unknown if no author found"


def test_extract_category(scraper):
    html = "<div class='category-name'>Politics</div>"
    soup = BeautifulSoup(html, 'html.parser')
    result = scraper.extract_category(soup)
    assert result == "Politics", "Should extract category from new selector"

def test_extract_category_no_category(scraper):
    html = "<html></html>"
    soup = BeautifulSoup(html, 'html.parser')
    result = scraper.extract_category(soup)
    assert result == "News"

def test_extract_content(scraper):
    html = """
    <section class="news-section-wrap-story">
        <p>संघीय संसद्को दुवै सदनको</p>
        <p>थप सामग्री यहाँ छ।</p>
    </section>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = scraper.extract_content(soup)
    assert result == "संघीय संसद्को दुवै सदनको\nथप सामग्री यहाँ छ।", "Should extract content from new selector"



def test_extract_content_no_content(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    result = scraper.extract_content(soup)
    assert result == "", "Should return empty string if no content is found with new selector"


def test_extract_published_date_json_ld(scraper):
    json_ld_html = """
    <script type="application/ld+json">
    {
        "@type": "NewsArticle",
        "datePublished": "2026-02-13 22:03:35"
    }
    </script>
    """
    soup = BeautifulSoup(json_ld_html, 'html.parser')
    result = scraper.extract_published_date(soup, "https://test.com")
    assert result == datetime(2026, 2, 13, 22, 3, 35)


def test_extract_published_data_invalid_format_html_fallback(scraper, scraper_service, mocker):
    html = "<div class='author-date'><span class='published-at'>प्रकाशित : वैशाख ९, २०८१</span></div>"
    soup = BeautifulSoup(html, 'html.parser')

    mocker.patch(
        'nepali_news_scrapers.services.scraper_service.ScraperService.convert_nepali_to_english',
        side_effect=["वैशाख 9, 2081", "00:00"] # Mock the conversion for date part and default time
    )
    mocker.patch(
        'nepali_news_scrapers.scrapers.ekantipur.ekanitpur.converter.nepali_to_english',
        return_value=(2024, 4, 21) # Mock Nepali to English date conversion
    )

    result = scraper.extract_published_date(soup, "test_url")
    assert result == datetime(2024, 4, 21, 0, 0), "Should return datetime with default 00:00 time when time is missing from HTML fallback"

def test_extract_published_date_invalid_month_html_fallback(scraper, scraper_service, mocker):
    html = "<div class='author-date'><span class='published-at'>प्रकाशित : बेसाक ९, २०८१ १०:३०</span></div>"
    soup = BeautifulSoup(html, 'html.parser')
    
    mocker.patch(
        'nepali_news_scrapers.services.scraper_service.ScraperService.convert_nepali_to_english', 
        side_effect=["Baisakh 9, 2081", "10:30"]
    )
    
    result = scraper.extract_published_date(soup, "test_url")
    assert result is None, "Should return None if Nepali month is invalid in HTML fallback"

def test_extract_missing_fields_no_json_ld(scraper, scraper_service, mocker):
    # This test HTML has no JSON-LD or specific selectors
    html = "<html><body>No data here</body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    
    mocker.patch('nepali_news_scrapers.scrapers.ekantipur.ekanitpur.converter.nepali_to_english', return_value=(2024, 1, 1)) # Dummy for HTML fallback
    mocker.patch('nepali_news_scrapers.services.scraper_service.ScraperService.convert_nepali_to_english', side_effect=["माघ 1, 2080", "10:00"]) # Dummy for HTML fallback


    assert scraper.extract_title(soup) == "Untitled"
    assert scraper.extract_author(soup) == ["Unknown"]
    assert scraper.extract_category(soup) == "News" # New default category
    assert scraper.extract_published_date(soup, "test_url") is None # No date container at all

def test_convert_nepali_date_to_english(scraper, scraper_service, mocker):
    mocker.patch(
        'nepali_news_scrapers.services.scraper_service.ScraperService.convert_nepali_to_english',
        side_effect=["वैशाख 7, 2081", "10:30"]
    )
    mocker.patch(
        'nepali_news_scrapers.scrapers.ekantipur.ekanitpur.converter.nepali_to_english',
        return_value=(2024, 4, 19)
    )
    # This test directly calls the internal helper function `convert_nepali_date_to_english`
    # and mocks its dependencies that come from ScraperService or nepali.date_converter
    date_result = scraper.convert_nepali_date_to_english("वैशाख 7, 2081", "10:30", "test_url")
    assert date_result == datetime(2024, 4, 19, 10, 30),"Should convert Nepali date to correct datetime"


def test_scrape_article(scraper, scraper_service, mocker, ekantipur_article_html):
    scraper_service.make_get_request.return_value = ekantipur_article_html

    
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')

    fake_now_time = datetime(2026, 2, 13, 22, 23, 35, tzinfo=kathmandu_tz) # 20 minutes difference

    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = fake_now_time
    mocker.patch('nepali_news_scrapers.scrapers.ekantipur.ekanitpur.datetime', mock_datetime_class)


    mocker.patch(
        'nepali_news_scrapers.services.scraper_service.ScraperService.convert_nepali_to_english',
        side_effect=["फागुन 1, 2082", "07:28"],
    )
    mocker.patch(
        'nepali_news_scrapers.scrapers.ekantipur.ekanitpur.converter.nepali_to_english',
        return_value=(2026, 2, 13)
    )
    test_url = "https://ekantipur.com/world/2026/02/13/tariq-rahman-set-to-be-new-bangladesh-pm-58-43.html"
    scraper.get_details(test_url)

    scraper_service.make_get_request.assert_called_once_with(
        test_url, scraper.headers
    )
    assert scraper_service.save_json.call_count == 1, "save_json should be called once"

    args, _ = scraper_service.save_json.call_args
    saved_data = args[0]

    assert saved_data["title"] == "बंगलादेशको नयाँ प्रधानमन्त्रीमा तारिक रहमान आउने निश्चित" 
    assert saved_data["category"] == "विश्व" # From div.category-name
    assert saved_data["author"] == ["रासस"] # From author-date a tag
    assert saved_data["published_date"] == "2026-02-13" # From JSON-LD
    assert saved_data["published_time"] == "22:03:35" # From JSON-LD
    assert "बंगलादेश नेसनलिस्ट पार्टी (बीएनपी)" in saved_data["content"]
    assert saved_data["url"] == test_url



def test_extract_missing_fields(scraper, scraper_service):
    html = "<html><body>No data here</body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_title(soup) == "Untitled"
    assert scraper.extract_author(soup) == ["Unknown"]
    assert scraper.extract_category(soup) == "News"
    assert scraper.extract_published_date(soup, "test_url") is None
   

# tst date conversion
def test_date_conversion(scraper, scraper_service, mocker):
    html = "<span class='published-at'>प्रकाशित : वैशाख ७, २०८१ १०:३०</span>"
    soup = BeautifulSoup(html, 'html.parser')

    # mocks Nepali to English digit conversion (static method)
    mock_convert_nepali = mocker.patch(
        'nepali_news_scrapers.services.scraper_service.ScraperService.convert_nepali_to_english', #path to replace 
        side_effect=["वैशाख 7, 2081", "10:30"] #returnigng value of the mock when it is called first time the first element , and 2nd time returns 2nd element of list
    )

    # Mocks the converter.mepali_to_english function in the nepali library
    mock_nepali_to_english = mocker.patch(
        'nepali_news_scrapers.scrapers.ekantipur.ekanitpur.converter.nepali_to_english',
        return_value=(2024, 4, 19)  #returns this वैशाख 7, 2081 to --> 2024-04-19 everytime
    )

    # Execute extraction from the url
    date_result = scraper.extract_published_date(soup, "test_url")

    # Should return correct datetime
    assert date_result == datetime(2024, 4, 19, 10, 30),"Should convert Nepali date to correct datetime"

    # Verify service conversions
    assert mock_convert_nepali.call_count == 2,"Should convert both date and time parts"
    mock_convert_nepali.assert_any_call("वैशाख ७, २०८१")
     # Checks if *one* of the calls made to the fake `convert_nepali_to_english` function was with the argument "वैशाख ७, २०८१" (the original Nepali date part).

    mock_convert_nepali.assert_any_call("१०:३०")

    # Verify date converter received correct numeric values
    mock_nepali_to_english.assert_called_once_with(2081, 1, 7)  # वैशाख (1), 7, 2081


#integration test for the scraper


#helper function to extract expected hrefs from html
def extract_expected_hrefs(html):
    soup = BeautifulSoup(html, 'html.parser')
    hrefs = set()
    # Mimic the scraper's extract_articles logic:
    search_container = soup.find("div", class_="search-content-wrapper")
    blocks = soup.find("div", class_="blocksLayout")
    
    target_containers = []
    if search_container:
        target_containers.append(search_container)
    if blocks:
        target_containers.append(blocks)
    if not target_containers: # Fallback to soup if no specific containers
        target_containers.append(soup)

    for container in target_containers:
        items = container.find_all(["article", "div"], class_=lambda x: x == "news-list" or x is None)
        for item in items:
            for a in item.find_all("a"):
                href = a.get("href")
                # IMPORTANT: Replicate the scraper's filtering here!
                if href and "/author" not in href and "/2026/" in href:
                    full_url = urljoin("https://ekantipur.com", href)
                    hrefs.add(full_url)
    return hrefs




#test case for the page listings retrieval
def test_page_listings_success(scraper,scraper_service,mocker,ekantipur_page_listings):
    listing_url = "https://ekantipur.com/search/2025/?txtSearch=&year=2025&date-from=2025-04-24&date-to=2025-04-24"
    scraper_service.make_get_request.return_value = ekantipur_page_listings
    expected_hrefs = extract_expected_hrefs(ekantipur_page_listings)

    mock_get_details = mocker.patch.object(scraper, 'get_details', return_value=None)

    # Call the method under test
    scraper.get_page_listings(listing_url)

    # Verify that get_details was called with each expected URL
    for href in expected_hrefs:
        mock_get_details.assert_any_call(href)
    
    # Verify that unique_links contains the expected URLs
    assert scraper.unique_links == expected_hrefs, "unique_links should contain all expected article URLs"



def test_get_page_listings_no_articles(scraper, scraper_service, mocker):
    listing_url = "https://ekantipur.com/search/2025/?txtSearch=&year=2025&date-from=2025-04-24&date-to=2025-04-24"
    no_articles_html = "<html><body><div class='blocksLayout'></div></body></html>"
    scraper_service.make_get_request.return_value = no_articles_html

    # Mock get_details to ensure it's not called
    mock_get_details = mocker.patch.object(scraper, 'get_details', return_value=None)

    # Call the method under test
    scraper.get_page_listings(listing_url)

    # Verify that unique_links remains empty
    assert scraper.unique_links == set(), "unique_links should remain empty when no articles are present"
    
    # Verify that get_details was not called
    mock_get_details.assert_not_called(), "get_details should not be called when no articles are found"