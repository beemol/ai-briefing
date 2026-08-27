from typing import Protocol


class LLMService(Protocol):
    
    def generate_summary(self, system_prompt: str, user_data: str) -> str:
        """Takes a system prompt and user data, returns a generated text summary."""
        ...
