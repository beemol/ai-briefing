import os

from llm_service import LLMService
from providers.deepseek_client import DeepSeekService
from providers.gemini_service import GeminiService


def get_llm_service() -> LLMService:
    """Factory: resolve the active LLM service from the LLM_PROVIDER env var."""
    provider = os.getenv("LLM_PROVIDER", "deepseek").lower()

    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is missing.")
        return DeepSeekService(api_key)

    elif provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing.")
        return GeminiService(api_key)

    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
