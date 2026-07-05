from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import create_top_up_request


async def top_up_request(session: AsyncSession, user_id: UUID, amount: int) -> str:
    top_up_id: UUID = await create_top_up_request(
        session=session, user_id=user_id, amount=amount
    )
    return str(top_up_id)
