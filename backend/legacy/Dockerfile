FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY agents ./agents
COPY moderator ./moderator
COPY tests ./tests
COPY baseline ./baseline
COPY eval ./eval
ENV PYTHONPATH=/app PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
