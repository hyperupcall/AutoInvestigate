FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY council ./council
COPY prompts ./prompts
COPY agent_host ./agent_host
COPY orchestrator ./orchestrator
COPY tests ./tests
COPY scripts ./scripts
COPY schema ./schema
ENV PYTHONPATH=/app PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
