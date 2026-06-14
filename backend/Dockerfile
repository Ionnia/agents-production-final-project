# syntax=docker/dockerfile:1
# Backend BFF (FastAPI). Build context: ./backend
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/backend/.venv \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

# 1) Dependencies first (cached unless pyproject/lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Application source, then install the project itself
COPY . .
RUN uv sync --frozen --no-dev \
    && chmod +x docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
