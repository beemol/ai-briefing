from collections.abc import Sequence
from typing import Any, cast, final

from anthropic import Anthropic
from anthropic.types import Message, MessageParam

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
        """Send the conversation with the configured model and knobs.

        The system prompt and tool definitions are marked with Anthropic
        prompt caching (cache_control): they are identical on every step, so
        the API re-reads them from cache (~90% cheaper for those tokens)
        instead of processing them anew on each round trip.
        """
        # Shallow copies so adding cache_control never mutates self._tools.
        tools: list[dict[str, Any]] = [dict(t) for t in self._tools]
        if tools:
            # Only the LAST tool in the list can carry cache_control.
            tools[-1]["cache_control"] = {"type": "ephemeral"}

        kwargs: dict[str, Any] = {
            "model": self._config.model.value,
            "max_tokens": self._config.max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": self._system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tools": tools,
            "messages": cast(list[MessageParam], messages),
        }
        if self._config.temperature is not None:
            kwargs["temperature"] = self._config.temperature
        resp = self._claude.messages.create(**kwargs)
        usage = resp.usage
        if self._config.usage_callback is not None and usage is not None:
            self._config.usage_callback(
                usage.input_tokens,
                usage.output_tokens,
                getattr(usage, "cache_read_input_tokens", 0),
            )
        return resp

    @property
    def tools(self) -> list[dict[str, object]]:
        """Anthropic-compatible tool schemas (for registration / external use)."""
        return self._tools

    def _step(self, message: str) -> None:
        """Report progress to the configured callback (UI feedback)."""
        if self._config.step_callback is not None:
            self._config.step_callback(message)

    def ask(self, question: str) -> str:
        """Run a conversational loop until the LLM produces a final text answer."""
        messages: list[dict[str, object]] = [{"role": "user", "content": question}]
        total = self._config.max_steps

        for step in range(1, total + 1):
            self._step(f"Шаг {step}/{total}: вызов модели…")
            resp = self._call_llm(messages)

            messages.append({"role": "assistant", "content": resp.content})

            tool_results: list[dict[str, object]] = []
            for block in resp.content:
                if block.type == "tool_use":
                    tk = self._tool_map.get(block.name)
                    if not tk:
                        res_str = f"Error: Tool '{block.name}' not found."
                    else:
                        self._step(f"  инструмент: {block.name}")
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
                self._step("Ответ получен.")
                return text

            messages.append({"role": "user", "content": tool_results})

        # Steps exhausted: ask the model to summarize what it already found,
        # so the user gets a useful partial answer instead of a terse failure.
        self._step("Лимит шагов: запрашиваю промежуточный итог…")
        messages.append(
            {
                "role": "user",
                "content": (
                    "Лимит шагов исчерпан. Кратко ответь на исходный вопрос: "
                    "что уже удалось выяснить, и какие данные/запросы ещё нужны "
                    "для полного ответа."
                ),
            }
        )
        resp = self._call_llm(messages)
        return "".join(
            block.text for block in resp.content if block.type == "text"
        ) or "Не удалось получить ответ — лимит шагов исчерпан."
