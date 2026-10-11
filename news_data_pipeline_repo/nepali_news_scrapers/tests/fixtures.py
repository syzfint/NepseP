from datetime import datetime
import pytz
from unittest.mock import Mock
from pytest_mock import MockerFixture
import pytest
from nepali_news_scrapers.services.scraper_service.scraper_service import ScraperService,ScraperError
from nepali_news_scrapers.scrapers.ekantipur.ekanitpur import EkantipurScraper
import os
import json 

@pytest.fixture
def scraper_service():
    service = Mock(spec=ScraperService)
    service.log = Mock()
    service.db_service = Mock()
    service.make_get_request = Mock()
    service.save_json = Mock()
    service.convert_nepali_to_english = Mock()
    return service

@pytest.fixture
def mock_datetime(mocker: MockerFixture):
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    fake_time = datetime(2024, 4, 19, 10, 45, tzinfo=kathmandu_tz)

    class MockDateTime:
        @classmethod
        def now(cls, tz=None):
            return fake_time if tz else fake_time.replace(tzinfo=None)
        
       

    mocker.patch('nepali_news_scrapers.scrapers.ekantipur.ekanitpur.datetime', MockDateTime)
    return fake_time


@pytest.fixture
def mock_kathmandu_datetime(mocker: MockerFixture):
    """Custom datetime mock for Kathmandu Post scraper"""
    kathmandu_tz = pytz.timezone('Asia/Kathmandu')
    fake_time = datetime(2024, 4, 19, 10, 45, tzinfo=kathmandu_tz)

    class MockDateTime:
        @classmethod
        def now(cls, tz=None):
            return fake_time if tz else fake_time.replace(tzinfo=None)
        
        @classmethod
        def strptime(cls, *args, **kwargs):
            return datetime.strptime(*args, **kwargs)

    mocker.patch(
        'nepali_news_scrapers.scrapers.the_kathmandu_post.the_kathmandu_post.datetime',
        MockDateTime
    )
    return fake_time


#ekantipur fixtures
@pytest.fixture
def ekantipur_article_html():
    """fixture to load the actual html content of ekantipur html file"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/ekantipur_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        return content


@pytest.fixture
def ekantipur_page_listings():
    """fixture to load the html content of the ekanitpur page listing"""   
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/ekantipur_page_listings.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        return content

#setopati fixtures
@pytest.fixture
def setopati_article_html():
    """fixture to load the actual HTML content of a Setopati article page."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/setopati_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    
@pytest.fixture
def setopati_page_listings():
    """fixture to load the actual lsitings html content of a Setopati ."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/setopati_listings.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    


#merolagani fixture
@pytest.fixture
def merolagani_article_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/merolagani_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    


#myrepublica fixtures
@pytest.fixture
def republica_article_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/republica_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    

@pytest.fixture
def republica_page_listings():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/republica_listings.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


#nepalitimes fixture
@pytest.fixture
def graphql_response():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/graphql_response.json")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def nepalitimes_article_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/nepalitimes_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    


#nepalipaisa fixtures
@pytest.fixture
def nepalipaisa_news_list():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/nepalipaisa_news_list.json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"JSON file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def nepalipaisa_news_details():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/nepalipaisa_news_details.json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"JSON file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def nepalipaisa_article_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/nepalipaisa_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    


#Sharesansar fixtures
@pytest.fixture
def sharesansar_article_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/sharesansar_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    

@pytest.fixture
def sharesansar_page_listings():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/sharesansar_listings.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

#annapurnaPost fixtures
@pytest.fixture
def annapurna_article_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/annapurna_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    

@pytest.fixture
def annapurna_page_listings():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/annapurna_listings.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    

#icra fixtures
@pytest.fixture
def icra_listings_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/icra_listings.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def icra_sample_pdf():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/sample_icra_pdf.pdf")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found at: {file_path}")
    with open(file_path, "rb") as f:
        return f.read()




#fixtures for NRB
@pytest.fixture
def nrb_homepage_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/nrb_homepage.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()



@pytest.fixture
def nrb_sample_pdf():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/nrb_sample.pdf")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found at: {file_path}")
    with open(file_path, "rb") as f:
        return f.read()
    


#kathmandupost fixtures
@pytest.fixture
def kathmandu_post_article_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/kathmandupost_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    
@pytest.fixture
def kathmandu_post_page_listings():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/kathmandupost_listings.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    

#gorkhapatra fixtures

@pytest.fixture
def gorkhapatra_page_listings():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/gorkhapatra_listings.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def gorkhapatra_article_html():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/gorkhapatra_single_page.html")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"HTML file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
    


#instagram fixture
@pytest.fixture
def instagram_api_response():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "html_test_files/insta_response.json")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
