import json
from typing import Any, Protocol

# Hard limit to prevent blowing up the LLM context window with huge payloads
MAX_RESULT_CHARS = 8000

def serialize_tool_result(value: Any) -> str:
    """Serialize a tool result with a hard char budget so history stays small."""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
        
    if len(text) > MAX_RESULT_CHARS:
        return text[:MAX_RESULT_CHARS] + f"\n... [truncated {len(text) - MAX_RESULT_CHARS} chars. Refine your query.]"
    return text

class Toolkit(Protocol):
    """Protocol for a modular set of tools that an Agent can use."""
    
    def get_tools(self) -> list[dict[str, Any]]:
        """Return a list of Anthropic/OpenAI compatible tool schemas."""
        ...
        
    def execute(self, name: str, args: dict[str, Any]) -> str:
        """Execute the tool by name with arguments and return a serialized, capped string."""
        ...
