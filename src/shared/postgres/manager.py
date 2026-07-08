from time import perf_counter
from typing import Any

from orjson import (
    OPT_NON_STR_KEYS,
    OPT_SERIALIZE_UUID,
    dumps,
    loads,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa

from src.core.base import StrictSlots
from src.core.env_conf import PostgresSettings
from src.core.exceptions import PostgresNotReachableError


def orjson_dumps(data: Any) -> bytes:
    return dumps(data, option=OPT_SERIALIZE_UUID | OPT_NON_STR_KEYS)


def orjson_loads(data: str | bytes) -> Any:
    return loads(data)


class PostgresManager(StrictSlots):
    __slots__ = ("_cfg", "_engine", "_session_maker")

    def __init__(self, config: PostgresSettings) -> None:
        self._cfg = config
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        if self._engine and self._session_maker:
            return

        try:
            start = perf_counter()
            self._engine = create_async_engine(
                # url=self._cfg.pgbouncer_url,
                url=self._cfg.postgres_url,
                json_serializer=orjson_dumps,
                json_deserializer=orjson_loads,
                # poolclass=NullPool,
                # connect_args={
                #     "statement_cache_size": 0,
                #     "prepared_statement_cache_size": 0,
                # },
            )
            self._session_maker = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            await self.ping()

            pool_name = (
                "NullPool"
                if self._engine.pool.__class__.__name__ == "NullPool"
                else "QueuePool"
            )
            print(
                f"[CONNECTED] PostgreSQL initialized in {
                    (perf_counter() - start) * 1000:.2f}ms, pool={pool_name}",
                flush=True,
            )

        except (SQLAlchemyError, TimeoutError, Exception) as e:
            await self.disconnect()
            raise PostgresNotReachableError from e

    async def ping(self) -> None:
        if not self._engine:
            raise PostgresNotReachableError

        async with self._session_maker() as session:
            await session.execute(text("SELECT 1"))

    def get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        if not self._session_maker:
            raise PostgresNotReachableError

        return self._session_maker

    async def disconnect(self) -> None:
        if not self._engine:
            self._engine, self._session_maker = None, None
            return

        start = perf_counter()
        try:
            await self._engine.dispose()
            print(
                f"DISCONNECTED, time: {(perf_counter() - start) * 1000}ms",
                flush=True,
            )

        finally:
            self._engine, self._session_maker = None, None
