import os
from .base import LLMProvider

def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider()
    elif provider == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
