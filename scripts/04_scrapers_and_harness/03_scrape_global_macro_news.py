import os
import requests
import pandas as pd
from datetime import datetime

# ==========================================
# IMPORTANT: Put your World News API key here!
# ==========================================
API_KEY = os.environ.get("WORLD_NEWS_API_KEY", "YOUR_API_KEY_HERE")

def update_world_news():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] Fetching from World News API...")
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print(f"[{current_time}] ERROR: Please set your World News API key in this script or as the WORLD_NEWS_API_KEY environment variable.")
        return

    url = f"https://api.worldnewsapi.com/search-news?source-country=np&api-key={API_KEY}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if "news" in data and data["news"]:
            # Convert incoming World News data to match our schema
            incoming_df = pd.DataFrame(data["news"])
            
            # Map World News API fields to our existing schema
            # Our schema: title, summary, source, language, source_url, image_url, date, scraped_at
            if not incoming_df.empty:
                df = pd.DataFrame()
                df['title'] = incoming_df['title']
                df['summary'] = incoming_df.get('text', incoming_df.get('summary', ''))
                df['source'] = incoming_df.get('author', incoming_df.get('source', 'WorldNewsAPI'))
                df['language'] = incoming_df.get('language', 'en')
                df['source_url'] = incoming_df.get('url', '')
                df['image_url'] = incoming_df.get('image', '')
                df['date'] = incoming_df.get('publish_date', datetime.now().strftime('%Y-%m-%d'))
                df['scraped_at'] = datetime.now().isoformat()
                
                output_dir = "nepali_news_structured"
                
                # Deduplication logic
                # First, load existing titles or URLs to check for duplicates
                print(f"[{current_time}] Loading existing database to deduplicate...")
                try:
                    existing_df = pd.read_parquet(output_dir)
                    existing_urls = set(existing_df['source_url'].dropna())
                    existing_titles = set(existing_df['title'].dropna())
                    
                    # Filter out rows that are already in our database by URL or exact Title
                    original_count = len(df)
                    df = df[~df['source_url'].isin(existing_urls)]
                    df = df[~df['title'].isin(existing_titles)]
                    print(f"[{current_time}] Found {original_count} articles. Deduplicated: {len(df)} are new.")
                except Exception as e:
                    print(f"[{current_time}] No existing data found or error reading ({e}). Saving all {len(df)} articles.")
                
                if len(df) > 0:
                    # Format dates for partitioning
                    df['parsed_date'] = pd.to_datetime(df['date'], errors='coerce')
                    df['year'] = df['parsed_date'].dt.year.fillna(0).astype(int).astype(str).replace('0', 'unknown')
                    df = df.drop(columns=['parsed_date'])
                    df['source'] = df['source'].fillna('unknown_source').astype(str)
                    
                    batch_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_worldnews")
                    
                    # Save into the partitioned schema
                    for (source, year), group in df.groupby(['source', 'year']):
                        path = os.path.join(output_dir, f"source={source}", f"year={year}")
                        os.makedirs(path, exist_ok=True)
                        
                        filepath = os.path.join(path, f"update_{batch_id}.parquet")
                        group.to_parquet(filepath, index=False)
                        
                    print(f"[{current_time}] Successfully saved {len(df)} NEW articles to the structured schema.")
                else:
                    print(f"[{current_time}] No new articles to save. Everything is already up to date.")
                
                # Check Newest and Oldest dates overall
                try:
                    full_db = pd.read_parquet(output_dir)
                    full_db['parsed_date'] = pd.to_datetime(full_db['date'], errors='coerce')
                    min_date = full_db['parsed_date'].min()
                    max_date = full_db['parsed_date'].max()
                    print(f"[{current_time}] DATABASE TIMELINE -> Oldest news: {min_date.date()}, Newest news: {max_date.date()}")
                except Exception as e:
                    print(f"[{current_time}] Could not calculate timeline: {e}")
                
        else:
            print(f"[{current_time}] No articles found in the feed.")
            
    except Exception as e:
        print(f"[{current_time}] Failed to fetch updates: {e}")

if __name__ == "__main__":
    update_world_news()
