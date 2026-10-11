import pytest
from unittest.mock import Mock
from bs4 import BeautifulSoup
from datetime import datetime
from pytest_mock import mocker
import pytz
from unittest.mock import MagicMock
from nepali_news_scrapers.scrapers.setopati.setopati import SetoPatiScraper
from nepali_news_scrapers.services.scraper_service import ScraperService
from .fixtures import scraper_service,setopati_article_html,setopati_page_listings





# Set up SetoPatiScraper
@pytest.fixture
def scraper(scraper_service):
    # Create a new scraper instance with the mocked scraper_service
    return SetoPatiScraper(scraper_service)

@pytest.fixture
def article_soup(setopati_article_html):
    """Creates a BeautifulSoup object from the setopati_article_html fixture."""
   
    try:
        # Try lxml first
        return BeautifulSoup(setopati_article_html, 'lxml')
    except ImportError:
        # Fallback to html.parser if lxml is not installed
        return BeautifulSoup(setopati_article_html, 'html.parser')


def test_make_request_url(scraper):
    # Test if the scraper builds the correct URL
    result = scraper.make_request_url("/politics/1232")
    assert result == "https://www.setopati.com/politics/1232", "Should make full URL"


#test setopati site availability
def test_setopati_site_down(scraper,scraper_service):
    #mock a failed request to setpati 
    scraper_service.make_get_request.return_value = None
    content = scraper_service.make_get_request("https://www.setopati.com")
    assert content is None, "Should return None if site is down"
    

def test_setopati_site_running(scraper,scraper_service):
    #mock a failed request to setpati 
    scraper_service.make_get_request.return_value = "<html><body>Setopati Site</body></html>"
    content = scraper_service.make_get_request("https://www.setopati.com")
    assert content is not None, "Should return content if site is up and running"
    


# testing valid article link ending with digits i.e newsId
def test_is_valid_article_link(scraper):
    assert scraper.is_valid_article_link("/political/23123") is True, "Should be valid as it ends with digits"

    assert scraper.is_valid_article_link("/business/131423") is True, "Should be valid as it ends with digits"

    assert scraper.is_valid_article_link("/something")is False, "Should be invalid not ending with digits"

    assert scraper.is_valid_article_link("/photo-detail/123")is False, "Should be invalid contains photo details"

    assert scraper.is_valid_article_link("/author/setpati")is False, "Should be invalid contians author" 
    




def test_extract_title(scraper,article_soup):
    expected_title="ट्राफिक प्रहरीले कुटपिट गरेको अर्को भिडिओ पनि भाइरल, घटनाबारे बुझ्दै प्रहरी"
    assert scraper.extract_title(article_soup) == expected_title  ,"Should extract the correct title "

def test_extract_title_no_title(scraper):

    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_title(soup) == "N/A", "Should return N/A if title tag is not found"


def test_extract_author(scraper,article_soup):
    expected_author="सेतोपाटी संवाददाता"
    assert scraper.extract_author(article_soup) == expected_author , "Should extract the correct author from fixture"

def test_extract_author_no_author(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_author(soup) == "N/A", "Should return N/A if author elements are not found"

def test_extract_content(scraper, article_soup):
    content = scraper.extract_content(article_soup)
    assert content is not None, "Content should be extracted"
    assert "युवकले किन यस्तो गरेको भनेर प्रश्न गरेको देखिन्छ।" in content,"Should contain specific content"




def test_extract_content_no_content(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_content(soup) == "", "Should return empty string if content elements are not found"


def test_extract_category(scraper):
    url = "https://www.setopati.com/politics/32321"
    assert scraper.extract_category(url) == "politics", "Should extract category from URL"

def test_extract_category_no_category(scraper):
    url = "https://www.setopati.com/12345"
    assert scraper.extract_category(url) is None, "Should return None if category missing"


def test_extract_published_date(scraper, article_soup, scraper_service,mocker):    
    scraper_service.convert_nepali_to_english.side_effect =['12:36', '2082', '12']
    # Mock the nepali date converter
    mocker.patch('nepali_news_scrapers.scrapers.setopati.setopati.converter.nepali_to_english', return_value=(2024, 4, 25))

    expected_date = "2024-04-25"
    expected_time = "12:36:00"

    extracted_date, extracted_time = scraper.extract_published_date(article_soup)

    assert extracted_date == expected_date, "Should extract the correct date from fixture HTML"
    assert extracted_time == expected_time, "Should extract the correct time from fixture HTML"


def test_extract_published_date_missing(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    date, time = scraper.extract_published_date(soup)
    assert date is None, "Should return None if date container missing"
    assert time is None, "Should return None if time missing"


def test_extract_published_date_invalid_format(scraper, scraper_service):
    html = '<div class="published-date col-md-6">प्रकाशित मिति: बैशाख १२, २०८२</div>'  # No time
    soup = BeautifulSoup(html, 'html.parser')
    date, time = scraper.extract_published_date(soup)
    assert date is None, "Should return None if time missing"
    assert time is None, "Should return None if time missing"

#invalid month mapping
def test_extract_published_date_invalid_month(scraper, scraper_service,article_soup):
    #access the nepali_months dict from scraper
    nepali_months= scraper.nepali_months

    #potential demo invalid months
    invalid_months= ["बैसाख",     
          "वैशख"]

    invalid_months = [month for month in invalid_months if month not in nepali_months]

    if not invalid_months:
        raise ValueError("No invalid months found for testing")


    for invalid_month in invalid_months:
        #creting a copy of article_soup to avoid modifying the original fixture
        soup = BeautifulSoup(str(article_soup), 'lxml')

        #find  published date container and replace its text with an invalid month
        date_container = soup.find("div", class_="published-date col-md-6")
        if date_container:
            date_container.string = f"प्रकाशित मिति: {invalid_month} १२, २०८२ १२:३६"
        else:
            raise ValueError("Published date container not found in article_soup")

        #mock convert_nepali_to_english to handle the date and time parts
        scraper_service.convert_nepali_to_english.side_effect = [f"{invalid_month} 12, 2082", "12:36"]

        # Call the method under test
        date, time = scraper.extract_published_date(soup)

        #asert that both date and time are None due to invalid month
        assert date is None, f"Should return None for date with invalid month '{invalid_month}'"
        assert time is None, f"Should return None for time with invalid month '{invalid_month}'"

def extract_expected_hrefs(html, scraper):
    soup = BeautifulSoup(html, 'html.parser')
    href_links = []
    # Get featured article links
    banner_article_links = soup.find_all("div", class_="big-feature col-md-12")
    for item in banner_article_links:
        anchors = item.find_all("a")
        href_links.extend(a['href'] for a in anchors if 'href' in a.attrs and scraper.is_valid_article_link(a['href']))
    # Get other news links
    div_tags = soup.find_all('div', class_='items')
    href_links.extend(div.find('a')['href'] for div in div_tags if div.find('a') and 'href' in div.find('a').attrs and scraper.is_valid_article_link(div.find('a')['href']))
    
    # Normalize URLs: use absolute URLs directly, convert relative URLs
    normalized_links = set()
    for link in href_links:
        if link.startswith('https://'):
            normalized_links.add(link)
        else:
            normalized_links.add(scraper.make_request_url(link))
    return normalized_links



def test_get_page_details_real_html(scraper, scraper_service, mocker, setopati_article_html):
    url = "https://www.setopati.com/social/357088"
    scraper_service.make_get_request.return_value = setopati_article_html
    scraper_service.convert_nepali_to_english.side_effect = ['12:36', '2082', '12']
    mocker.patch(
        'nepali_news_scrapers.scrapers.setopati.setopati.converter.nepali_to_english',
        return_value=(2024, 4, 25)
    )
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    mock_now = datetime(2024, 4, 25, 13, 0, 0, tzinfo=kathmandu_tz)
    
    # Mock the datetime module instead of datetime.now
    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = mock_now
    mocker.patch('nepali_news_scrapers.scrapers.setopati.setopati.datetime', mock_datetime_class)

    scraper.get_page_details(url)
    scraper_service.save_json.assert_called_once()
    args, _ = scraper_service.save_json.call_args
    saved_data = args[0]
    assert saved_data["url"] == url, "URL should match"
    assert saved_data["category"] == "social", "Category should match"
    assert saved_data["title"] == "ट्राफिक प्रहरीले कुटपिट गरेको अर्को भिडिओ पनि भाइरल, घटनाबारे बुझ्दै प्रहरी", "Title should match"
    assert saved_data["author"] == "सेतोपाटी संवाददाता", "Author should match"
    assert saved_data["content"] != "", "Content should be present"
    assert "युवकले किन यस्तो गरेको भनेर प्रश्न गरेको देखिन्छ।" in saved_data["content"], "Content should contain specific text"
    assert saved_data["published_date"] == "2024-04-25", "Date should match"
    assert saved_data["published_time"] == "12:36:00", "Time should match"



def test_get_page_listings_success(scraper, scraper_service, mocker, setopati_page_listings):
    listing_url = "https://www.setopati.com/search?&page="
    scraper_service.make_get_request.return_value = setopati_page_listings
    expected_hrefs = extract_expected_hrefs(setopati_page_listings, scraper)
    mock_get_page_details = mocker.patch.object(scraper, 'get_page_details')

    scraper.get_page_listings(listing_url)
    for href in expected_hrefs:
        mock_get_page_details.assert_any_call(href)
    assert scraper.unique_links == expected_hrefs, "unique_links should contain all expected article URLs"

#test get_page_listings with no articles
def test_get_page_listings_no_articles(scraper, scraper_service, mocker):
    listing_url = "https://www.setopati.com/search?&page="
    no_articles_html = "<html><body></body></html>"
    scraper_service.make_get_request.return_value = no_articles_html
    mock_get_page_details = mocker.patch.object(scraper, 'get_page_details')

    scraper.get_page_listings(listing_url)
    assert scraper.unique_links == set(), "unique_links should remain empty when no articles are present"
    mock_get_page_details.assert_not_called(), "get_page_details should not be called when no articles are found"
