# llm_service.py
from typing import Protocol, List, Dict, Any

class LLMService(Protocol):
    
    def generate_summary(self, system_prompt: str, user_data: str) -> str:
        """Takes a system prompt and user data, returns a generated text summary."""
        ...