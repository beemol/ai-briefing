import json
from typing import cast

from anthropic import Anthropic
from anthropic.types import MessageParam, ToolParam

from toolkit import Toolkit


class Agent:
    """Agnostic LLM loop that manages conversation history and delegates to Toolkits."""

    def __init__(
        self,
        claude: Anthropic,
        toolkits: list[Toolkit],
        model: str = "claude-3-7-sonnet-20250219",
    ):
        self._claude = claude
        self._model = model
        self._toolkits = toolkits

        self._tools: list[dict[str, object]] = []
        self._tool_map: dict[str, Toolkit] = {}

        # Aggregate all schemas and build a routing map
        for tk in toolkits:
            for tool in tk.get_tools():
                self._tools.append(tool)
                self._tool_map[tool["name"]] = tk

        self._system_prompt = (
            "You are an assistant for a truck-leasing company. "
            "Use tools to answer questions about leasing leads (Bitrix24) or report data (Power BI). "
            "Prefer counts and aggregations over raw rows; never request full tables. "
            "Call get_powerbi_schema to discover tables, get_table_schema for one table's columns, "
            "then run_dax_query with TOPN or SUMMARIZECOLUMNS. "
            "Answer concisely in Russian."
        )

    def ask(self, question: str) -> str:
        """Run a conversational loop until the LLM produces a final text answer."""
        messages: list[dict[str, object]] = [{"role": "user", "content": question}]

        for _ in range(6):
            resp = self._claude.messages.create(
                model=self._model,
                max_tokens=1024,
                system=self._system_prompt,
                tools=cast(list[ToolParam], self._tools),
                messages=cast(list[MessageParam], messages),
            )

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
                        except Exception as exc:
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
                return "".join(
                    block.text for block in resp.content if block.type == "text"
                )

            messages.append({"role": "user", "content": tool_results})

        return "Не удалось получить ответ (превышен лимит шагов)."
