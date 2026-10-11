import pytest
from unittest.mock import Mock
from bs4 import BeautifulSoup
from datetime import datetime
from pytest_mock import mocker
import pytz
from unittest.mock import MagicMock
from nepali_news_scrapers.scrapers.mero_lagani.mero_lagani import MeroLaganiScraper
from nepali_news_scrapers.services.scraper_service import ScraperService,ScraperError
from .fixtures import scraper_service,merolagani_article_html


@pytest.fixture
def scraper(scraper_service):
    return MeroLaganiScraper(scraper_service)


@pytest.fixture
def article_soup(merolagani_article_html):
    try:
        # Try lxml first
        return BeautifulSoup(merolagani_article_html, 'lxml')
    except ImportError:
        # Fallback to html.parser if lxml is not installed
        return BeautifulSoup(merolagani_article_html, 'html.parser')


def test_merolagani_site_down(scraper, scraper_service):
    # mock a failed requet to meroalgani
    scraper_service.make_get_request.return_value = None
    content = scraper_service.make_get_request("http://merolagani.com")
    assert content is None, "Should return None when the site is down"


def test_merolagani_site_running(scraper, scraper_service, merolagani_article_html):
    #mock  a successfull request to return real html 
    scraper_service.make_get_request.return_value = merolagani_article_html
    content = scraper_service.make_get_request("http://merolagani.com")
    assert content is not None, "Should return content when the site is running"
    assert "merolagani" in content.lower(), "Should contain expected site identifier from real HTML"


def test_make_request_url_np(scraper):
    result = scraper.make_request_url("/news","NP")
    assert result == "http://merolagani.com/news" ,"Should construct correct url for Np"

def test_make_request_url_eng(scraper):
    result = scraper.make_request_url("/news","ENG")
    assert result == "http://eng.merolagani.com/news" ,"Should construct correct url for ENG"




#test for api request
def test_fetch_news_list_success(scraper, scraper_service):
    sample_json = '''[
    {
        "newsID": 113908,
        "newsTitle": "लथालिंग, भताभुंग जे खालको आजको मुलुकको तस्बिर त्यहाँ देखिन्छः सञ्चारमन्त्री रुङ",
        "newsOverview": "<p style=\\"text-align: justify;\\"><span style=\\"font-size: 18px;\\">सञ्चार तथा सूचना प्रविधिमन्त्री पृथ्वीसुब्बा गुरुङले परिस्थिति बदलिएपछि कार्यशैली बदलिनुपर्ने बताएका छन्।</span></p>",
        "newsDateAD": "2025-04-27T11:30:00.133",
        "imagePath": "Uploads/Repository\\\\638813501912128400.jpg",
        "viewCount": 578,
        "featured": false
    }
]'''
    scraper_service.make_get_request.return_value = sample_json

    result = scraper.fetch_news_list("NP", "1")

    expected = [
        {
            "newsID": 113908,
            "newsTitle": "लथालिंग, भताभुंग जे खालको आजको मुलुकको तस्बिर त्यहाँ देखिन्छः सञ्चारमन्त्री रुङ",
            "newsOverview": "<p style=\"text-align: justify;\"><span style=\"font-size: 18px;\">सञ्चार तथा सूचना प्रविधिमन्त्री पृथ्वीसुब्बा गुरुङले परिस्थिति बदलिएपछि कार्यशैली बदलिनुपर्ने बताएका छन्।</span></p>",
            "newsDateAD": "2025-04-27T11:30:00.133",
            "imagePath": "Uploads/Repository\\638813501912128400.jpg",
            "viewCount": 578,
            "featured": False
        }
    ]

    assert result == expected, "Should parse JSON correctly"



def test_fetch_news_list_no_response(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    with pytest.raises(ScraperError, match="Failed to fetch news list"):
        scraper.fetch_news_list("ENG", "1")

def test_fetch_news_list_invalid_json(scraper, scraper_service):
    scraper_service.make_get_request.return_value = "invalid json"
    with pytest.raises(ScraperError, match="Invalid JSON response"):
        scraper.fetch_news_list("NP", "1")



def test_extract_title(scraper, article_soup):
    title = scraper.extract_title(article_soup)
    assert title is not None, "Should extract title from real HTML"
    assert title == "लथालिंग, भताभुंग जे खालको आजको मुलुकको तस्बिर त्यहाँ देखिन्छः सञ्चारमन्त्री गुरुङ", "Should extract correct title"

def test_extract_title_no_title(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    with pytest.raises(ScraperError, match="News title not found"):
        scraper.extract_title(soup)

def test_extract_source(scraper,article_soup):
    source = scraper.extract_source(article_soup)
    assert source == "Merolagani", "Should extract correct source"

def test_extract_source_no_source(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    with pytest.raises(ScraperError, match="News source not found"):
        scraper.extract_source(soup)
    
def test_extract_overview(scraper, article_soup):
    overview = scraper.extract_overview(article_soup)
    assert isinstance(overview, str), "Should return a string (empty or not) from real HTML"

def test_extract_overview_no_overview(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_overview(soup) == "", "Should return empty string if overview missing"

def test_extract_content(scraper,article_soup):
    content = scraper.extract_content(article_soup)
    assert content is not None, "Content should be extracted"
    assert "नेपाल चलचित्र संघको ५० औं वार्षिक" in content, "Should contain the specific content"

def test_extract_content_no_content(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    with pytest.raises(ScraperError,match="News content not found"):
        scraper.extract_content(soup)


def test_extract_category(scraper,article_soup):
    category = scraper.extract_category(article_soup)
    assert category is not None, "Should extract category from html"
    assert category == "Uncategorized", "Should extract correct category"

def test_extract_category_no_category(scraper):
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert scraper.extract_category(soup) == "Uncategorized", "Should return Uncategorized if missing"


def test_get_page_listing_skip_old_news(scraper, scraper_service, mocker):
    sample_json = '[{"newsID": "113908","newsDateAD": "2025-04-27T09:00:00"}]'
    scraper_service.make_get_request.return_value = sample_json
    mock_get_page_details = mocker.patch.object(scraper, 'get_page_details')

    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    mock_now = datetime(2025, 4, 27, 10, 30, 0, tzinfo=kathmandu_tz)
    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = mock_now
    mocker.patch('nepali_news_scrapers.scrapers.mero_lagani.mero_lagani.datetime', mock_datetime_class)

    scraper.get_page_listing("NP")
    mock_get_page_details.assert_not_called(), "Should not call get_page_details for old news"


def test_get_page_details_no_response(scraper, scraper_service):
    scraper_service.make_get_request.return_value = None
    with pytest.raises(ScraperError, match="Failed to fetch news details"):
        scraper.get_page_details("113643", "http://merolagani.com/NewsDetail.aspx?newsID=113643", "NP")


def test_parse_publication_date_invalid(scraper):
    with pytest.raises(ScraperError, match="Error parsing date"):
        scraper.parse_publication_date("invalid-date")


def test_extract_published_date_time(scraper, article_soup):
    date, time = scraper.extract_published_date_time(article_soup)
    assert date is not None, "Should extract date from real HTML"
    assert time is not None, "Should extract time from real HTML"
    assert date == "2025-04-27", "Should extract correct date"
    assert time == "11:30:00", "Should extract correct time"

def test_extract_published_date_time_invalid_format(scraper):
    html = '<span id="ctl00_ContentPlaceHolder1_newsDate">Invalid Date</span>'
    soup = BeautifulSoup(html, 'html.parser')
    with pytest.raises(ScraperError, match="Published date/time format invalid"):
        scraper.extract_published_date_time(soup)


#integration Test
def test_get_page_details_real_html(scraper, scraper_service, mocker, merolagani_article_html):
    url = "http://merolagani.com/NewsDetail.aspx?newsID=113643"
    scraper_service.make_get_request.return_value = merolagani_article_html

    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    mock_now = datetime(2025, 4, 27, 10, 0, 0, tzinfo=kathmandu_tz)
    mock_datetime_class = MagicMock(wraps=datetime)
    mock_datetime_class.now.return_value = mock_now
    mocker.patch('nepali_news_scrapers.scrapers.mero_lagani.mero_lagani.datetime', mock_datetime_class)

    scraper.get_page_details("113643", url, "NP")
    scraper_service.save_json.assert_called_once()

    args, _ = scraper_service.save_json.call_args
    saved_data = args[0]
    assert saved_data["url"] == url, "URL should match"
    assert "title" in saved_data, "Title should be present"
    assert "category" in saved_data, "Category should be present"
    assert "author" in saved_data, "Author should be present"
    assert "content" in saved_data, "Content should be present"
    assert "published_date" in saved_data, "Date should be present"
    assert "published_time" in saved_data, "Time should be present"

