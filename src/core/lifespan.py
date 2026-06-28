from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infra.persistence.postgres import PostgresManager

from .exceptions import SafeStartError
from .lifespan_helpers import safe_start, silent_close


def get_lifespan(pg_manager: PostgresManager):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            await safe_start(
                service_name="PostgreSQL", coro=pg_manager.connect(), timeout=10.0
            )
        except Exception as e:
            await silent_close(service_name="PostgreSQL", coro=pg_manager.disconnect())
            raise SafeStartError(message="App startup failed due to DB error") from e

        app.state.pg_manager = pg_manager

        try:
            yield
        finally:
            await silent_close(service_name="PostgreSQL", coro=pg_manager.disconnect())

    return lifespan
