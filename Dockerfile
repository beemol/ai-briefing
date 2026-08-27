FROM python:3.14-slim

WORKDIR /app

# Install the package (src layout) with its dependencies.
COPY pyproject.toml ./
COPY src ./src
COPY entrypoint.sh ./
RUN pip install --no-cache-dir . \
    && useradd --create-home appuser

USER appuser

EXPOSE 8000

# Run the Telegram bot (long-polling) AND the web server (/health) together.
# The web server keeps the platform's health check happy; the bot handles chat.
CMD ["sh", "/app/entrypoint.sh"]
