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

Use a local model instead of Claude (Ollama / LM Studio, OpenAI-compatible):

    chat "сколько лидов?" --backend openai --model qwen2.5:14b \
        --base-url http://localhost:11434/v1

    Or set LLM_BACKEND / LLM_BASE_URL / LLM_MODEL / LLM_API_KEY in .env.

Flags:

    --model NAME|ID   Which Claude model answers (default: AgentConfig in
                      core/config.py). Fast & cheap: CLAUDE_HAIKU_4_5
                      Balanced: CLAUDE_SONNET_4_5; best: CLAUDE_OPUS_4_1
    --max-steps N     Max tool-calling rounds (default: AgentConfig in
                      core/config.py). Simple questions take 1-3; complex
                      analyses (conversions, comparisons) may need 12-20.
                      Use 0 for no limit (a weak local model can loop forever).
    --max-tokens N    Max tokens per generated reply (default: AgentConfig in
                      core/config.py). Use 0 for no limit (Claude becomes 16384).
    --temperature X   Randomness 0.0-1.0 (default: API default). Use 0.0 for
                      factual answers, higher for creative ones.

Progress lines ([agent] ...) and token counts are printed first; the final
answer is the last block of output.
"""

import argparse
import os
from typing import Any

from dotenv import load_dotenv

from ai_briefing.core import Agent, AgentConfig, AgentModel, build_llm_client
from ai_briefing.domain import build_system_prompt
from ai_briefing.domain.bitrix import BitrixClient, BitrixTools
from ai_briefing.domain.powerbi import PowerBIClient, PowerBITools, get_access_token

_ = load_dotenv()


def _progress(message: str) -> None:
    """Print progress to stdout, flushed immediately — visible even when piped."""
    print(f"[agent] {message}", flush=True)


def _print_usage(input_tokens: int, output_tokens: int, cached: int) -> None:
    """Print token usage (input / output / cache) as a progress line."""
    print(
        f"[agent] токены: {input_tokens} вх / {output_tokens} вых (кэш: {cached})",
        flush=True,
    )


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
            "  chat \"вопрос\" --model claude-opus-4-1 --max-tokens 2048\n"
            "  chat \"вопрос\" --backend openai --model qwen2.5:14b "
            "--base-url http://localhost:11434/v1"
        ),
    )
    _ = parser.add_argument("question", nargs="+", help="The question to ask")
    _ = parser.add_argument(
        "--backend",
        choices=["anthropic", "openai"],
        default=os.getenv("LLM_BACKEND", "anthropic"),
        help="LLM backend: anthropic (Claude) or openai (local model). Default: env LLM_BACKEND or anthropic.",
    )
    _ = parser.add_argument(
        "--base-url",
        default=None,
        help="OpenAI-compatible endpoint for --backend openai, e.g. http://localhost:11434/v1 (Ollama).",
    )
    _ = parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the LLM endpoint (local servers accept any value).",
    )
    _ = parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=(
            "Model: for Claude use enum name or API id (CLAUDE_OPUS_4_1 / claude-opus-4-1); "
            "for --backend openai use any id, e.g. qwen2.5:14b. "
            f"Claude options: {', '.join(m.name for m in AgentModel)}"
        ),
    )
    _ = parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help=(
            "Max tokens per generated reply. Default: AgentConfig (core/config.py). "
            "Use 0 for no limit (Claude becomes 16384)."
        ),
    )
    _ = parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help=(
            "Max tool-calling rounds. Default: AgentConfig (core/config.py). "
            "Use 0 for no limit (risky)."
        ),
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
    backend = args.backend.lower()

    webhook = os.getenv("BITRIX_WEBHOOK")
    if not webhook:
        raise SystemExit("Missing required env var: BITRIX_WEBHOOK")

    if backend == "openai":
        api_key = args.api_key or os.getenv("LLM_API_KEY", "")
        model_id = args.model or os.getenv("LLM_MODEL", "")
        if not model_id:
            raise SystemExit("Missing model: pass --model or set LLM_MODEL")
    else:
        api_key = args.api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise SystemExit("Missing env var: ANTHROPIC_API_KEY (or --api-key)")
        model_id = args.model or ""

    # Start from AgentConfig defaults and override only what the user passed
    # on the command line — core/config.py stays the single source of truth.
    config_kwargs: dict[str, Any] = {
        "system_prompt": build_system_prompt(),
        "step_callback": _progress,
        "usage_callback": _print_usage,
    }

    if backend == "openai":
        config_kwargs["model_name"] = model_id
        # Local models don't explore the schema themselves — give it to them.
        config_kwargs["preload_tools"] = ("get_data_guide",)
    elif args.model is not None:
        config_kwargs["model"] = _model_from_arg(args.model)

    # 0 = "no limit"; absence = "use the AgentConfig default".
    if args.max_tokens == 0:
        config_kwargs["max_tokens"] = None if backend == "openai" else 16384
    elif args.max_tokens is not None:
        config_kwargs["max_tokens"] = args.max_tokens
    if args.max_steps is not None:
        config_kwargs["max_steps"] = None if args.max_steps == 0 else args.max_steps
    if args.temperature is not None:
        config_kwargs["temperature"] = args.temperature

    config = AgentConfig(**config_kwargs)

    # Report the effective configuration so the actual settings are visible.
    effective_model = config.model_name or config.model.value
    max_tokens_s = "без лимита" if config.max_tokens is None else str(config.max_tokens)
    max_steps_s = "без лимита" if config.max_steps is None else str(config.max_steps)
    temperature_s = "default" if config.temperature is None else str(config.temperature)
    _progress(
        f"конфиг: модель={effective_model} | backend={backend} | "
        + f"max_tokens={max_tokens_s} | max_steps={max_steps_s} | "
        + f"temperature={temperature_s}"
    )

    llm = build_llm_client(
        backend=backend,
        api_key=api_key,
        base_url=args.base_url or os.getenv("LLM_BASE_URL", ""),
        model=model_id,
    )
    toolkits = [
        BitrixTools(BitrixClient(webhook)),
        PowerBITools(PowerBIClient(get_access_token)),
    ]
    agent = Agent(llm, toolkits, config=config)

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
