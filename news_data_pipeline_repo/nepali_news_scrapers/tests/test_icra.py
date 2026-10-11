import pytest
from unittest.mock import Mock, MagicMock
from bs4 import BeautifulSoup
import requests
from io import BytesIO
from nepali_news_scrapers.scrapers.icra_scraper.icra_scraper import USER_AGENTS, IcraScraper
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService
from .fixtures import scraper_service, icra_listings_html, icra_sample_pdf
import pdfplumber
from unittest.mock import patch

@pytest.fixture
def scraper(scraper_service):
    scraper_service.db_service= Mock()
    return IcraScraper(scraper_service)

@pytest.fixture
def listings_soup(icra_listings_html):
    try:
        return BeautifulSoup(icra_listings_html, 'lxml')
    except ImportError:
        return BeautifulSoup(icra_listings_html, 'html.parser')



def test_make_request_url(scraper):
    result = scraper.make_request_url("page/1/")
    assert result == "https://www.icranepal.com/releases/page/1/", "Should construct a complete URL"

def test_get_random_user_agent(scraper):
    user_agent = scraper.get_random_user_agent()
    assert user_agent in USER_AGENTS, "Should return a valid user agent"


def test_extract_pdf_links(scraper, icra_listings_html):

    scraper.service.make_get_request.return_value = icra_listings_html
    pdf_links = scraper.extract_pdf_links("dummy_url")
    
    
    assert len(pdf_links) > 5
    
    #verifying the first link in the icra_listings.html
    assert pdf_links[0]["title"] == "Himalayan Capital Limited: Rating reaffirmed"
    assert pdf_links[0]["url"] == "https://www.icranepal.com/wp-content/uploads/2025/04/A.1101-Himalayan-Capital-Limited_-FMQR-Surv._-Apr-2025_final.pdf"


#test for date extraction from pdf
def test_extract_date_from_text(scraper, icra_sample_pdf):
    
    # extract text from the sample PDF
    with pdfplumber.open(BytesIO(icra_sample_pdf)) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)
    
    date = scraper.extract_date_from_text(text)
    assert date == "April 17, 2025"


def test_get_pdf_details(scraper, icra_sample_pdf, mocker):
    #mock requests.get to return the sample PDF
    mock_get = mocker.patch('requests.get')
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_content.return_value = [icra_sample_pdf]
    mock_get.return_value = mock_response
    
    text = scraper.get_pdf_details("some_pdf_url")
    assert "Fund Management Quality " in text  



#test to process a new link 
def test_process_pdf_link(scraper, mocker):
    pdf_link = {"title": "Test Report", "url": "http://test.com/report.pdf"}
    
    # Configure the db_service mock
    scraper.service.db_service.check_if_event_exists.return_value = False
    scraper.service.db_service.add_event.return_value = 123
    
    # Mock other dependencies
    mocker.patch.object(scraper, 'get_pdf_details', return_value="PDF text")
    mocker.patch.object(scraper, 'extract_date_from_text', return_value="2024-04-30")
    mock_upload = mocker.patch('nepali_news_scrapers.scrapers.icra_scraper.icra_scraper.upload_json_to_minio')
    
    scraper.process_pdf_link(pdf_link)
    
    # Verify DB interaction and Minio upload
    scraper.service.db_service.check_if_event_exists.assert_called_once_with("http://test.com/report.pdf")
    scraper.service.db_service.add_event.assert_called_once_with(
        title="Test Report",
        url="http://test.com/report.pdf",
        published_date="2024-04-30",
        content="PDF text"
    )
    mock_upload.assert_called_once()
    assert pdf_link["url"] in scraper.processed_urls



def test_process_pdf_link_skips_duplicate(scraper):
    pdf_link = {"title": "Test", "url": "http://existing.com/report.pdf"}
    scraper.processed_urls.add(pdf_link["url"])
    
    scraper.process_pdf_link(pdf_link)
    scraper.service.db_service.check_if_event_exists.assert_not_called()

def test_process_pdf_link_skips_existing_db(scraper):
    """Test skipping URLs present in the database."""
    pdf_link = {"title": "Test", "url": "http://existing.com/report.pdf"}
    scraper.service.db_service.check_if_event_exists.return_value = True
    
    scraper.process_pdf_link(pdf_link)
    scraper.service.db_service.add_event.assert_not_called()
