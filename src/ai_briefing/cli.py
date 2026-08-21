"""Terminal client for the AI Briefing agent (Bitrix24 + Power BI Q&A).

Run from the project root with the venv active (or use venv/bin/chat explicitly):

    chat "сколько лидов в стадии TS_ISSUED?"
    chat "проанализируй конверсии менеджеров за июль+август" --max-steps 20
    chat "короткий вопрос" --model CLAUDE_HAIKU_4_5
    chat "вопрос" --model claude-opus-4-1 --max-tokens 2048 --temperature 0.0

Other commands in this project:

    powerbi-inspect tables                 # list Power BI tables
    powerbi-inspect schema "Table name"    # columns of one table
    powerbi-inspect preview "Table name" --limit 3
    powerbi-inspect dax 'EVALUATE ROW("Test", 1)'
    python -m uvicorn ai_briefing.server:app --reload   # HTTP backend

Flags:

    --model NAME|ID   Which Claude model answers (default: CLAUDE_SONNET_4_5).
                      Fast & cheap: CLAUDE_HAIKU_4_5
                      Balanced:     CLAUDE_SONNET_4_5
                      Most capable: CLAUDE_OPUS_4_1
    --max-steps N     Max tool-calling rounds (default: 10). Simple questions
                      take 1-3; complex analyses (conversions, comparisons)
                      may need 12-20. Each step = one model round trip.
    --max-tokens N    Max tokens per generated reply (default: 1024, ~2 pages
                      of text). Raise it for long report answers.
    --temperature X   Randomness 0.0-1.0 (default: API default). Use 0.0 for
                      factual answers, higher for creative ones.

Progress lines ([agent] ...) and token counts are printed first; the final
answer is the last block of output.
"""

import argparse
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from ai_briefing.agent import Agent, AgentConfig, AgentModel
from ai_briefing.bitrix import BitrixClient, BitrixTools
from ai_briefing.powerbi import PowerBIClient, PowerBITools, get_access_token

_ = load_dotenv()


def _progress(message: str) -> None:
    """Print progress to stdout, flushed immediately — visible even when piped."""
    print(f"[agent] {message}", flush=True)


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
        epilog=(
            "Examples:\n"
            "  chat \"сколько лидов в стадии TS_ISSUED?\"\n"
            "  chat \"конверсии менеджеров за июль+август\" --max-steps 20\n"
            "  chat \"вопрос\" --model claude-opus-4-1 --max-tokens 2048"
        ),
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
    _ = parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="Max tool-calling rounds (default: 10). Raise for complex analyses.",
    )
    _ = parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Randomness 0.0-1.0 (default: API default). Use 0.0 for facts.",
    )
    return parser


def _run() -> None:
    args = build_parser().parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    webhook = os.getenv("BITRIX_WEBHOOK")
    missing = [
        name
        for name, value in {"ANTHROPIC_API_KEY": api_key, "BITRIX_WEBHOOK": webhook}.items()
        if not value
    ]
    if missing:
        raise SystemExit("Missing required env vars: " + ", ".join(missing))
    # Narrow the types: after the check above both are guaranteed non-None.
    assert api_key is not None and webhook is not None

    _progress("инициализация: Bitrix + Power BI + модель…")
    claude = Anthropic(api_key=api_key, timeout=120)
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
            step_callback=_progress,
            usage_callback=lambda inp, out, cached: print(
                f"[agent] токены: {inp} вх / {out} вых (кэш: {cached})", flush=True
            ),
        ),
    )

    print(agent.ask(" ".join(args.question)), flush=True)


def main() -> None:
    """Entry point. Always prints something to stdout — progress, answer, or error."""
    _progress("запуск…")
    try:
        _run()
    except SystemExit as exc:
        if exc.code:
            print(f"[agent] {exc.code}", flush=True)
        raise
    except Exception as exc:  # CLI must always print a readable error
        print(f"[agent] ошибка: {exc}", flush=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
