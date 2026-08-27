from typing import final, override

from openai import OpenAI

from ai_briefing.legacy.llm_service import LLMService


@final
class GeminiService(LLMService):
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        self.model = "gemini-3.7-flash"

    @override
    def generate_summary(self, system_prompt: str, user_data: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Data: {user_data}"}
            ]
        )
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Gemini returned an empty response (content is None)")
        return content
