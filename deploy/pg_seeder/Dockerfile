ARG BASE_IMAGE=python:3.12-slim-bookworm

FROM ${BASE_IMAGE} AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvbin/uv
ENV PATH="/uvbin:${PATH}"
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

COPY pyproject.toml uv.lock ./
COPY src/pg_seeder/pyproject.toml ./src/pg_seeder/
RUN uv sync --frozen --no-install-project --no-dev --package pg_seeder

FROM ${BASE_IMAGE} AS runtime
WORKDIR /app

RUN useradd -m -u 1000 app && mkdir -p /app && chown app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1 \
    HOME=/app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

COPY --chown=app:app ./src/pg_seeder /app/pg_seeder
COPY --chown=app:app ./data/seeds /app/data/seeds

USER app

CMD ["python3", "-m", "pg_seeder.bootstrap"]
