"""Generic, reusable agent framework — nothing here is leasing-specific.

These modules know how to run an LLM tool-calling loop, cap results, and
talk to different backends (Anthropic / OpenAI-compatible), but they have no
idea what Bitrix24 or Power BI are. See ai_briefing.domain for that.
"""

from ai_briefing.core.agent import Agent
from ai_briefing.core.backends import LLMClient, OpenAIBackend, build_llm_client
from ai_briefing.core.config import AgentConfig, AgentModel, CacheType
from ai_briefing.core.toolkit import Toolkit, serialize_tool_result

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentModel",
    "CacheType",
    "LLMClient",
    "OpenAIBackend",
    "Toolkit",
    "build_llm_client",
    "serialize_tool_result",
]
