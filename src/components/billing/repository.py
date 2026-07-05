from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.postgres.enums import TopUpStatus
from src.shared.postgres.schema import WalletTopUpsModel


async def create_top_up_request(
    session: AsyncSession, user_id: UUID, amount: int
) -> UUID:
    stmt = (
        insert(WalletTopUpsModel)
        .values(user_id=user_id, amount=amount, status=TopUpStatus.PENDING)
        .returning(WalletTopUpsModel.id)
    )

    result = await session.execute(stmt)
    return result.scalar_one()
