from google import genai
from google.genai import types
from dotenv import load_dotenv
from pathlib import Path
import os
import json
import re
import time
import yaml
import numpy as np
import logging

load_dotenv()
logger = logging.getLogger(__name__)

#setup multiple keys at the top
API_KEYS = [os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_API_KEY_2"),os.getenv("GEMINI_API_KEY_3")]
API_KEYS = [k for k in API_KEYS if k]  # Filter out empty keys
CURRENT_KEY_INDEX = 0

def get_gemini_client():
    if not API_KEYS:
        logger.warning("No GEMINI_API_KEY set in environment; returning None")
        return None
    return genai.Client(api_key=API_KEYS[CURRENT_KEY_INDEX])

def get_gemini_embedding(client, text: str) -> list:
    global CURRENT_KEY_INDEX
    for _ in range(len(API_KEYS)):

        try:
            active_client = genai.Client(api_key=API_KEYS[CURRENT_KEY_INDEX])

            result = active_client.models.embed_content(
                model=os.getenv("GEMINI_EMBED_MODEL"),
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            logger.debug("Embedding generated.")
            if result.embeddings:
                embedding_values = result.embeddings[0].values
                # Normalize embedding to unit vector
                normed_embedding = np.array(embedding_values) / np.linalg.norm(embedding_values)
                return normed_embedding.tolist()

        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(API_KEYS)
                logger.warning(
                    "Embedding rate limit hit. Switched to key index: %s",
                    CURRENT_KEY_INDEX,
                )
                continue
            logger.error("Failed to generate embedding: %s", e)
            break
    return [0.0] * 768



def call_with_retry(gemini_client, model, prompt, max_retries=3, backoff_factor=2):
    global CURRENT_KEY_INDEX

    for i in range(max_retries):
        active_client = genai.Client(api_key=API_KEYS[CURRENT_KEY_INDEX])
        try:
            response = active_client.models.generate_content(
                model=model,
                contents=prompt,
            )
            return response
        except Exception as e:
            # Check if error indicates rate limiting/resource exhaustion
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(API_KEYS)
                logger.warning(
                    "Attempt %s: key exhausted. Switched to key index: %s",
                    i + 1,
                    CURRENT_KEY_INDEX,
                )
                
                # If we've rotated through all keys, wait a bit
                if (i + 1) % len(API_KEYS) == 0:
                    wait_time = backoff_factor ** (i + 1)
                    time.sleep(wait_time)
                continue
            else:
                logger.error("Attempt %s: failed to generate content: %s", i + 1, e)
                time.sleep(backoff_factor ** (i + 1))
                
    raise Exception("Max retries exceeded for all Gemini API keys.")



def load_prompt(file_name, **kwargs):
    try:
        # Get the directory of the current script
        base_dir = Path(__file__).parent
        file_path = base_dir / "prompts" / file_name

        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as file:
            prompt_data = yaml.safe_load(file)
            
            if not prompt_data or 'prompt' not in prompt_data:
                raise ValueError(f"Invalid prompt format in {file_name}")
                
            return prompt_data['prompt'].format(**kwargs)
            
    except Exception as e:
        logger.error("Error loading prompt %s: %s", file_name, e)
        raise

def extract_json_from_markdown(text: str) -> str:
    """
    Extracts JSON content from a Markdown-formatted string.
    If the text is wrapped in triple backticks, this function removes them.
    """
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def summarize_and_score_article(content, gemini_client,  likes_count=0, comments_count=0):
    
    # Define weights for likes and comments
    likes_weight = 0.4
    comments_weight = 0.6
    max_likes = 1000  # Adjust based on your data
    max_comments = 500  # Adjust based on your data

    # Normalize likes and comments
    normalized_likes = min(likes_count / max_likes, 1.0)
    normalized_comments = min(comments_count / max_comments, 1.0)
    engagement_score = (likes_weight * normalized_likes) + (comments_weight * normalized_comments)

    prompt = load_prompt('summarize_and_score_article.yaml', content=content)
    try:
        response = call_with_retry(
            gemini_client,
            model=os.getenv("GEMINI_GENERATE_MODEL"),
            prompt=prompt
        )
        raw_output = response.text.strip()
        json_str = extract_json_from_markdown(raw_output)
        result = json.loads(json_str)

        summary = result.get("summary", "")
        impact_score = min(result.get("impact_score", 0) + (engagement_score * 0.2), 1.0)
        relevance_score = min(result.get("relevance_score", 0) + (engagement_score * 0.1), 1.0)

        return summary, impact_score, relevance_score,

    except Exception as e:
        logger.error("Failed to summarize and score article: %s", e)
        return "", 0.0,0.0
    
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse JSON in summarize_and_score_article")
        return "", 0.0, 0.0


def get_trending_topics(news_articles, gemini_client):
    if not news_articles:
        logger.info("No articles provided for trending topics analysis")
        return []

    # Sort articles by relevance and impact
    sorted_articles = sorted(news_articles, 
                           key=lambda x: (x.get("relevance_score", 0), x.get("impact_score", 0)), 
                           reverse=True)
    
    # Use all available articles (no minimum count requirement)
    combined_content = "\n".join([
        f"Article {i+1} (Relevance: {article.get('relevance_score', 0):.2f}, Impact: {article.get('impact_score', 0):.2f}):\n"
        f"{article.get('summary', '')}\n"
        for i, article in enumerate(sorted_articles)
    ])
    
    prompt = load_prompt('get_trending_topics.yaml', combined_content=combined_content)
    try:
        response = call_with_retry(
            gemini_client,
            model=os.getenv("GEMINI_GENERATE_MODEL"),
            prompt=prompt
        )

        # Extract and clean JSON response
        json_str = response.text.strip()
        json_str = re.sub(r"```(json)?\s*", "", json_str)  
        json_str = re.sub(r"\s*```", "", json_str)
        
        trending_topics = json.loads(json_str)
        
        # Ensure we always return a list
        if isinstance(trending_topics, dict):
            return [trending_topics]
        return trending_topics
        
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse JSON response for trending topics: %s", e)
        return []
    except Exception as e:
        logger.error("Error generating trending topics: %s", e)
        return []
    
def extract_companies_and_sectors(content, gemini_client, sector_names, nepse_companies):
    # Prepare company reference string with both names and symbols
    company_ref = "\n".join([f"{name} (Symbol: {symbol})" for name, symbol in nepse_companies])
    
    prompt = load_prompt('extract_companies.yaml',sector_list=", ".join(sector_names),company_reference=company_ref,content=content)

    
    try:
        logger.debug("Sending content to Gemini for analysis...")
        response = call_with_retry(gemini_client, os.getenv("GEMINI_GENERATE_MODEL"), prompt)
        logger.debug("Received Gemini response for company/sector extraction")
        
        json_str = extract_json_from_markdown(response.text.strip())
        result = json.loads(json_str)
        
        # Enhanced validation
        valid_sectors = []
        valid_companies = []
        
        # Sector validation (case insensitive)
        sector_lower_map = {s.lower(): s for s in sector_names}
        for sector in result.get("affected_sectors", []):
            normalized = sector.strip().lower()
            if normalized in sector_lower_map:
                valid_sectors.append(sector_lower_map[normalized])
        
        # Company validation - check both names and symbols
        company_map = {(name.lower(), symbol.lower()) for name, symbol in nepse_companies}
        mentioned = result.get("mentioned_companies", [])
        
        # Deduplicate while preserving order
        seen = set()
        for item in mentioned:
            item_lower = item.strip().lower()
            
            # Check if matches any name or symbol exactly
            for name, symbol in company_map:
                if item_lower == name or item_lower == symbol:
                    if symbol not in seen:  # Use symbol as deduplication key
                        seen.add(symbol)
                        valid_companies.append(symbol if item_lower == symbol else item)
                    break
            else:
                # Try fuzzy matching if no exact match
                fuzzy_match = fuzzy_match_company(item, nepse_companies)
                if fuzzy_match and fuzzy_match not in seen:
                    logger.debug("Fuzzy matched %s to %s", item, fuzzy_match)
                    seen.add(fuzzy_match)
                    valid_companies.append(fuzzy_match)
        
        logger.debug(
            "Validated extraction results. sectors=%s companies=%s",
            len(valid_sectors),
            len(valid_companies),
        )
        return valid_sectors, valid_companies
        
    except Exception as e:
        logger.error("Error in company/sector extraction: %s", e)
        return [], []
    
from fuzzywuzzy import fuzz, process

def fuzzy_match_company(name, nepse_companies, threshold=85):
    # Create a combined list of names and symbols
    choices = []
    for company, symbol in nepse_companies:
        choices.append(company)
        choices.append(symbol)
    
    # Find best match using process.extractOne
    best_match = process.extractOne(name, choices, scorer=fuzz.token_set_ratio)
    
    if best_match and best_match[1] >= threshold:
        matched_text = best_match[0]
        # Return the symbol if available
        for company, symbol in nepse_companies:
            if matched_text == company or matched_text == symbol:
                return symbol
    return None


def generate_watchlist_insight(user_id, watched_companies, articles, gemini_client):
    company_list = ", ".join([f"{c['symbol']} ({c['name']})" for c in watched_companies])
    
    prompt = load_prompt('watchlist_insight.yaml',
                    company_list=", ".join(f"{c['symbol']} ({c['name']})" for c in watched_companies),
                    articles=json.dumps(articles[:3]))
    try:
        response = call_with_retry(gemini_client, os.getenv("GEMINI_GENERATE_MODEL"), prompt)
        return json.loads(extract_json_from_markdown(response.text))
    except Exception as e:
        logger.error("Insight generation failed: %s", e)
        return None