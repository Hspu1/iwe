from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.shared.postgres.manager import PostgresManager


async def get_pg_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    pg_manager: PostgresManager = request.app.state.pg_manager
    session_maker: async_sessionmaker[AsyncSession] = pg_manager.get_session_maker()

    async with session_maker.begin() as session:
        yield session


PgSession = Annotated[AsyncSession, Depends(get_pg_session)]
