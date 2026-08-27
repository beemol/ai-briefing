"""Case-specific configuration for the leasing assistant.

The generic framework in ai_briefing.core knows nothing about Bitrix24 or
Power BI. The system prompt below is where you tweak how the assistant
behaves: role, language, and the exact rules it follows.
"""

import os

# The system prompt injected into every request. Edit this to change tone,
# add rules, or adjust which tools the assistant is encouraged to use.
LEASING_SYSTEM_PROMPT = (
    "You are an assistant for a truck-leasing company. "
    "Use tools to answer questions about leasing leads (Bitrix24) or report data (Power BI). "
    "Prefer counts and aggregations over raw rows; never request full tables. "
    "Never ask the user for clarification or more details: explore the data "
    "yourself using the tools (get_data_guide, get_powerbi_schema, get_table_schema, "
    "run_dax_query, manager_rating). "
    "If the data is insufficient, still give the best answer you can and state what is missing. "
    "Answer concisely in Russian."
)


def load_glossary() -> str:
    """Return the contents of glossary.md, or "" if the file is missing.

    The glossary is the CEO-maintained dictionary of business abbreviations,
    stage semantics (Y/X/O/N), and metric definitions. Appending it to the
    system prompt guarantees the agent always understands the terminology.
    """
    path = os.path.join(os.path.dirname(__file__), "glossary.md")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def build_system_prompt() -> str:
    """LEASING_SYSTEM_PROMPT plus the glossary, so terminology is always known."""
    glossary = load_glossary()
    if not glossary:
        return LEASING_SYSTEM_PROMPT
    return (
        LEASING_SYSTEM_PROMPT
        + "\n\n--- Бизнес-глоссарий (сокращения, стадии, метрики) ---\n"
        + glossary
    )
