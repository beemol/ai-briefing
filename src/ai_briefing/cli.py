import argparse
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from ai_briefing.agent import Agent, AgentConfig, AgentModel
from ai_briefing.bitrix import BitrixClient, BitrixTools
from ai_briefing.powerbi import PowerBIClient, PowerBITools, get_access_token

_ = load_dotenv()


def _model_from_arg(value: str) -> AgentModel:
    """Accept the enum name (CLAUDE_OPUS_4_1) or the API id (claude-opus-4-1)."""
    try:
        return AgentModel[value.upper()]
    except KeyError:
        return AgentModel(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chat",
        description="Ask the AI assistant a question about leasing (Bitrix24 + Power BI).",
    )
    _ = parser.add_argument("question", nargs="+", help="The question to ask")
    _ = parser.add_argument(
        "--model",
        type=_model_from_arg,
        default=AgentModel.CLAUDE_SONNET_4_5,
        help=(
            "Model: enum name (CLAUDE_OPUS_4_1) or API id (claude-opus-4-1). "
            f"Options: {', '.join(m.name for m in AgentModel)}"
        ),
    )
    _ = parser.add_argument("--max-tokens", type=int, default=1024)
    _ = parser.add_argument("--max-steps", type=int, default=6)
    _ = parser.add_argument("--temperature", type=float, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    webhook = os.getenv("BITRIX_WEBHOOK")
    if not api_key or not webhook:
        raise SystemExit("Missing required env vars: ANTHROPIC_API_KEY, BITRIX_WEBHOOK")

    claude = Anthropic(api_key=api_key)
    toolkits = [
        BitrixTools(BitrixClient(webhook)),
        PowerBITools(PowerBIClient(get_access_token())),
    ]
    agent = Agent(
        claude,
        toolkits,
        config=AgentConfig(
            model=args.model,
            max_tokens=args.max_tokens,
            max_steps=args.max_steps,
            temperature=args.temperature,
        ),
    )

    print(agent.ask(" ".join(args.question)))


if __name__ == "__main__":
    main()
