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


DEFAULT_SYSTEM_PROMPT = (
    "You are an assistant for a truck-leasing company. "
    "Use tools to answer questions about leasing leads (Bitrix24) or report data (Power BI). "
    "Prefer counts and aggregations over raw rows; never request full tables. "
    "Call get_powerbi_schema to discover tables, get_table_schema for one table's columns, "
    "then run_dax_query with TOPN or SUMMARIZECOLUMNS. "
    "Answer concisely in Russian."
)


@dataclass(frozen=True)
class AgentConfig:
    """All knobs for the agent loop. Every field has a safe default.

    Field guide:

    model          - which LLM answers the question.
                     Opus = best quality, slowest, priciest.
                     Sonnet = balanced default.
                     Haiku = cheapest & fastest, fine for simple counts.
    max_tokens     - cap on the size of the *generated answer* (output only;
                     the question and tool results are not counted).
                     1 token ~ 3-4 characters ~ 0.5-0.75 words, so
                     1024 ~ 2 pages of text. Answers are hard-cut at this
                     limit, so raise it for long reports.
    max_steps      - how many tool-calling rounds before the agent gives up.
                     1 step = one API round trip (model -> tool -> model).
                     Typical question: 1-5; complex analyses: 8-15.
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
    """

    #: Which LLM answers (see AgentModel).
    model: AgentModel = AgentModel.CLAUDE_HAIKU_4_5
    #: Max tokens the model may generate per reply (1024 = ~2 pages of text).
    max_tokens: int = 1024
    #: Max tool-calling rounds before the agent gives up.
    max_steps: int = 10
    #: Randomness 0.0-1.0; None = API default (1.0). Use low for facts.
    temperature: float | None = None
    #: Standing instructions prepended to every request.
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    #: Called after every LLM call with (input, output, cached) token counts.
    usage_callback: Callable[[int, int, int], None] | None = None
    #: Called with short progress messages during ask() (UI feedback); None = silent.
    step_callback: Callable[[str], None] | None = None
