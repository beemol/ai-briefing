"""LLM backends — swap Claude for any OpenAI-compatible model.

The Agent only needs a tiny client surface: `.messages.create(**kwargs)`
that accepts Anthropic-shaped input and returns Anthropic-shaped output.
`OpenAIBackend` adapts that to the OpenAI Chat Completions API, so any
local or hosted server with that protocol works: Ollama
(http://localhost:11434/v1), LM Studio (http://localhost:1234/v1),
llama.cpp, vLLM, DeepSeek, Gemini, ...

Usage:

    llm = build_llm_client(
        backend="openai",
        api_key="local",                       # any value for local servers
        base_url="http://localhost:11434/v1",  # Ollama
        model="qwen2.5:14b",
    )
"""

import json
from itertools import count
from types import SimpleNamespace
from typing import Any, Protocol, final

from openai import OpenAI


class LLMClient(Protocol):
    """Interface the Agent uses to talk to an LLM (Anthropic-shaped).

    The agent calls `client.messages.create(**kwargs)` with Anthropic-style
    kwargs and expects an object with `.content` (blocks), `.stop_reason`
    and `.usage` — the exact shape the Anthropic SDK returns.
    """

    messages: Any


def _get(block: Any, key: str, default: Any = None) -> Any:
    """Read `key` from an SDK block that may be a dict or an attribute object."""
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


# Many local models (especially "coder" variants) don't implement the native
# tool_calls protocol — they print the call as JSON text instead. We teach
# them the format via the system prompt and parse it back here, so weak/
# coder models still work (native tool_calls are preferred when present).
def _tool_hint(tool_names: str) -> str:
    return (
        "When you need data, respond with a single JSON object and nothing else "
        + "(no markdown, no commentary) in this exact format:\n"
        + '{"name": "tool_name", "arguments": {"param": "value"}}\n'
        + f"Available tools: {tool_names}.\n"
    )


_json_call_seq = count(1)


def _try_parse_tool_call(text: str) -> dict[str, Any] | None:
    """Detect a JSON tool call that a model printed as plain text."""
    stripped = text.strip()
    if stripped.startswith("```"):  # strip ```json ... ``` fences
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name") or data.get("tool")
    args = data.get("arguments", data.get("args", {}))
    if not isinstance(name, str) or not name:
        return None
    if not isinstance(args, dict):
        args = {}
    return {"name": name, "arguments": args}


@final
class OpenAIBackend:
    """Adapter: Anthropic-shaped request <-> OpenAI Chat Completions API.

    Args:
        api_key:  any value for local servers; a real key for hosted endpoints.
        base_url: OpenAI-compatible endpoint root, e.g. "http://localhost:11434/v1".
        model:    model id the server knows, e.g. "qwen2.5:14b".
        client:   injectable OpenAI client (used in tests).
    """

    def __init__(
        self,
        api_key: str = "local",
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen2.5:14b",
        client: Any | None = None,
    ):
        self._client: Any = client or OpenAI(
            api_key=api_key, base_url=base_url, timeout=120
        )
        self._model: str = model
        self.messages = _MessagesWrapper(self)

    def create(self, **kwargs: Any) -> Any:
        """Translate an Anthropic-shaped request into an OpenAI request."""
        oai_messages: list[dict[str, Any]] = []

        system = kwargs.get("system")
        tools = kwargs.get("tools") or []
        if system:
            if isinstance(system, str):
                text = system
            else:
                text = "".join(_get(b, "text", "") for b in system)
            if tools:
                # Teach non-tool models the JSON protocol (and list tools).
                tool_names = ", ".join(t.get("name", "") for t in tools)
                text += "\n\n" + _tool_hint(tool_names)
            oai_messages.append({"role": "system", "content": text})

        for msg in kwargs.get("messages", []):
            role = msg.get("role")
            content = msg.get("content")
            if role == "user" and isinstance(content, list):
                # Anthropic tool_result blocks -> OpenAI tool messages.
                for block in content:
                    if _get(block, "type") == "tool_result":
                        oai_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": _get(block, "tool_use_id", ""),
                                "content": str(_get(block, "content", "")),
                            }
                        )
                    elif isinstance(block, str):
                        oai_messages.append({"role": "user", "content": block})
            elif role == "assistant" and isinstance(content, list):
                text_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                for block in content:
                    btype = _get(block, "type")
                    if btype == "text":
                        text_parts.append(str(_get(block, "text", "")))
                    elif btype == "tool_use":
                        tool_calls.append(
                            {
                                "id": _get(block, "id", ""),
                                "type": "function",
                                "function": {
                                    "name": _get(block, "name", ""),
                                    "arguments": json.dumps(
                                        _get(block, "input", {}), ensure_ascii=False
                                    ),
                                },
                            }
                        )
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(text_parts) or None,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                oai_messages.append(assistant_msg)
            else:
                oai_messages.append({"role": role, "content": str(content)})

        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
            for tool in (kwargs.get("tools") or [])
        ]

        params: dict[str, Any] = {
            "model": self._model,
            "messages": oai_messages,
        }
        if kwargs.get("max_tokens") is not None:
            params["max_tokens"] = kwargs["max_tokens"]
        if oai_tools:
            params["tools"] = oai_tools
        if kwargs.get("temperature") is not None:
            params["temperature"] = kwargs["temperature"]

        resp = self._client.chat.completions.create(**params)
        return _to_anthropic_shape(resp)


@final
class _MessagesWrapper:
    """Exposes `.create(**kwargs)` so the backend looks like Anthropic's client."""

    def __init__(self, backend: OpenAIBackend):
        self._backend: OpenAIBackend = backend

    def create(self, **kwargs: Any) -> Any:
        return self._backend.create(**kwargs)


def _to_anthropic_shape(resp: Any) -> Any:
    """Translate an OpenAI response into the Anthropic-shaped object the Agent expects."""
    choice = resp.choices[0]
    message = choice.message
    blocks: list[Any] = []

    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        for tc in tool_calls:
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            blocks.append(
                SimpleNamespace(
                    type="tool_use",
                    id=tc.id,
                    name=tc.function.name,
                    input=arguments,
                )
            )
        stop_reason = "tool_use"
    else:
        text = message.content or ""
        parsed = _try_parse_tool_call(text)
        if parsed is not None:
            blocks.append(
                SimpleNamespace(
                    type="tool_use",
                    id=f"json_call_{next(_json_call_seq)}",
                    name=parsed["name"],
                    input=parsed["arguments"],
                )
            )
            stop_reason = "tool_use"
        else:
            if text:
                blocks.append(SimpleNamespace(type="text", text=text))
            stop_reason = (
                "max_tokens" if choice.finish_reason == "length" else "end_turn"
            )

    usage = getattr(resp, "usage", None)
    return SimpleNamespace(
        content=blocks,
        stop_reason=stop_reason,
        usage=SimpleNamespace(
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            cache_read_input_tokens=0,  # local servers have no prompt cache
        ),
    )


def build_llm_client(
    backend: str,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> LLMClient:
    """Create the LLM client for the given backend name ("anthropic" | "openai")."""
    if backend == "openai":
        return OpenAIBackend(
            api_key=api_key or "local",
            base_url=base_url or "http://localhost:11434/v1",
            model=model or "qwen2.5:14b",
        )
    from anthropic import Anthropic

    return Anthropic(api_key=api_key, timeout=120)
