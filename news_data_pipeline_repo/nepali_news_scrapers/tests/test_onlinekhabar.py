import os
import pytest
import json
from unittest.mock import MagicMock, patch
import requests
from nepali_news_scrapers.scrapers.online_khabar_market.ok_scraper_news_backend import  ScraperService,   OnlineKhabarMarketScraper,  cache_lock,   cache
import asyncio


# fixture to load all the test JSON data from files at once
@pytest.fixture(scope="session") #runs only once for all tests below
def all_test_data():
    fixtures = {}
    symbol = "NICA"
    sections = [
        "price_chart", "key_statistics", "quick_view",
        "technical_indicators", "ticker_info", "market_range", "market_status"
    ]
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(current_dir, "html_test_files")

    for section in sections:
        file_path = os.path.join(base_path, symbol, f"{section}.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                fixtures[section] = json.load(f)
                print(f"Loaded: {file_path}")
        except FileNotFoundError:
            pytest.fail(f"Critical test file missing: {file_path}") 

    return fixtures # return the  fixture dictionary with all loaded data


#set up the scraper object and clear caches before each test
@pytest.fixture(autouse=True) # autouse=True makes this run automatically before every test
def setup_scraper():
    service = ScraperService()
    service.log = MagicMock()
    scraper = OnlineKhabarMarketScraper(service)

    #clear caches to make sure each test starts fresh
    with cache_lock:
        cache.clear()    #clear global cache
    scraper.data_cache.clear() # Clear the cache inside the scraper instance

    # make the scraper object available to the test function
    yield scraper



# test getting the price chart section
def test_get_price_chart_section(setup_scraper, all_test_data):
    scraper = setup_scraper 
    test_data = all_test_data  #get all the laded json files/data

    symbol = "NICA"
    section = "price_chart"
    price_chart_data = test_data[section] 

    #mock to simulate real http requests
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = price_chart_data 

    # Patch the 'get' method

    with patch.object(scraper.service.session, "get", return_value=mock_response) as mock_get_call:
        result = asyncio.run(scraper.get_section(section, symbol))


    expected_response = price_chart_data.get("response", {})
    assert result == expected_response
    mock_get_call.assert_called_once() # Check the fake web request was made once


# Test getting key statistics
def test_get_key_statistics_section(setup_scraper, all_test_data):
    scraper = setup_scraper
    test_data = all_test_data
    symbol = "NICA"
    section = "key_statistics"
    fixture_data = test_data[section]

    # Mocking
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = fixture_data
    with patch.object(scraper.service.session, "get", return_value=mock_response) as mock_get_call:
        # Run code
        result = asyncio.run(scraper.get_section(section, symbol))

    # Check result
    expected_response = fixture_data.get("response", {})
    assert result == expected_response
    mock_get_call.assert_called_once()


# Test market status section
def test_get_market_status_section(setup_scraper, all_test_data):
    scraper = setup_scraper
    test_data = all_test_data
    symbol = "NICA"
    section = "market_status"
    fixture_data = test_data[section]

    # Mocking
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = fixture_data
    with patch.object(scraper.service.session, "get", return_value=mock_response) as mock_get_call:
        # Run code
        result = asyncio.run(scraper.get_section(section, symbol))

    # Check result - special case for market status
    expected_response = fixture_data.get("response", [{}])[0]
    assert result == expected_response
    mock_get_call.assert_called_once()


# test caching behavior
def test_get_section_uses_cache(setup_scraper, all_test_data):
    scraper = setup_scraper
    test_data = all_test_data
    symbol = "NICA"
    section = "quick_view"
    fixture_data = test_data[section]

    # Mocking
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = fixture_data

    with patch.object(scraper.service.session, "get", return_value=mock_response) as mock_get_method:

        # call the function  first time
        result1 = asyncio.run(scraper.get_section(section, symbol))

        #call the function  second time
        result2 = asyncio.run(scraper.get_section(section, symbol))


    assert result1 == result2

    assert mock_get_method.call_count == 1


#test handling bad JSON response
def test_get_section_handles_bad_json_response(setup_scraper): 
    scraper = setup_scraper
    symbol = "NICA"
    section = "ticker_info"

    # Mocking - return JSON without 'response' key
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"dummy_key": "some_value"}

    with patch.object(scraper.service.session, "get", return_value=mock_response) as mock_get_call:
        # Run code
        result = asyncio.run(scraper.get_section(section, symbol))

    # Check result - should be empty dict
    assert result == {}
    mock_get_call.assert_called_once()


#testing the  scrape_all func
def test_scrape_all_works(setup_scraper, all_test_data):
    scraper = setup_scraper
    fixtures = all_test_data 
    symbol = "NICA"
    sections = list(fixtures.keys()) # Get section names from loaded data


    # Mocking - need to return different data based on URL
    def mock_get_logic(url, *args, **kwargs):

        # This function decides what data to return based on the URL requested
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "chart" in url: 
            mock_resp.json.return_value = fixtures["price_chart"]
        elif "ticker-stats" in url:
            mock_resp.json.return_value = fixtures["key_statistics"]

        elif "ticker-quick-view" in url:
            mock_resp.json.return_value = fixtures["quick_view"]

        elif "ticker-technical-indicator" in url: 
            mock_resp.json.return_value = fixtures["technical_indicators"]
        elif "ticker-info" in url:
            mock_resp.json.return_value = fixtures["ticker_info"]
            
        elif "market-range" in url: 
            mock_resp.json.return_value = fixtures["market_range"]
        elif "market-status" in url: 
            mock_resp.json.return_value = fixtures["market_status"]
        else:
            print(f"Warning: Mock GET received unexpected URL: {url}")
            mock_resp.json.return_value = {}
            mock_resp.status_code = 404
        return mock_resp

    # Patch 'get' 
    with patch.object(scraper.service.session, "get", side_effect=mock_get_logic) as mock_get_method:

        result = asyncio.run(scraper.scrape_all(symbol))

    assert result["symbol"] == symbol
    assert "scraped_at" in result
    assert result["price_chart"] == fixtures["price_chart"]["response"]
    expected_ticker_info = fixtures["ticker_info"]["response"]
    expected_ticker_info["icon"] = f"https://images.smtmcapital.com.np/logos/{symbol}.png"
    assert result["ticker_info"] == expected_ticker_info
    assert result["market_status"] == fixtures["market_status"]["response"][0]

    assert mock_get_method.call_count == len(sections)


# Test scrape_all when one section fails
def test_scrape_all_handles_one_section_failing(setup_scraper, all_test_data):
    scraper = setup_scraper
    fixtures = all_test_data
    symbol = "NICA"
    sections = list(fixtures.keys())

    # Mocking with an error for one URL
    def mock_get_with_failure(url, *args, **kwargs):
        print(f"Mock GET (with failure logic) called with URL: {url}")
        if "ticker-info" in url:
            print("Simulating failure for ticker-info")
            raise requests.RequestException("Fake network error") # THE FAILURE

        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "chart" in url:
            mock_resp.json.return_value = fixtures["price_chart"]

        elif "ticker-stats" in url:
            mock_resp.json.return_value = fixtures["key_statistics"]
        elif "ticker-quick-view" in url:
            mock_resp.json.return_value = fixtures["quick_view"]
        elif "market-status" in url:
            mock_resp.json.return_value = fixtures["market_status"]
        else:
             if not any(sec_pattern in url for sec_pattern in ["chart", "ticker-stats", "quick-view", "market-status"]):
                mock_resp.json.return_value = {}
                mock_resp.status_code = 404

        return mock_resp


    with patch.object(scraper.service.session, "get", side_effect=mock_get_with_failure) as mock_get_method:
        # Run code
        result = asyncio.run(scraper.scrape_all(symbol))

    # Check results
    assert result["symbol"] == symbol
    assert "scraped_at" in result
    # Check the failed section is empty (except icon added by scrape_all)
    assert result["ticker_info"] == {"icon": f"https://images.smtmcapital.com.np/logos/{symbol}.png"}

    # Check other sections are populated correctly
    assert result["price_chart"] == fixtures["price_chart"]["response"]
    assert result["key_statistics"] == fixtures["key_statistics"]["response"]
    assert result["market_status"] == fixtures["market_status"]["response"][0]

    assert mock_get_method.call_count == len(sections)