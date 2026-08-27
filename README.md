# AI Briefing

A natural-language assistant for a truck-leasing company. The CEO asks a
question in plain language, and an LLM answers it by calling tools that read
live data from **Bitrix24** (CRM / leasing leads) and **Power BI** (the
"Воронка Лизинг_5.0" report).

The code is split into a **generic agent framework** and a **leasing-specific
domain**, so you can reuse the framework for other integrations and keep all
business tweaks in one place.

---

## Quick start

```sh
# 1. Create and activate a virtualenv
python3 -m venv venv
source venv/bin/activate

# 2. Install the project (editable, so code changes apply immediately)
pip install -e .

# 3. Create .env from the example and fill in real values
cp .env.example .env

# 4. Try the CLI
chat "сколько лидов в стадии FAIL?"
```

See [Environment variables](#environment-variables) for what goes in `.env`.

---

## How to run it

There are three entry points:

| Command | What it does |
|---|---|
| `chat "вопрос"` | Ask a single question from the terminal (dev/debug) |
| `powerbi-inspect …` | Inspect the Power BI schema / data (dev/debug) |
| `python -m uvicorn ai_briefing.server:app --reload` | HTTP API (`/ask`, `/tools`, `/health`) |
| `telegram-bot` | Long-running Telegram bot for the CEO |

The **Telegram bot** is the main channel for the CEO — it runs standalone
(long-polling, no public HTTPS needed) and answers messages directly.

---

## Architecture

```
src/ai_briefing/
├── core/            # GENERIC framework — knows nothing about leasing
│   ├── agent.py     #   the LLM tool-calling loop (steps/token caps, partial summary)
│   ├── config.py    #   AgentConfig + AgentModel (typed knobs, no magic strings)
│   ├── toolkit.py   #   Toolkit protocol + result-size cap
│   └── backends.py  #   LLM backends: Anthropic + any OpenAI-compatible server
│
├── domain/          # LEASING-SPECIFIC — all your business tweaks live here
│   ├── config.py    #   LEASING_SYSTEM_PROMPT (role, language, rules)
│   ├── factory.py   #   shared build_agent() used by server + bot
│   ├── glossary.md  #   business abbreviations (fill this in with the CEO)
│   ├── bitrix/      #   Bitrix24 client + tools
│   └── powerbi/     #   Power BI auth + client + tools + schema + data guide
│
├── cli.py           # terminal entry point (`chat`)
├── server.py        # FastAPI entry point (`/ask`)
├── telegram_bot.py  # Telegram entry point
└── legacy/          # old mock pipeline + dead-end diagnostics (NOT wired in)
```

### The one rule to remember

- **`core/`** = reusable framework. Put nothing leasing-specific here.
- **`domain/`** = everything about *this* business. This is where you make changes.

---

## Where to tweak

| You want to… | Edit |
|---|---|
| Change the assistant's role/rules/language | `domain/config.py` → `LEASING_SYSTEM_PROMPT` |
| Add/remove a Power BI tool | `domain/powerbi/tools.py` → `get_tools()` / `execute()` |
| Add/remove a Bitrix tool | `domain/bitrix/tools.py` |
| Change model choices | `core/config.py` → `AgentModel` enum |
| Change token/step defaults | `core/config.py` → `AgentConfig` |
| Teach it business jargon | `domain/glossary.md` (then wire it in) |
| Change the Power BI dataset | `domain/powerbi/tools.py` → `DEFAULT_DATASET_ID` |

---

## Environment variables

Copy `.env.example` to `.env` (`.env` is gitignored).

| Var | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | for Claude | Claude API key |
| `BITRIX_WEBHOOK` | yes | Bitrix24 incoming-webhook URL (pre-authenticated token) |
| `TENANT_ID` | yes | Azure tenant id (Power BI service principal) |
| `CLIENT_ID` | yes | App (client) id |
| `CLIENT_SECRET` | yes | App client secret |
| `DATASET_ID` | no | Power BI dataset id (has a default in code) |
| `LLM_BACKEND` | no | `anthropic` (default) or `openai` |
| `LLM_BASE_URL` | no | OpenAI-compatible endpoint (for a local model) |
| `LLM_MODEL` | no | model id (e.g. `qwen2.5:14b` for Ollama) |
| `LLM_API_KEY` | no | OpenAI API key (any value for local servers) |
| `TELEGRAM_BOT_TOKEN` | for the bot | token from @BotFather |
| `PORT` | no | server port (default 8000) |

> ⚠️ Never commit real secrets. Use the platform's secret manager in production.

---

## Choosing a model

`core/config.py` defines an `AgentModel` enum (the Python equivalent of a
Swift enum) so you never hardcode model strings:

```python
class AgentModel(StrEnum):
    CLAUDE_OPUS_4_1   = "claude-opus-4-1"    # best quality, slowest
    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5"  # balanced default
    CLAUDE_HAIKU_4_5  = "claude-haiku-4-5"   # cheapest & fastest
```

- Claude: `chat "вопрос" --model CLAUDE_OPUS_4_1`
- Any OpenAI-compatible model (Ollama, LM Studio, DeepSeek, …):
  `chat "вопрос" --backend openai --model qwen2.5:14b --base-url http://localhost:11434/v1`

---

## Deployment (Docker)

The repo has a `Dockerfile`. Two zero-SSH options: **Railway** or **Render**
— point them at the repo, add the env vars as secrets, and deploy. The
healthcheck is `GET /health`.

```sh
# Local container (web API):
docker build -t ai-briefing .
docker run --env-file .env -p 8000:8000 ai-briefing

# Run the Telegram bot instead (long-polling, no port needed):
docker run --env-file .env ai-briefing python -m ai_briefing.telegram_bot
```

---

## Development

```sh
# Run the type checker / linter (project uses basedpyright + Ruff)
# (see pyrightconfig.json and [tool.ruff] in pyproject.toml)

# Tests (none yet — planned)
pytest
```
