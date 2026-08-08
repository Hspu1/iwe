from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from iwe.infra.postgres.manager import PostgresManager
from iwe.shared import dependencies
from iwe.shared.exceptions import SafeStartError

from .lifespan_helpers import safe_start, silent_close


def get_lifespan(
    pg_manager_instance: PostgresManager,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        dependencies.pg_manager = pg_manager_instance

        try:
            await safe_start(
                service_name="PostgreSQL",
                coro=dependencies.pg_manager.connect(),
                atimeout=10.0,
            )
        except Exception as e:
            await silent_close(
                service_name="PostgreSQL", coro=dependencies.pg_manager.disconnect()
            )
            raise SafeStartError(
                message="App startup failed due to PostgreSQL error"
            ) from e

        try:
            yield
        finally:
            await silent_close(
                service_name="PostgreSQL", coro=dependencies.pg_manager.disconnect()
            )

    return lifespan
