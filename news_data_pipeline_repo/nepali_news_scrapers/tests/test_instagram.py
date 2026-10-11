import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import pytz
from nepali_news_scrapers.scrapers.insta_scraper.ronb_scraper import InstagramScraper
from .fixtures import scraper_service, instagram_api_response
import requests

@pytest.fixture
def instagram_scraper(scraper_service):
    return InstagramScraper(scraper_service)

# Test fetching user profile
def test_fetch_user_profile(instagram_scraper, instagram_api_response, mocker):
    username = "routineofnepalbanda"
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    mock_get = mocker.patch("requests.get")
    mock_response = Mock()
    mock_response.json.return_value = instagram_api_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    
    profile_data = instagram_scraper.fetch_user_profile(username)
    
    assert profile_data == instagram_api_response
    assert profile_data["data"]["user"]["username"] == username
    mock_get.assert_called_once_with(url, headers=mocker.ANY)


def test_fetch_user_profile_request_failure(instagram_scraper, mocker):
    username = "routineofnepalbanda"
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = requests.RequestException("Network error")
    
    profile_data = instagram_scraper.fetch_user_profile(username)
    
    assert profile_data is None
    instagram_scraper.service.log.error.assert_called_once_with(
        f"Failed to fetch user profile: Network error"
    )
    mock_get.assert_called_once_with(url, headers=mocker.ANY)


# Test extracting posts
def test_extract_posts(instagram_scraper, instagram_api_response):
    posts = instagram_scraper.extract_posts(instagram_api_response, max_posts=2)
    
    expected_posts = instagram_api_response["data"]["user"]["edge_owner_to_timeline_media"]["edges"][:2]
    assert len(posts) == 2
    assert posts[0]["node"]["id"] == expected_posts[0]["node"]["id"]
    assert posts[1]["node"]["id"] == expected_posts[1]["node"]["id"]

def test_extract_posts_no_posts(instagram_scraper):
    profile_data = {"data": {"user": {"edge_owner_to_timeline_media": {"edges": []}}}}
    posts = instagram_scraper.extract_posts(profile_data, max_posts=2)
    
    assert posts == []
    
    # Test with missing keys
    profile_data = {"data": {"user": {}}}
    posts = instagram_scraper.extract_posts(profile_data, max_posts=2)
    
    assert posts == []


# Test processing a post 
def test_process_post(instagram_scraper, instagram_api_response, mocker):
    username = "routineofnepalbanda"
    
    node = instagram_api_response["data"]["user"]["edge_owner_to_timeline_media"]["edges"][0]["node"]
    post_timestamp = node["taken_at_timestamp"]
    post_datetime = datetime.fromtimestamp(post_timestamp, tz=instagram_scraper.tz)
    current_time = post_datetime + timedelta(minutes=30)
    
    mock_now = mocker.patch("datetime.datetime")
    mock_now.now.return_value = current_time
    
    post_info = instagram_scraper.process_post(node, username, current_time)
    
    expected_id = node["id"]
    expected_content = node["edge_media_to_caption"]["edges"][0]["node"]["text"] if node["edge_media_to_caption"]["edges"] else ""
    expected_likes = node["edge_media_preview_like"]["count"]
    expected_comments = node["edge_media_to_comment"]["count"]
    expected_shortcode = node["shortcode"]
    
    assert post_info is not None
    assert post_info["id"] == expected_id
    assert post_info["content"] == expected_content
    assert post_info["likes_count"] == expected_likes
    assert post_info["comments_count"] == expected_comments
    assert post_info["title"] == f"post by {username}"
    assert post_info["author"] == username
    assert post_info["published_date"] == post_datetime.strftime("%Y-%m-%d")
    assert post_info["published_time"] == post_datetime.strftime("%H:%M:%S")
    assert post_info["category"] == "social_media"
    assert post_info["url"] == f"https://www.instagram.com/p/{expected_shortcode}"

def test_process_post_empty_caption(instagram_scraper, mocker):
    username = "testuser"
    current_time = datetime.now(pytz.timezone("Asia/Kathmandu"))
    
    node = {
        "id": "123",
        "taken_at_timestamp": int(current_time.timestamp()) - 1800,
        "edge_media_to_caption": {"edges": [{"node": {"text": ""}}]},
        "shortcode": "abc",
        "edge_media_preview_like": {"count": 10},
        "edge_media_to_comment": {"count": 5},
    }
    
    mock_now = mocker.patch("datetime.datetime")
    mock_now.now.return_value = current_time
    
    post_info = instagram_scraper.process_post(node, username, current_time)
    
    assert post_info is None
    instagram_scraper.service.log.info.assert_called_once_with(
        f"Skipping post 123 due to empty content."
    )


def test_process_post_missing_shortcode(instagram_scraper, mocker):
    username = "testuser"
    current_time = datetime.now(pytz.timezone("Asia/Kathmandu"))
    
    node = {
        "id": "123",
        "taken_at_timestamp": int(current_time.timestamp()) - 1800,
        "edge_media_to_caption": {"edges": [{"node": {"text": "Test caption"}}]},
        "edge_media_preview_like": {"count": 10},
        "edge_media_to_comment": {"count": 5},
    }
    
    mock_now = mocker.patch("datetime.datetime")
    mock_now.now.return_value = current_time
    
    post_info = instagram_scraper.process_post(node, username, current_time)
    
    assert post_info is not None
    assert post_info["url"] == "https://www.instagram.com/p/"  # Empty shortcode results in base URL
    assert post_info["content"] == "Test caption"

# Test processing a post older than 1 hour
def test_process_post_skips_old_post(scraper_service, instagram_scraper,instagram_api_response, mocker):
    username = "routineofnepalbanda"
    
    node = instagram_api_response["data"]["user"]["edge_owner_to_timeline_media"]["edges"][0]["node"]
    post_timestamp = node["taken_at_timestamp"]
    post_datetime = datetime.fromtimestamp(post_timestamp, tz=instagram_scraper.tz)
    current_time = post_datetime + timedelta(hours=2)
    
    mock_now = mocker.patch("datetime.datetime")
    mock_now.now.return_value = current_time
    
    post_info = instagram_scraper.process_post(node, username, current_time)
    
    assert post_info is None

# Test skipping posts with empty content
def test_process_post_skips_empty_content(scraper_service, instagram_scraper,mocker):
    username = "testuser"
    current_time = datetime.now(pytz.timezone("Asia/Kathmandu"))
    
    node = {
        "id": "123",
        "taken_at_timestamp": int(current_time.timestamp()) - 1800,
        "edge_media_to_caption": {"edges": []},
        "shortcode": "abc",
        "edge_media_preview_like": {"count": 10},
        "edge_media_to_comment": {"count": 5},
    }
    
    mock_now = mocker.patch("datetime.datetime")
    mock_now.now.return_value = current_time
    
    post_info = instagram_scraper.process_post(node, username, current_time)
    assert post_info is None




def test_start_no_posts_found(instagram_scraper, instagram_api_response, mocker):
    username = "routineofnepalbanda"
    modified_profile_data = instagram_api_response.copy()
    modified_profile_data["data"]["user"]["edge_owner_to_timeline_media"]["edges"] = []
    
    mocker.patch.object(instagram_scraper, "fetch_user_profile", return_value=modified_profile_data)
    
    instagram_scraper.start({"username": username})
    
    instagram_scraper.service.log.info.assert_called_once_with(
        "No posts found for this user."
    )


def test_start_skips_existing_embeddings(instagram_scraper, instagram_api_response, mocker):
    username = "routineofnepalbanda"
    mocker.patch.object(instagram_scraper, "fetch_user_profile", return_value=instagram_api_response)
    mocker.patch.object(
        instagram_scraper.service.db_service,
        "check_if_embeddings_exist",
        return_value=True
    )
    
    instagram_scraper.start({"username": username})
    
    instagram_scraper.service.log.info.assert_called_with(
        mocker.ANY
    )
    instagram_scraper.service.save_json.assert_not_called()