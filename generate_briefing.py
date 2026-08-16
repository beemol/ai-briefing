# generate_briefing.py
import os
from dotenv import load_dotenv

from data_fetcher import get_housing_kpis
from llm_service import LLMService
from providers.deepseek_client import DeepSeekService
#from providers.gemini_client import GeminiService

load_dotenv()

SYSTEM_SOP = """
You are the Chief Operations Officer for a housing management company.
Every morning, you review the daily KPI data and write a brief, 3-bullet-point summary for the CEO.

Rules for the summary:
- If overdue tickets > 0, highlight them as an immediate action item.
- Do not use corporate jargon. Be blunt and direct.
- Always bold the critical flags.
"""

def get_llm_provider() -> LLMService:
    """Factory function to resolve the active LLM service based on environment variables."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is missing.")
        return DeepSeekService(api_key=api_key)
        
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def run_daily_audit(llm_service: LLMService) -> None:
    print("Fetching metrics from Power BI...")
    daily_data = get_housing_kpis()
    
    print("Generating report via active LLM provider...")
    # Clean call against the abstract protocol signature
    briefing = llm_service.generate_summary(
        system_prompt=SYSTEM_SOP,
        user_data=daily_data
    )
    
    print("\n--- EXECUTIVE BRIEFING ---\n")
    print(briefing)
    print("\n--------------------------")


if __name__ == "__main__":
    # Dependency Injection
    service = get_llm_provider()
    run_daily_audit(llm_service=service)