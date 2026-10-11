from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def summarize_and_score(self, content: str) -> tuple[str, float, float]:
        pass

    @abstractmethod
    def extract_companies_and_sectors(self, content: str, sector_names: list, nepse_companies: list) -> tuple[list, list]:
        pass

    @abstractmethod
    def get_trending_topics(self, articles: list) -> list:
        pass
