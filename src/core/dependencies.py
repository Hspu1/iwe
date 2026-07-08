from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stripe import HTTPXClient, StripeClient

from src.core.env_conf import stripe_stg
from src.shared.postgres.manager import PostgresManager


async def get_pg_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    pg_manager: PostgresManager = request.app.state.pg_manager
    session_maker: async_sessionmaker[AsyncSession] = pg_manager.get_session_maker()

    async with session_maker.begin() as session:
        yield session


async def get_pg_ro_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    pg_manager: PostgresManager = request.app.state.pg_manager
    session_maker: async_sessionmaker[AsyncSession] = pg_manager.get_session_maker()

    async with session_maker() as session:
        yield session


async def get_stripe_client() -> StripeClient:
    return StripeClient(api_key=stripe_stg.stripe_secret_key)


PgSession = Annotated[AsyncSession, Depends(get_pg_session)]
PgRoSession = Annotated[AsyncSession, Depends(get_pg_ro_session)]
StripeClientDep = Annotated[StripeClient, Depends(get_stripe_client)]
