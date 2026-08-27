"""Shared agent wiring for long-running processes (server, Telegram bot).

The CLI builds its own Agent from argparse flags; the server and the bot both
read the same environment variables, so they share this builder to avoid
duplicating the wiring of Bitrix24 + Power BI + the LLM backend.
"""

import logging
import os
from collections.abc import Callable

from ai_briefing.core import Agent, AgentConfig, build_llm_client
from ai_briefing.domain.bitrix import BitrixClient, BitrixTools
from ai_briefing.domain.config import LEASING_SYSTEM_PROMPT
from ai_briefing.domain.powerbi import PowerBIClient, PowerBITools, get_access_token

logger = logging.getLogger("ai_briefing.factory")


def _log_usage(input_tokens: int, output_tokens: int, cached: int) -> None:
    logger.info("LLM usage: input=%d output=%d cached=%d", input_tokens, output_tokens, cached)


def build_agent(
    *,
    step_callback: Callable[[str], None] | None = None,
    usage_callback: Callable[[int, int, int], None] | None = None,
) -> Agent:
    """Build the agent from environment variables (clear error if misconfigured)."""
    backend = os.getenv("LLM_BACKEND", "anthropic").lower()

    missing: list[str] = []
    if not os.getenv("BITRIX_WEBHOOK"):
        missing.append("BITRIX_WEBHOOK")
    if backend == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    for name in ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET"):
        if not os.getenv(name):
            missing.append(name)
    if missing:
        raise RuntimeError("Missing required env vars: " + ", ".join(missing))

    llm = build_llm_client(
        backend=backend,
        api_key=os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("LLM_API_KEY")
        or "local",
        base_url=os.getenv("LLM_BASE_URL", ""),
        model=os.getenv("LLM_MODEL", ""),
    )

    return Agent(
        llm,
        [
            BitrixTools(BitrixClient(os.getenv("BITRIX_WEBHOOK", ""))),
            PowerBITools(PowerBIClient(get_access_token)),
        ],
        config=AgentConfig(
            system_prompt=LEASING_SYSTEM_PROMPT,
            model_name=os.getenv("LLM_MODEL") if backend != "anthropic" else None,
            # Local models don't explore the schema themselves — give it to them.
            preload_tools=("get_data_guide",) if backend != "anthropic" else (),
            step_callback=step_callback,
            usage_callback=usage_callback or _log_usage,
        ),
    )
