from enum import StrEnum
from typing import cast
from uuid import UUID

from asyncpg.exceptions import LockNotAvailableError, UniqueViolationError
from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.enums import OutboxEventType, TopUpStatus
from iwe.shared.postgres.schema import (
    OutboxEventsModel,
    UserCardsModel,
    WalletTopUpsModel,
)

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


class ResultMessages(StrEnum):
    SUCCESS = "success"
    NO_CARD_LAD = "no card lad"
    HOLD_THE_FUCK_UP = "hold the fuck up"
    UNSUPPORTED_RESULT = "ya forgot to handle new msg"
    CONCURRENT_LOCK_TRY_AGAIN = "oopsie smth went wrong, try again"


class ErrCauseState(StrEnum):
    OP_VIOLATES_FK_CONSTRAINT = "23503"
    DUPLICATE_KEY = "23505"
    LOCK_NOT_AVAILABLE = "55P03"


class ErrCauseConstraint(StrEnum):
    WALLET_TOP_UPS_USER_ID_FK = "wallet_top_ups_user_id_fkey"
    UQ_WALLET_TOP_UPS_USER_IDEMPOTENCY = "uq_wallet_top_ups_user_idempotency"


#######################################################################################
#######################################################################################

router = APIRouter()


@router.post("/top-up")
async def create_request(request: TopUpRequest, response: Response) -> ResultMessages:
    async with pg_session() as session:
        verdict = await create_topup_request(
            session=session,
            user_id=request.user_id,
            amount=request.amount,
            idempotency_key=request.idempotency_key,
        )

    match verdict:
        case ResultMessages.CONCURRENT_LOCK_TRY_AGAIN:
            response.status_code = status.HTTP_409_CONFLICT
            return verdict

        case ResultMessages.NO_CARD_LAD:
            # also triggers when the user is missing
            response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
            return verdict

        case ResultMessages.HOLD_THE_FUCK_UP:
            response.status_code = status.HTTP_202_ACCEPTED
            return verdict

        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_201_CREATED
            return verdict

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return ResultMessages.UNSUPPORTED_RESULT  # for debugging


#######################################################################################
#######################################################################################


async def create_topup_request(
    session: AsyncSession, user_id: UUID, amount: int, idempotency_key: UUID
) -> ResultMessages:

    stmt_lock_card = (
        select(UserCardsModel.seti_id)
        .where(UserCardsModel.user_id == user_id)
        .with_for_update(nowait=True)
    )

    try:
        res_card = await session.execute(stmt_lock_card)
        card_seti_id = res_card.scalar_one_or_none()

    except DBAPIError as err:
        driver_err = cast(LockNotAvailableError, err.__cause__.__cause__)  # wtf
        if driver_err.sqlstate == ErrCauseState.LOCK_NOT_AVAILABLE:
            return ResultMessages.CONCURRENT_LOCK_TRY_AGAIN

        raise err

    if not card_seti_id:
        return ResultMessages.NO_CARD_LAD

    stmt_top_up = (
        pg_insert(WalletTopUpsModel)
        .from_select(
            [
                WalletTopUpsModel.user_id.name,
                WalletTopUpsModel.idempotency_key.name,
                WalletTopUpsModel.amount.name,
                WalletTopUpsModel.status.name,
            ],
            select(
                literal(user_id),
                literal(idempotency_key),
                literal(amount),
                literal(TopUpStatus.PENDING),
            )
            .select_from(UserCardsModel)
            .where(UserCardsModel.user_id == user_id),
        )
        .returning(WalletTopUpsModel.id)
    )

    try:
        await session.execute(stmt_top_up)

    except IntegrityError as err:
        driver_err = cast(UniqueViolationError, err.__cause__.__cause__)  # wtf

        if (
            driver_err.sqlstate == ErrCauseState.DUPLICATE_KEY
            and driver_err.constraint_name
            == ErrCauseConstraint.UQ_WALLET_TOP_UPS_USER_IDEMPOTENCY
        ):
            return ResultMessages.HOLD_THE_FUCK_UP

        raise err

    event_type = literal(OutboxEventType.HOLD_FUNDS_REQUESTED)
    payload = func.json_build_object(
        WalletTopUpsModel.user_id.name,
        user_id,
        WalletTopUpsModel.amount.name,
        amount,
        UserCardsModel.seti_id.name,
        card_seti_id,
        WalletTopUpsModel.idempotency_key.name,
        idempotency_key,
    )

    stmt_outbox = pg_insert(OutboxEventsModel).values(
        event_type=event_type, payload=payload
    )

    await session.execute(stmt_outbox)
    return ResultMessages.SUCCESS
