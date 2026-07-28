from enum import StrEnum
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel
from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.enums import OrderStatus, OutboxEventType, TopUpStatus
from iwe.shared.postgres.schema import (
    OrderContentsModel,
    OrdersModel,
    OutboxEventsModel,
    UserCardsModel,
    WalletTopUpsModel,
)

#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    HOLD_THE_FUCK_UP = "hold the fuck up"
    NO_CARD_LAD = "no card lad"
    ZERO_AMOUNT = "amount cannot be equal to zero"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


class ErrCauseState(StrEnum):
    OP_VIOLATES_FK_CONSTRAINT = "23503"
    DUPLICATE_KEY = "23505"


class ErrCauseConstraint(StrEnum):
    WALLET_TOP_UPS_USER_ID_FK = "wallet_top_ups_user_id_fkey"
    UQ_WALLET_TOP_UPS_USER_IDEMPOTENCY = "uq_wallet_top_ups_user_idempotency"


#######################################################################################
#######################################################################################


class TopUpRequest(BaseModel):
    idempotency_key: UUID


class TopUpResponse(BaseModel):
    verdict: ResultMessages


#######################################################################################
#######################################################################################

router = APIRouter()


@router.post("/top-up")
async def create_request(
    x_user_id: Annotated[UUID, Header()], payload: TopUpRequest, response: Response
) -> TopUpResponse:

    async with pg_session() as session:
        verdict = await create_topup_request(
            session=session,
            user_id=x_user_id,
            idempotency_key=payload.idempotency_key,
        )

    match verdict:
        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_201_CREATED
            return TopUpResponse(verdict=verdict)

        case ResultMessages.HOLD_THE_FUCK_UP:
            response.status_code = status.HTTP_202_ACCEPTED
            return TopUpResponse(verdict=verdict)

        case ResultMessages.NO_CARD_LAD:
            # also triggers when the user is missing
            response.status_code = status.HTTP_404_NOT_FOUND
            return TopUpResponse(verdict=verdict)

        case ResultMessages.ZERO_AMOUNT:
            response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
            return TopUpResponse(verdict=verdict)

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return TopUpResponse(verdict=ResultMessages.UNSUPPORTED_RESULT)


#######################################################################################
#######################################################################################


async def create_topup_request(
    session: AsyncSession, user_id: UUID, idempotency_key: UUID
) -> ResultMessages:

    stmt_lock_card = (
        select(UserCardsModel.seti_id)
        .where(
            UserCardsModel.user_id == user_id,
            UserCardsModel.is_default.is_(True),
        )
        .with_for_update()
    )

    res_card = await session.execute(stmt_lock_card)
    card_seti_id = res_card.scalar_one_or_none()

    if not card_seti_id:
        return ResultMessages.NO_CARD_LAD

    order_cost_res = await session.execute(
        select(
            func.sum(OrderContentsModel.price_cents * OrderContentsModel.qty).label(
                "total_cost"
            )
        )
        .select_from(OrdersModel)
        .join(OrderContentsModel, OrderContentsModel.order_id == OrdersModel.id)
        .where(OrdersModel.user_id == user_id, OrdersModel.status == OrderStatus.FROZEN)
    )

    amount_cents = order_cost_res.scalar_one()
    if amount_cents == 0:
        return ResultMessages.ZERO_AMOUNT

    stmt_top_up = pg_insert(WalletTopUpsModel).values(
        user_id=user_id,
        idempotency_key=idempotency_key,
        amount_cents=amount_cents,
        status=TopUpStatus.PENDING,
    )

    try:
        await session.execute(stmt_top_up)

    except IntegrityError as err:
        driver_err: asyncpg.PostgresError | None = (
            err.orig.__cause__ if err.orig else None
        )  # wtf
        sqlstate: str = driver_err.sqlstate if driver_err else "unknown"
        constraint: str = (driver_err.constraint_name if driver_err else None) or "none"

        if (
            sqlstate == ErrCauseState.DUPLICATE_KEY
            and constraint == ErrCauseConstraint.UQ_WALLET_TOP_UPS_USER_IDEMPOTENCY
        ):
            return ResultMessages.HOLD_THE_FUCK_UP

        print(
            f"IntegrityError unexpected shi in create_topup_request: {
                sqlstate, constraint
            }"
        )
        raise err

    event_type = OutboxEventType.HOLD_FUNDS_REQUESTED
    payload = func.json_build_object(
        literal(WalletTopUpsModel.user_id.name),
        user_id,
        literal(WalletTopUpsModel.amount_cents.name),
        amount_cents,
        literal(UserCardsModel.seti_id.name),
        card_seti_id,
        literal(WalletTopUpsModel.idempotency_key.name),
        idempotency_key,
    )

    stmt_outbox = pg_insert(OutboxEventsModel).values(
        event_type=event_type, payload=payload
    )

    await session.execute(stmt_outbox)
    return ResultMessages.SUCCESS
