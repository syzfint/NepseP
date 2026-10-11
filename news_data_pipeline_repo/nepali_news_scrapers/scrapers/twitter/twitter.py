import requests
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()
BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

def create_headers():
    return {"Authorization": f"Bearer {BEARER_TOKEN}"}

def check_rate_limits(response):
  
    remaining = int(response.headers.get("x-rate-limit-remaining", 1))  # Default to 1 if header is missing
    reset_time = int(response.headers.get("x-rate-limit-reset", time.time() + 900))  # Default to 15 minutes if missing

    if remaining <= 1:  # if only 1 or 0 requests remain, sleep until reset
        current_time = int(time.time())
        sleep_duration = max(reset_time - current_time, 1)  # Ensure at least 1 second
        print(f"Rate limit almost exhausted. Sleeping for {sleep_duration} seconds until reset...")
        time.sleep(sleep_duration)

def get_user_id(username):   
    url = f"https://api.twitter.com/2/users/by/username/{username}"
    response = requests.get(url, headers=create_headers())
    if response.status_code != 200:
        raise Exception(f"Error fetching user id: {response.status_code} {response.text}")
    check_rate_limits(response)
    return response.json()["data"]["id"]

def get_recent_tweets(user_id, max_results=10):
   
    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    params = {
        "max_results": max_results,
        "tweet.fields": "created_at,public_metrics,author_id" 
    }
    headers = create_headers()
    max_retries = 3

    for attempt in range(max_retries):
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            check_rate_limits(response)
            return response.json().get("data", [])
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"Rate limit exceeded. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            raise Exception(f"Error fetching tweets: {response.status_code} {response.text}")
    raise Exception("Failed to fetch tweets after multiple attempts due to rate limits.")

def get_tweet_comments(tweet):
    """
    """
    tweet_id = tweet["id"]
    original_author_id = tweet["author_id"]
    url = "https://api.twitter.com/2/tweets/search/recent"
    # Fetch only direct replies to the original tweet
    query = f"conversation_id:{tweet_id} in_reply_to_user_id:{original_author_id}"
    params = {
        "query": query,
        "max_results": 10,
        "tweet.fields": "author_id,created_at,public_metrics"  # Added public_metrics
    }
    max_retries = 3
    for attempt in range(max_retries):
        response = requests.get(url, headers=create_headers(), params=params)
        if response.status_code == 200:
            return response.json().get("data", [])
        elif response.status_code == 429:
            reset_time = int(response.headers.get("x-rate-limit-reset", time.time() + 60))
            current_time = int(time.time())
            sleep_duration = max(reset_time - current_time, 60)
            print(f"Rate limit exceeded for tweet {tweet_id}. Sleeping for {sleep_duration} seconds...")
            time.sleep(sleep_duration)
        else:
            print(f"Warning: Unable to fetch comments for tweet {tweet_id}: {response.status_code} {response.text}")
            return []
    print(f"Failed to fetch comments for tweet {tweet_id} after {max_retries} attempts.")
    return []

def main():
    username = "imVkohli"  # Hardcoded for this example
    try:
        user_id = get_user_id(username)
        print(f"User ID for {username} is {user_id}\n")
    except Exception as e:
        print(f"Error: {e}")
        if "429" in str(e):
            print("Rate limit exceeded. Please wait 15 minutes and try again.")
        return

    try:
        tweets = get_recent_tweets(user_id, max_results=8)
        if not tweets:
            print("No tweets found.")
            return
    except Exception as e:
        print(f"Error: {e}")
        if "429" in str(e):
            print("Rate limit exceeded for tweets. Please wait 15 minutes.")
        return

    for tweet in tweets:
        # Print tweet details with like and comment counts
        print(f"Tweet ID: {tweet['id']}")
        print(f"Tweet text: {tweet['text']}")
        print(f"Created at: {tweet['created_at']}")
        print(f"Likes: {tweet['public_metrics']['like_count']}")
        print(f"Comments: {tweet['public_metrics']['reply_count']}")
        
        # Fetch and print comments
        # comments = get_tweet_comments(tweet)
        # if comments:
        #     print("Comments:")
        #     for comment in comments:
        #         print(f" - Comment ID: {comment['id']}")
        #         print(f" - Author ID: {comment['author_id']}")
        #         print(f" - Comment text: {comment['text']}")
        #         print(f" - Likes: {comment['public_metrics']['like_count']}")
        #         print(f" - Created at: {comment['created_at']}")
        # else:
        #     print(" - No comments found or available.")
        
        print("-" * 40)
        time.sleep(5)  # Delay between comment requests

if __name__ == "__main__":
    main()