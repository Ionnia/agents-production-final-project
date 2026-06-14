# syntax=docker/dockerfile:1
# Agent Service (FastAPI Contract A + LangGraph reasoning core).
# Build context: repository ROOT (needs both agent-service/ and agent/).
# Layout under /app preserves the repo structure so planner.py resolves
# `<repo_root>/agent/baselines` (it walks Path(__file__).parents[3]).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/agent-service/.venv \
    PATH="/app/agent-service/.venv/bin:$PATH"

WORKDIR /app/agent-service

# 1) Dependencies incl. the [llm] reasoning core (langchain/langgraph/gigachat/chroma),
#    pinned by the committed lock for reproducible builds.
COPY agent-service/pyproject.toml agent-service/uv.lock ./
RUN uv sync --frozen --extra llm --no-install-project

# 2) Service source + the Final-agent runtime it imports from ../agent
COPY agent-service/ /app/agent-service/
COPY agent/ /app/agent/
RUN uv sync --frozen --extra llm \
    && chmod +x docker-entrypoint.sh

EXPOSE 8001
ENTRYPOINT ["./docker-entrypoint.sh"]
