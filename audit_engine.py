from typing import final

from llm_service import LLMService


@final
class ExecutiveAuditEngine:
    def __init__(self, llm_client: LLMService): # Dependency Injection
        self.llm = llm_client

    def run_daily_briefing(self, raw_json_data: str) -> str:
        system_prompt = "You are a COO. Summarize KPIs in 3 blunt bullet points."
        
        summary = self.llm.generate_summary(
            system_prompt=system_prompt, 
            user_data=raw_json_data
        )
        return summary
