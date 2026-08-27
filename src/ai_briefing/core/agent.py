from collections.abc import Sequence
from typing import Any, cast, final

from anthropic.types import Message, MessageParam

from .backends import LLMClient
from .config import AgentConfig
from .toolkit import Toolkit


@final
class Agent:
    """Agnostic LLM loop that manages conversation history and delegates to Toolkits."""

    def __init__(
        self,
        claude: LLMClient,
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

    def _with_cached_tail(
        self,
        messages: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Return a copy of `messages` with a cache breakpoint on the last block.

        The last message when the LLM is called is either the user question
        (a string, on step 1) or the accumulated tool results (a list of
        blocks, on later steps). Tool results are the large, stable prefix
        that gets re-sent on every step, so marking the tail lets Anthropic
        reuse them across steps instead of re-processing them.

        String content is left untouched: it is small, and converting it to a
        list would change the message shape that the OpenAI adapter relies on.
        """
        if not messages:
            return messages
        last = messages[-1]
        content = last.get("content")
        if not isinstance(content, list) or not content:
            return messages

        last_copy = dict(last)
        blocks = list(content)
        tail = blocks[-1]
        if not isinstance(tail, dict):
            return messages
        blocks[-1] = {
            **tail,
            "cache_control": {"type": self._config.cache_type.value},
        }
        last_copy["content"] = blocks
        return messages[:-1] + [last_copy]

    def _call_llm(self, messages: list[dict[str, object]]) -> Message:
        """Send the conversation with the configured model and knobs.

        Three stable prefixes are marked with Anthropic prompt caching
        (cache_control) so the API re-reads them from cache (~90% cheaper)
        instead of re-processing them on every round trip:
          1. the system prompt,
          2. the tool definitions,
          3. the accumulated conversation history (tool results).
        """
        # Shallow copies so adding cache_control never mutates self._tools.
        tools: list[dict[str, Any]] = [dict(t) for t in self._tools]
        if tools:
            # Only the LAST tool in the list can carry cache_control.
            tools[-1]["cache_control"] = {"type": self._config.cache_type.value}

        kwargs: dict[str, Any] = {
            "model": self._config.model_name or self._config.model.value,
            "system": [
                {
                    "type": "text",
                    "text": self._system_prompt,
                    "cache_control": {"type": self._config.cache_type.value},
                }
            ],
            "tools": tools,
            "messages": cast(
                list[MessageParam], self._with_cached_tail(messages)
            ),
        }
        if self._config.max_tokens is not None:
            kwargs["max_tokens"] = self._config.max_tokens
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

        # Preload schema/context tools so weak models don't need to discover
        # the data layout themselves (they tend to ask for clarification).
        for name in self._config.preload_tools:
            tk = self._tool_map.get(name)
            if tk is None:
                continue
            try:
                content = tk.execute(name, {})
            except Exception as exc:  # noqa: BLE001 - preload must never crash ask
                content = f"Ошибка предзагрузки {name}: {exc}"
            self._step(f"предзагрузка: {name}")
            messages.append(
                {"role": "user", "content": f"[данные из {name}]\n{content}"}
            )

        limit = self._config.max_steps

        step = 0
        while limit is None or step < limit:
            step += 1
            label = str(limit) if limit is not None else "∞"
            self._step(f"Шаг {step}/{label}: вызов модели…")
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
