from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import PgSession
from src.shared.postgres.enums import TopUpStatus
from src.shared.postgres.schema import WalletTopUpsModel

router = APIRouter()


#######################################################################################
#######################################################################################


class TopUpRequest(BaseModel):
    user_id: UUID
    amount: int = Field(
        ge=5000,
        description="Amount in minor units (789.99 --> 78999)",
    )


#######################################################################################
#######################################################################################


@router.post("/top-up", status_code=status.HTTP_200_OK)
async def create_request(session: PgSession, request: TopUpRequest) -> UUID:
    top_up_id = await create_top_up_transaction(
        session=session, user_id=request.user_id, amount=request.amount
    )
    return top_up_id


#######################################################################################
#######################################################################################


async def create_top_up_transaction(
    session: AsyncSession, user_id: UUID, amount: int
) -> UUID:
    stmt = (
        insert(WalletTopUpsModel)
        .values(user_id=user_id, amount=amount, status=TopUpStatus.PENDING)
        .returning(WalletTopUpsModel.id)
    )

    result = await session.execute(stmt)
    return result.scalar_one()
