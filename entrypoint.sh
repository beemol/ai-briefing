#!/bin/sh
set -e

echo "[entrypoint] starting Telegram bot + web server"

# Telegram bot (long-polling) in the background.
python -m ai_briefing.telegram_bot &

# Web server in the foreground (binds $PORT, provides /health for the platform).
exec python -m uvicorn ai_briefing.server:app --host 0.0.0.0 --port "${PORT:-8000}"
