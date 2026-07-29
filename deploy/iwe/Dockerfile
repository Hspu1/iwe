ARG BASE_IMAGE=python:3.12-slim-bookworm
ARG APP_PORT=8000

FROM ${BASE_IMAGE} AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvbin/uv
ENV PATH="/uvbin:${PATH}"
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

COPY pyproject.toml uv.lock ./
COPY src/iwe/pyproject.toml ./src/iwe/
RUN uv sync --frozen --no-install-project --no-dev --package iwe

FROM ${BASE_IMAGE} AS runtime
ARG APP_PORT
WORKDIR /app

RUN useradd -m -u 1000 app && mkdir -p /app && chown app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1 \
    HOME=/app
ENV APP_PORT=${APP_PORT}

COPY --from=builder --chown=app:app /app/.venv /app/.venv

COPY --chown=app:app ./src/iwe /app/iwe
COPY --chown=app:app deploy/alembic/ /app/deploy/alembic/

USER app

CMD ["sh", "-c", "exec granian --interface asgi iwe.main:app \
    --host 0.0.0.0 \
    --port ${APP_PORT} \
    --loop uvloop \
    --http 1 \
    --workers 1 \
    --log-level warning"]

EXPOSE ${APP_PORT}
