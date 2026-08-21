from collections.abc import Sequence
from typing import Any, cast, final

from anthropic import Anthropic
from anthropic.types import Message, MessageParam, ToolParam

from .config import AgentConfig
from .toolkit import Toolkit


@final
class Agent:
    """Agnostic LLM loop that manages conversation history and delegates to Toolkits."""

    def __init__(
        self,
        claude: Anthropic,
        toolkits: Sequence[Toolkit],
        config: AgentConfig | None = None,
    ):
        self._claude = claude
        self._config = config or AgentConfig()
        self._toolkits = toolkits

        self._tools: list[dict[str, object]] = []
        self._tool_map: dict[str, Toolkit] = {}

        # Aggregate all schemas and build a routing map
        for tk in toolkits:
            for tool in tk.get_tools():
                self._tools.append(tool)
                self._tool_map[tool["name"]] = tk

        self._system_prompt = self._config.system_prompt

    def _call_llm(self, messages: list[dict[str, object]]) -> Message:
        """Send the conversation with the configured model and knobs."""
        kwargs: dict[str, Any] = {
            "model": self._config.model.value,
            "max_tokens": self._config.max_tokens,
            "system": self._system_prompt,
            "tools": cast(list[ToolParam], self._tools),
            "messages": cast(list[MessageParam], messages),
        }
        if self._config.temperature is not None:
            kwargs["temperature"] = self._config.temperature
        return self._claude.messages.create(**kwargs)

    def ask(self, question: str) -> str:
        """Run a conversational loop until the LLM produces a final text answer."""
        messages: list[dict[str, object]] = [{"role": "user", "content": question}]

        for _ in range(self._config.max_steps):
            resp = self._call_llm(messages)

            messages.append({"role": "assistant", "content": resp.content})

            tool_results: list[dict[str, object]] = []
            for block in resp.content:
                if block.type == "tool_use":
                    tk = self._tool_map.get(block.name)
                    if not tk:
                        res_str = f"Error: Tool '{block.name}' not found."
                    else:
                        try:
                            # execute() already handles serialization and capping
                            res_str = tk.execute(block.name, block.input or {})
                        except Exception as exc:  # noqa: BLE001 - keep the loop alive on tool errors
                            res_str = f"Error executing tool: {exc}"

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": res_str,
                        }
                    )

            if not tool_results:
                # No tools called -> the LLM provided a final text answer
                text = "".join(
                    block.text for block in resp.content if block.type == "text"
                )
                if resp.stop_reason == "max_tokens":
                    text += (
                        "\n\n⚠️ Ответ обрезан лимитом max_tokens — "
                        "увеличьте --max-tokens (ответ неполный)."
                    )
                return text

            messages.append({"role": "user", "content": tool_results})

        return "Не удалось получить ответ (превышен лимит шагов)."
