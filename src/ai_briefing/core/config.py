"""Agent configuration — typed knobs, no magic strings.

The Python equivalent of a Swift enum with a raw value: `StrEnum` members
carry the API string, so call sites use `AgentModel.CLAUDE_OPUS_4_1`
instead of hardcoding "claude-opus-4-1".
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class AgentModel(StrEnum):
    """Anthropic model IDs the agent can use.

    Add a new model here (never in call sites) and it becomes available
    everywhere the enum is used: CLI choices, configs, defaults.
    """

    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5"
    CLAUDE_SONNET_3_7 = "claude-3-7-sonnet-20250219"
    CLAUDE_OPUS_4_1 = "claude-opus-4-1"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5"


GENERIC_SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the provided tools to answer the user's question. "
    "Prefer counts and aggregations over raw rows; never request full tables. "
    "Never ask the user for clarification: explore the data yourself using the tools. "
    "If the data is insufficient, still give the best answer you can and state what is missing."
)


@dataclass(frozen=True)
class AgentConfig:
    """All knobs for the agent loop. Every field has a safe default.

    Field guide:

    model          - which LLM answers the question.
                     Opus = best quality, slowest, priciest.
                     Sonnet = balanced default.
                     Haiku = cheapest & fastest, fine for simple counts.
    max_tokens     - cap on the *generated answer* (output only).
                     1 token ~ 3-4 chars ~ 0.5-0.75 words, so 1024 ~ 2 pages.
                     None/0 = no cap (backend default). NOTE: the Anthropic
                     API always requires a value — the CLI sends 16384 for
                     Claude when you ask for no limit.
    max_steps      - max tool-calling rounds before giving up.
                     1 step = one API round trip (model -> tool -> model).
                     Typical question: 1-5; complex analyses: 8-15.
                     None/0 = unlimited (use with care: a weak model can
                     loop forever emitting tool calls).
                     On exhaustion the agent asks the model for a partial summary.
    temperature    - randomness of the answer. 0.0 = deterministic/repeatable,
                     1.0 = most creative. For numbers and facts use ~0.0.
                     None = leave the API default (1.0).
    system_prompt  - standing instructions the model sees before every reply:
                     role, language, rules like "always use TOPN".
    usage_callback - optional hook called after every LLM call with
                     (input_tokens, output_tokens, cached_input_tokens);
                     used for cost logging.
    step_callback  - optional hook called with short progress messages
                     during ask(); gives the UI live feedback.
    preload_tools  - tool names auto-executed before the first LLM call and
                     injected as context. Used for local models that fail to
                     explore the schema themselves (they tend to ask the user
                     for clarification instead).
    """

    #: Which LLM answers (see AgentModel).
    model: AgentModel = AgentModel.CLAUDE_HAIKU_4_5
    #: Exact model id sent to the API; overrides `model` (needed for
    #: OpenAI-compatible backends, e.g. local Ollama "qwen2.5:14b").
    model_name: str | None = None
    #: Max tokens per generated reply; None = no cap (backend default).
    #: NOTE: the Anthropic API always requires a value — pass a big number
    #: (e.g. 16384) to make Claude effectively unlimited.
    max_tokens: int | None = 2048
    #: Max tool-calling rounds; None = unlimited (risky with weak models —
    #: they can loop forever emitting tool calls).
    max_steps: int | None = 20
    #: Randomness 0.0-1.0; None = API default (1.0). Use low for facts.
    temperature: float | None = None
    #: Standing instructions prepended to every request.
    system_prompt: str = GENERIC_SYSTEM_PROMPT
    #: Called after every LLM call with (input, output, cached) token counts.
    usage_callback: Callable[[int, int, int], None] | None = None
    #: Called with short progress messages during ask() (UI feedback); None = silent.
    step_callback: Callable[[str], None] | None = None
    #: Tool names auto-executed before the first LLM call (context injection).
    #: Helps weak/local models that won't explore the schema themselves.
    preload_tools: tuple[str, ...] = ()
