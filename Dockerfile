FROM python:3.14-slim

WORKDIR /app

# Install the package (src layout) with its dependencies.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && useradd --create-home appuser

USER appuser

EXPOSE 8000

# PORT is set by many platforms (Railway, Fly.io, Render).
CMD ["python", "-m", "uvicorn", "ai_briefing.server:app", "--host", "0.0.0.0", "--port", "8000"]
