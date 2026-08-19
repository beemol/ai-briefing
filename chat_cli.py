import json
import os
import sys
from typing import cast

from anthropic import Anthropic
from anthropic.types import MessageParam, ToolParam
from dotenv import load_dotenv

from bitrix_client import BitrixClient
from bitrix_tools import BitrixTools

_ = load_dotenv()

MODEL = "claude-sonnet-4-5"

TOOLS: list[dict[str, object]] = [
    {
        "name": "leads_by_stage",
        "description": (
            "List leasing leads currently in a given pipeline stage. "
            "Example stage ids: TS_ISSUED, SECURITY_COUNCIL_REFUSAL, "
            "APPLICATION_DIRECT_ADVANCE, FAIL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "stage_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["stage_id"],
        },
    },
    {
        "name": "count_in_stage",
        "description": "Count how many leasing leads are in a given pipeline stage.",
        "input_schema": {
            "type": "object",
            "properties": {"stage_id": {"type": "string"}},
            "required": ["stage_id"],
        },
    },
    {
        "name": "search_by_inn",
        "description": "Find leasing leads by the Russian tax id (INN).",
        "input_schema": {
            "type": "object",
            "properties": {"inn": {"type": "string"}},
            "required": ["inn"],
        },
    },
    {
        "name": "lead_details",
        "description": "Get full details for one leasing lead by its numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "integer"}},
            "required": ["item_id"],
        },
    },
]


def run_tool(tools: BitrixTools, name: str, args: dict[str, object]) -> object:
    if name == "leads_by_stage":
        return tools.leads_by_stage(
            str(args.get("stage_id") or ""),
            cast(int, args.get("limit") or 20),
        )
    if name == "count_in_stage":
        return tools.count_in_stage(str(args.get("stage_id") or ""))
    if name == "search_by_inn":
        return tools.search_by_inn(str(args.get("inn") or ""))
    if name == "lead_details":
        return tools.lead_details(cast(int, args.get("item_id") or 0))
    raise ValueError(f"Unknown tool: {name}")


def ask(claude: Anthropic, tools: BitrixTools, question: str) -> str:
    messages: list[dict[str, object]] = [{"role": "user", "content": question}]

    for _ in range(6):
        resp = claude.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=(
                "You are an assistant for a truck-leasing company. "
                "Use the provided tools to answer questions about leasing leads in Bitrix24. "
                "Answer concisely in Russian."
            ),
            tools=cast(list[ToolParam], TOOLS),
            messages=cast(list[MessageParam], messages),
        )

        messages.append({"role": "assistant", "content": resp.content})

        tool_results: list[dict[str, object]] = []
        for block in resp.content:
            if block.type == "tool_use":
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(
                            run_tool(tools, block.name, block.input or {}),
                            ensure_ascii=False,
                            default=str,
                        ),
                    }
                )

        if not tool_results:
            return "".join(block.text for block in resp.content if block.type == "text")

        messages.append({"role": "user", "content": tool_results})

    return "Не удалось получить ответ."


def main() -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    webhook = os.getenv("BITRIX_WEBHOOK")
    if not api_key or not webhook:
        raise SystemExit("Missing required env vars: ANTHROPIC_API_KEY, BITRIX_WEBHOOK")

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise SystemExit("Usage: venv/bin/python chat_cli.py 'your question'")

    claude = Anthropic(api_key=api_key)
    tools = BitrixTools(BitrixClient(webhook))

    print(ask(claude, tools, question))


if __name__ == "__main__":
    main()
