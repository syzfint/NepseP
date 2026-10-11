import pytest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
import requests
from io import BytesIO
import pdfplumber
from nepali_news_scrapers.scrapers.nepal_rastra_bank.nrb_scraper import NRBScraper
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService
from .fixtures import scraper_service, nrb_homepage_html, nrb_sample_pdf


@pytest.fixture
def scraper(scraper_service):
    # Set up mock database service for scraper
    scraper_service.db_service = Mock()
    return NRBScraper(scraper_service)

@pytest.fixture
def homepage_soup(nrb_homepage_html):
    return BeautifulSoup(nrb_homepage_html, 'html.parser')



def test_make_request_url(scraper):
    relative_url = "economic-report/macroeconomic-report.pdf"
    result = scraper.make_request_url(relative_url)
    assert result == "https://www.nrb.org.np/economic-report/macroeconomic-report.pdf"



def test_site_availability(scraper):
    try:
        # Make real request to check if NRB site is up
        response = requests.get(scraper.base_url, headers=scraper.headers, timeout=10)
        assert response.status_code == 200
    except requests.exceptions.RequestException:
        # Fail the test if site is not available
        pytest.fail("NRB website is not available")




# test finding macroeconomic block
def test_find_macroeconomic_block_success(scraper, homepage_soup):
    block = scraper._find_macroeconomic_block(homepage_soup)
    assert block is not None
    # Check if block title contains expected text
    assert "Current Macro-Economic" in block.find("div", class_="card-title").text


def test_find_macroeconomic_block_failure(scraper):

    empty_soup = BeautifulSoup("<html></html>", 'html.parser')
    block = scraper._find_macroeconomic_block(empty_soup)
    assert block is None
    # Check if error is logged when block not found
    scraper.service.log.error.assert_called()


#test processing macroeconomic block and report items
def test_get_macroeconomic_situation_success(scraper, mocker, nrb_homepage_html):
    # Mock _fetch_page to return homepage HTML
    mocker.patch.object(scraper, '_fetch_page', return_value=nrb_homepage_html)
    # Mock _process_macroeconomic_block to check if it's called
    mocker.patch.object(scraper, '_process_macroeconomic_block')
    
    scraper.get_macroeconomic_situation()
    # Check if _process_macroeconomic_block is called once
    scraper._process_macroeconomic_block.assert_called_once()


def test_get_macroeconomic_situation_failure(scraper, mocker):
    # Mock requests.get to simulate a failure
    mocker.patch('requests.get', side_effect=requests.exceptions.RequestException("Mocked failure"))
    scraper.get_macroeconomic_situation()
    # Check if error is logged with correct message
    scraper.service.log.error.assert_called_with(
        f"Error fetching page {scraper.base_url}: Mocked failure"
    )

def test_process_report_item_english(scraper, mocker):
    # Create HTML for an English report item
    item_html = """
    <li>
        <a href="/reports/macroeconomic.pdf">Current Macroeconomic Report (English)</a>
        <span class="mr-3 text-muted">April 2024</span>
    </li>
    """
    item = BeautifulSoup(item_html, 'html.parser').li
    # Mock _process_english_report to check if it's called
    mocker.patch.object(scraper, '_process_english_report')
    
    scraper._process_report_item(item)
    # Check if _process_english_report is called for English report
    scraper._process_english_report.assert_called_once()

def test_process_report_item_non_english(scraper, mocker):
    # Create HTML for a non-English report item
    item_html = """
    <li>
        <a href="/reports/macroeconomic.pdf">वर्तमान म्याक्रोइकोनोमिक प्रतिवेदन</a>
        <span class="mr-3 text-muted">April 2024</span>
    </li>
    """
    item = BeautifulSoup(item_html, 'html.parser').li
    # Mock _process_english_report to check if it's not called
    mocker.patch.object(scraper, '_process_english_report')
    
    scraper._process_report_item(item)
    # Check that _process_english_report is not called for non-English report
    scraper._process_english_report.assert_not_called()



#test extracting published date
def test_extract_published_date(scraper, homepage_soup):
    # Get macroeconomic block from homepage
    macro_block = scraper._find_macroeconomic_block(homepage_soup)
    # Find the report list in the block
    report_list = macro_block.find("ul", class_="arrowed-list")
    # Get the first report item
    item = report_list.find_all("li")[0]
    
    date = scraper._extract_published_date(item)
    assert date is not None
    # Check if date matches expected value from homepage
    assert date == "April 9, 2025"


#test finding PDF URLs
def test_find_pdf_from_page_direct_pdf(scraper, mocker):
    url = "http://test.com/report.pdf"
    # Mock requests.head to simulate a direct PDF response
    mock_head = mocker.patch('requests.head')
    mock_response = Mock()
    mock_response.headers = {'content-type': 'application/pdf'}
    mock_response.url = url
    mock_head.return_value = mock_response
    
    result = scraper.find_pdf_from_page(url)
    # Check if the method returns the direct PDF URL
    assert result == url


#test that the scraper can handle NRB's redirect to PDF
def test_find_pdf_from_page_html_with_pdf(scraper, mocker):
    test_url = "https://www.nrb.org.np/red/some-report/"
    pdf_url = "https://www.nrb.org.np/contents/uploads/report.pdf"
    
    # Mock requests.head to simulate a redirect to a PDF
    mock_head = mocker.patch('requests.head')
    mock_head_response = Mock()
    mock_head_response.url = pdf_url
    mock_head.return_value = mock_head_response
    
    result = scraper.find_pdf_from_page(test_url)
    # Check if the method returns the redirected PDF URL
    assert result == pdf_url
    # Verify that HEAD request was made with correct parameters
    mock_head.assert_called_once_with(test_url, headers=scraper.headers, 
                                     allow_redirects=True, timeout=10)


def test_find_pdf_from_page_direct_html(scraper, mocker):
    """Test HTML page that contains direct PDF links"""
    test_url = "https://www.nrb.org.np/some-page/"
    pdf_url = "https://www.nrb.org.np/reports/report.pdf"

    # Mock HEAD request to show it's an HTML page
    mock_head = mocker.patch('requests.head')
    mock_head_response = Mock()
    mock_head_response.url = test_url
    mock_head_response.headers = {'content-type': 'text/html'}
    mock_head.return_value = mock_head_response

    # Mock GET request to return HTML with a PDF link
    mock_get = mocker.patch('requests.get')
    mock_get_response = Mock()
    mock_get_response.text = """
    <div>
        <a href="/reports/report.pdf">Download PDF</a>
    </div>
    """
    #mock raise_for_status to avoid errors
    mock_get_response.raise_for_status = Mock()
    mock_get.return_value = mock_get_response

    result = scraper.find_pdf_from_page(test_url)
    # Check if the method returns the PDF URL from the HTML
    assert result == pdf_url

def test_find_pdf_from_page_no_pdf(scraper, mocker):
    # Mock requests.get to return HTML with no PDF links
    mocker.patch('requests.get')
    mock_response = Mock()
    mock_response.headers = {'content-type': 'text/html'}
    mock_response.text = "<html><body>No PDF here</body></html>"
    requests.get.return_value = mock_response
    
    result = scraper.find_pdf_from_page("http://test.com/no-pdf")
    # Check if the method returns None when no PDF is found
    assert result is None

def test_find_pdf_from_page_homepage_redirect(scraper, mocker, nrb_homepage_html):
    """Test that the scraper handles the redirect to PDF from the homepage English report link"""
    # Parse homepage HTML to find the English report URL
    soup = BeautifulSoup(nrb_homepage_html, 'html.parser')
    macro_block = soup.find_all("div", class_="main-block-card")[1]
    report_list = macro_block.find("ul", class_="arrowed-list arrowed-list--border")
    # Find the first item with "English" in the link text
    english_item = next((item for item in report_list.find_all("li") if "English" in item.find("a").text), None)
    
    # Check if English report was found in HTML
    assert english_item is not None, "English report not found in homepage HTML"
    
    test_url = english_item.find("a")['href']
    pdf_url = "https://www.nrb.org.np/contents/uploads/2025/04/Current-Macroeconomic-and-Financial-Situation-English-Based-on-Eight-Months-data-of-2024.25.pdf"

    # Mock HEAD request to simulate redirect to PDF
    mock_head = mocker.patch('requests.head')
    mock_response = Mock()
    mock_response.url = pdf_url
    mock_response.headers = {'content-type': 'application/pdf'}
    mock_head.return_value = mock_response

    result = scraper.find_pdf_from_page(test_url)
    # Check if the method returns the correct PDF URL
    assert result == pdf_url


def test_find_pdf_from_page_redirect(scraper, mocker):
    test_url = "https://www.nrb.org.np/red/current-macroeconomic-and-financial-situation-english-based-on-eight-months-data-of-2024-25/"
    pdf_url = "https://www.nrb.org.np/contents/uploads/2025/04/Current-Macroeconomic-and-Financial-Situation-English-Based-on-Eight-Months-data-of-2024.25.pdf"

    # Mock HEAD request to simulate redirect to PDF
    mock_head = mocker.patch('requests.head')
    mock_head_response = Mock()
    mock_head_response.url = pdf_url
    mock_head.return_value = mock_head_response

    result = scraper.find_pdf_from_page(test_url)
    # Check if the method returns the redirected PDF URL
    assert result == pdf_url


#test extracting PDF text
def test_extract_pdf_text_success(scraper, nrb_sample_pdf, mocker):
    # Mock requests.get to return the sample PDF
    mocker.patch('requests.get')
    mock_response = Mock()
    mock_response.iter_content.return_value = [nrb_sample_pdf]
    requests.get.return_value = mock_response
    
    text = scraper.extract_pdf_text("http://test.com/report.pdf")
    assert text is not None
    # Check if extracted text contains expected keyword
    assert "Macroeconomic" in text  # Adjust based on your sample PDF content

def test_extract_pdf_text_failure(scraper, mocker):
    # Mock requests.get to simulate a failure
    mocker.patch('requests.get')
    mock_response = Mock()
    mock_response.iter_content.side_effect = Exception("Failed")
    requests.get.return_value = mock_response
    
    text = scraper.extract_pdf_text("http://test.com/report.pdf")
    assert text is None
    # Check if error is logged when PDF extraction fails
    assert scraper.service.log.error.call_count == 1

# Test storing report data
def test_store_report_data(scraper):
    # Mock database methods to return IDs
    scraper.service.db_service.upsert_nrb_report.return_value = 123
    scraper.service.db_service.add_event.return_value = 456
    
    # Mock upload_json_to_minio to avoid external calls
    with patch('nepali_news_scrapers.scrapers.nepal_rastra_bank.nrb_scraper.upload_json_to_minio') as mock_upload:
        scraper._store_report_data(
            title="Test Report",
            url="http://test.com/report",
            pdf_url="http://test.com/report.pdf",
            published_date="April 2024",
            content="PDF content"
        )
        
        # Check if database methods and upload were called
        scraper.service.db_service.upsert_nrb_report.assert_called_once()
        scraper.service.db_service.add_event.assert_called_once()
        mock_upload.assert_called_once()

#integration tests
def test_pdf_download_integration(scraper):
    
    # Use a known NRB report URL that redirects to PDF
    test_url = "https://www.nrb.org.np/red/current-macroeconomic-and-financial-situation-english-based-on-eight-months-data-of-2024-25/"
    
    try:
        # Check if the URL is accessible with a HEAD request
        head_response = requests.head(test_url, allow_redirects=True, timeout=10)
        if head_response.status_code != 200:
            # Skip if page is not available
            pytest.skip("NRB report page not available")
            
        # Skip if it doesn't redirect to a PDF (e.g., rate limiting)
        if not head_response.url.endswith('.pdf'):
            pytest.skip("NRB didn't redirect to PDF - might be rate limiting")
            
        # Test PDF text extraction
        text = scraper.extract_pdf_text(test_url)
        assert text is not None
        # Check if extracted text is long enough
        assert len(text) > 100 
        
    except requests.exceptions.RequestException as e:
        # Skip if there's a network error
        pytest.skip(f"Skipping due to network error: {str(e)}")
    except Exception as e:
        # Fail if PDF download fails
        pytest.fail(f"PDF download failed: {str(e)}")