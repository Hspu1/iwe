from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeClient

from iwe.bootstrap.env_conf import stripe_stg
from iwe.infra.postgres.manager import PostgresManager

from .exceptions import PostgresNotReachableError

pg_manager: PostgresManager | None = None


@asynccontextmanager
async def pg_session() -> AsyncIterator[AsyncSession]:
    if pg_manager is None:
        raise PostgresNotReachableError

    session_maker = pg_manager.get_session_maker()
    async with session_maker.begin() as session:
        yield session


@asynccontextmanager
async def pg_ro_session() -> AsyncIterator[AsyncSession]:
    if pg_manager is None:
        raise PostgresNotReachableError

    session_maker = pg_manager.get_session_maker()
    async with session_maker() as session:
        yield session


stripe_client = StripeClient(api_key=stripe_stg.stripe_secret_key)
