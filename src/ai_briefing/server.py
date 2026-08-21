"""FastAPI backend for the AI Briefing agent.

Endpoints:
    GET  /health  — liveness probe
    GET  /tools   — Anthropic-compatible tool schemas (for Claude.ai Actions)
    POST /ask     — {"question": "..."} -> {"answer": "..."}

Run locally:
    python -m uvicorn ai_briefing.server:app --reload
"""

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_briefing.agent import Agent, AgentConfig
from ai_briefing.bitrix import BitrixClient, BitrixTools
from ai_briefing.powerbi import PowerBIClient, PowerBITools, get_access_token

logger = logging.getLogger("ai_briefing.server")

app = FastAPI(
    title="AI Briefing API",
    description="Live Q&A over Bitrix24 + Power BI for the leasing business.",
    version="0.1.0",
)

# POC: allow any origin. Server-to-server consumers (Claude Actions, Telegram)
# don't need CORS at all; a future web UI would. Tighten before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent: Agent | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str


def build_agent() -> Agent:
    """Build the agent from environment variables (clear error if misconfigured)."""
    from anthropic import Anthropic  # lazy import: /health works even without it

    required = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "BITRIX_WEBHOOK": os.getenv("BITRIX_WEBHOOK"),
        "TENANT_ID": os.getenv("TENANT_ID"),
        "CLIENT_ID": os.getenv("CLIENT_ID"),
        "CLIENT_SECRET": os.getenv("CLIENT_SECRET"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Server not configured: missing env vars " + ", ".join(missing)
        )

    agent = Agent(
        Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""), timeout=120),
        [
            BitrixTools(BitrixClient(os.getenv("BITRIX_WEBHOOK", ""))),
            PowerBITools(PowerBIClient(get_access_token())),
        ],
        config=AgentConfig(
            usage_callback=lambda input_tokens, output_tokens, cached: logger.info(
                "LLM usage: input=%d output=%d cached=%d",
                input_tokens,
                output_tokens,
                cached,
            ),
        ),
    )
    return agent


def get_agent() -> Agent:
    """Build once, reuse for all requests (agent is stateless between asks)."""
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tools")
def tools() -> list[dict[str, object]]:
    """Return the Anthropic-compatible tool schemas the agent can execute."""
    try:
        return get_agent().tools
    except Exception as exc:
        logger.exception("tools failed")
        raise HTTPException(status_code=500, detail=f"Tools unavailable: {exc}") from exc


@app.post("/ask")
def ask(req: AskRequest) -> AskResponse:
    try:
        answer = get_agent().ask(req.question)
    except Exception as exc:
        logger.exception("ask failed")
        raise HTTPException(status_code=500, detail=f"Ask failed: {exc}") from exc
    return AskResponse(answer=answer)


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "ai_briefing.server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
