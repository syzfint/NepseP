import os
import requests
import pandas as pd
from datetime import datetime

def update_dataset():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] Fetching today's latest news...")
    
    url = "https://huggingface.co/datasets/thegauravgiri/nepali-news-dataset/raw/main/data/today.json"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if "articles" in data and data["articles"]:
            df = pd.DataFrame(data["articles"])
            output_dir = "nepali_news_structured"
            
            # Extract root level metadata and add to dataframe
            df['date'] = data.get('date', datetime.now().strftime('%Y-%m-%d'))
            df['scraped_at'] = data.get('scraped_at', datetime.now().isoformat())
            
            # Format dates for partitioning
            df['parsed_date'] = pd.to_datetime(df['date'], errors='coerce')
            df['year'] = df['parsed_date'].dt.year.fillna(0).astype(int).astype(str).replace('0', 'unknown')
            df = df.drop(columns=['parsed_date'])
            df['source'] = df['source'].fillna('unknown_source').astype(str)
            
            # Generate a unique filename for this batch to prevent overwriting
            batch_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            
            # Save into the partitioned schema
            for (source, year), group in df.groupby(['source', 'year']):
                path = os.path.join(output_dir, f"source={source}", f"year={year}")
                os.makedirs(path, exist_ok=True)
                
                filepath = os.path.join(path, f"update_{batch_id}.parquet")
                group.to_parquet(filepath, index=False)
                
            print(f"[{current_time}] Successfully fetched and saved {len(df)} new articles.")
            print(f"Sources updated: {', '.join(data['sources'])}")
        else:
            print(f"[{current_time}] No articles found in the feed.")
            
    except Exception as e:
        print(f"[{current_time}] Failed to fetch updates: {e}")

if __name__ == "__main__":
    update_dataset()
