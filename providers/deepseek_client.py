from openai import OpenAI

from llm_service import LLMService


class DeepSeekService(LLMService):
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"

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
            raise RuntimeError("DeepSeek returned an empty response (content is None)")
        return content
