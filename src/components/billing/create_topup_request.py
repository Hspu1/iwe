from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import PgSession
from src.shared.postgres.enums import OutboxEventType, TopUpStatus
from src.shared.postgres.schema import (
    OutboxEventsModel,
    UserCardsModel,
    WalletTopUpsModel,
)

router = APIRouter()


#######################################################################################
#######################################################################################


class TopUpRequest(BaseModel):
    """should be order_id instead of amount acshually"""

    user_id: UUID
    amount: int = Field(
        ge=5000,
        description="Amount in minor units (789.99 --> 78999)",
    )
    idempotency_key: UUID


#######################################################################################
#######################################################################################


@router.post("/top-up", status_code=status.HTTP_202_ACCEPTED)
async def create_request(session: PgSession, request: TopUpRequest) -> dict[str, str]:
    await create_topup_request(
        session=session,
        user_id=request.user_id,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
    )
    return {
        "status": "dih",
    }


#######################################################################################
#######################################################################################


async def create_topup_request(
    session: AsyncSession, user_id: UUID, amount: int, idempotency_key: UUID
) -> None:
    try:
        stmt_top_up = insert(WalletTopUpsModel).values(
            user_id=user_id,
            idempotency_key=idempotency_key,
            amount=amount,
            status=TopUpStatus.PENDING,
        )
        await session.execute(stmt_top_up)

    except IntegrityError as err:
        raise err

    event_type = OutboxEventType.HOLD_FUNDS_REQUESTED
    payload = func.json_build_object(
        "user_id",
        user_id,
        "amount",
        amount,
        "seti_id",
        UserCardsModel.seti_id,
        "idempotency_key",
        idempotency_key,
    )

    stmt_outbox = insert(OutboxEventsModel).from_select(
        ["event_type", "payload"],
        select(event_type, payload)
        .select_from(UserCardsModel)
        .where(UserCardsModel.user_id == user_id),
    )

    result = await session.execute(stmt_outbox)

    if result.rowcount == 0:
        raise Exception
