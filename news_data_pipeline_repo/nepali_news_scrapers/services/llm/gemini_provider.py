from .base import LLMProvider
from nepali_news_scrapers.services.gemini_client import (
    get_gemini_client, get_gemini_embedding,
    summarize_and_score_article, extract_companies_and_sectors,
    get_trending_topics, call_with_retry
)

class GeminiProvider(LLMProvider):
    def __init__(self):
        self.client = get_gemini_client()

    def generate(self, prompt: str) -> str:
        response = call_with_retry(self.client, ..., prompt)
        return response.text

    def embed(self, text: str) -> list[float]:
        return get_gemini_embedding(self.client, text)

    def summarize_and_score(self, content: str):
        return summarize_and_score_article(content, self.client)

    def extract_companies_and_sectors(self, content, sector_names, nepse_companies):
        return extract_companies_and_sectors(content, self.client, sector_names, nepse_companies)

    def get_trending_topics(self, articles: list) -> list:
        return get_trending_topics(articles, self.client)
