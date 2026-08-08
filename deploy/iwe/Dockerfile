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

RUN useradd -m -u 1000 app && \
    mkdir -p /app/tmp && \
    chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1 \
    HOME=/app \
    TMPDIR=/app/tmp \
    GRANIAN_PORT=${APP_PORT}

ENV GRANIAN_HOST=0.0.0.0
ENV GRANIAN_PORT=8000

COPY --from=builder --chown=app:app /app/.venv /app/.venv

COPY --chown=app:app ./src/iwe/iwe /app/iwe
COPY --chown=app:app ./deploy/alembic /app/deploy/alembic

USER app
EXPOSE ${GRANIAN_PORT}

CMD ["granian", "--interface", "asgi", "iwe.main:app", "--loop", "uvloop", "--workers", "1", "--log-level", "warning"]
