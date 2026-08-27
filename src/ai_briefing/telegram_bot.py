"""Telegram bot that exposes the leasing AI assistant on the CEO's phone.

Run:
    python -m ai_briefing.telegram_bot          # long-polling (no TLS needed)
    telegram-bot                                # same, via console entry point

Requires TELEGRAM_BOT_TOKEN (from @BotFather) plus the usual agent env vars.
Long-polling keeps the process connected to Telegram and pulls new messages;
no webhook or public HTTPS URL is needed, which makes it the simplest option
for a POC. For production scale, switch to a webhook.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ai_briefing.core import Agent
from ai_briefing.domain.factory import build_agent

_ = load_dotenv()

logger = logging.getLogger("ai_briefing.telegram_bot")

# Telegram hard-caps a message at 4096 characters; keep chunks safely under it.
_MAX_MESSAGE_CHARS = 4000

_agent: Agent | None = None


def get_agent() -> Agent:
    """Build once, reuse across messages (the agent is stateless between asks)."""
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


async def _reply_text(update: Update, text: str) -> None:
    chat = update.effective_chat
    if chat is None:
        return
    for i in range(0, len(text), _MAX_MESSAGE_CHARS):
        await chat.send_message(text[i : i + _MAX_MESSAGE_CHARS])


async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is None:
        return
    await chat.send_message(
        "Привет! Я ассистент по лизингу. Спросите о лидах (Bitrix24) "
        + "или данных отчёта (Power BI). Например: «сколько лидов в стадии FAIL?»"
    )


async def handle_message(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or message.text is None:
        return
    question = message.text.strip()
    if not question:
        return

    chat = update.effective_chat
    if chat is not None:
        await chat.send_chat_action(ChatAction.TYPING)

    try:
        # ask() is blocking (network + LLM calls) — run it off the event loop
        # so other Telegram updates aren't frozen while one answer is generated.
        answer = await asyncio.to_thread(get_agent().ask, question)
    except Exception as exc:
        logger.exception("agent failed")
        answer = f"Ошибка: {exc}"

    await _reply_text(update, answer)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Missing required env var: TELEGRAM_BOT_TOKEN")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.run_polling()


if __name__ == "__main__":
    main()
