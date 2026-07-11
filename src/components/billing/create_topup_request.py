from enum import StrEnum
from uuid import UUID

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import PgSession
from src.shared.postgres.enums import OutboxEventType, TopUpStatus
from src.shared.postgres.schema import (
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
    USER_NOT_FOUND = "user not found"
    NO_CARD_LAD = "no card lad"
    HOLD_THE_FUCK_UP = "hold the fuck up"
    UNSUPPORTED_RESULT = "ya forgot to handle new msg"


class ErrCauseState(StrEnum):
    OP_VIOLATES_FK_CONSTRAINT = "23503"
    DUPLICATE_KEY = "23505"


class ErrCauseConstraint(StrEnum):
    WALLET_TOP_UPS_USER_ID_FK = "wallet_top_ups_user_id_fkey"
    UQ_WALLET_TOP_UPS_USER_IDEMPOTENCY = "uq_wallet_top_ups_user_idempotency"


#######################################################################################
#######################################################################################

router = APIRouter()


@router.post("/top-up")
async def create_request(
    session: PgSession, request: TopUpRequest, response: Response
) -> ResultMessages:

    verdict = await create_topup_request(
        session=session,
        user_id=request.user_id,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
    )

    match verdict:
        case ResultMessages.USER_NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
            return verdict

        case ResultMessages.NO_CARD_LAD:
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
        res_top_up = await session.execute(stmt_top_up)

    except IntegrityError as err:
        driver_err = err.__cause__.__cause__  # wtf
        if (
            driver_err.sqlstate == ErrCauseState.OP_VIOLATES_FK_CONSTRAINT
            and driver_err.constraint_name == ErrCauseConstraint.WALLET_TOP_UPS_USER_ID_FK
        ):
            return ResultMessages.USER_NOT_FOUND

        elif (
            driver_err.sqlstate == ErrCauseState.DUPLICATE_KEY
            and driver_err.constraint_name
            == ErrCauseConstraint.UQ_WALLET_TOP_UPS_USER_IDEMPOTENCY
        ):
            return ResultMessages.HOLD_THE_FUCK_UP

        raise err

    if res_top_up.one_or_none() is None:
        return ResultMessages.NO_CARD_LAD

    event_type = OutboxEventType.HOLD_FUNDS_REQUESTED
    payload = func.json_build_object(
        WalletTopUpsModel.user_id.name,
        user_id,
        WalletTopUpsModel.amount.name,
        amount,
        UserCardsModel.seti_id.name,
        UserCardsModel.seti_id,
        WalletTopUpsModel.idempotency_key.name,
        idempotency_key,
    )

    stmt_outbox = pg_insert(OutboxEventsModel).from_select(
        [OutboxEventsModel.event_type.name, OutboxEventsModel.payload.name],
        select(event_type, payload)
        .select_from(UserCardsModel)
        .where(UserCardsModel.user_id == user_id),
    )

    await session.execute(stmt_outbox)
    return ResultMessages.SUCCESS
