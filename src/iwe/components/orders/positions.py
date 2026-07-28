from enum import StrEnum
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import literal, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.enums import OrderStatus
from iwe.shared.postgres.schema import DishesModel, OrderContentsModel, OrdersModel

#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    ALLEGEDLY_USER_NOT_FOUND = "ALLEGEDLY user not found (how tf?!)"
    ALLEGEDLY_DISH_NOT_FOUND = "ALLEGEDLY dish not found (how tf?!)"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


class ErrCauseState(StrEnum):
    OP_VIOLATES_FK_CONSTRAINT = "23503"


class ErrCauseConstraint(StrEnum):
    ORDERS_USER_ID_FK = "orders_user_id_fkey"


#######################################################################################
#######################################################################################


class PositionRequest(BaseModel):
    dish_name: str = Field(min_length=6, max_length=67, pattern=r"(?i)burger")
    qty: int = Field(ge=0, le=100)  # qty=0 => deleting


class PositionResponse(BaseModel):
    verdict: ResultMessages


#######################################################################################
#######################################################################################

router = APIRouter()


@router.post("/cart/positions")
async def manage_position(
    x_user_id: Annotated[UUID, Header()], payload: PositionRequest, response: Response
) -> PositionResponse:

    async with pg_session() as session:
        verdict = await add_position(
            session=session,
            user_id=x_user_id,
            dish_name=payload.dish_name,
            qty=payload.qty,
        )

    match verdict:
        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_201_CREATED
            return PositionResponse(verdict=verdict)

        case (
            ResultMessages.ALLEGEDLY_USER_NOT_FOUND
            | ResultMessages.ALLEGEDLY_DISH_NOT_FOUND
        ):
            response.status_code = status.HTTP_404_NOT_FOUND
            return PositionResponse(verdict=verdict)

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return PositionResponse(verdict=ResultMessages.UNSUPPORTED_RESULT)


#######################################################################################
#######################################################################################


async def add_position(
    session: AsyncSession, user_id: UUID, dish_name: str, qty: int
) -> ResultMessages:

    order_id_stmt = (
        pg_insert(OrdersModel)
        .values(user_id=user_id, status=OrderStatus.DRAFT)
        .on_conflict_do_update(
            index_elements=[OrdersModel.user_id],
            index_where=literal_column(
                f"status = {OrderStatus.DRAFT.value}",
            ),  # ok
            set_={
                OrdersModel.user_id: OrdersModel.user_id,
            },  # dummy
        )
        .returning(OrdersModel.id)
    )
    try:
        order_id_res = await session.execute(order_id_stmt)

    except IntegrityError as err:
        driver_err: asyncpg.PostgresError | None = (
            err.orig.__cause__ if err.orig else None
        )  # wtf
        sqlstate: str = driver_err.sqlstate if driver_err else "unknown"
        constraint: str = (driver_err.constraint_name if driver_err else None) or "none"

        match (sqlstate, constraint):
            case (
                ErrCauseState.OP_VIOLATES_FK_CONSTRAINT,
                ErrCauseConstraint.ORDERS_USER_ID_FK,
            ):
                return ResultMessages.ALLEGEDLY_USER_NOT_FOUND

            case _:
                print(
                    f"IntegrityError unexpected shi in add_position: {
                        sqlstate, constraint
                    }"
                )
                raise err

    else:
        order_id = order_id_res.scalar_one_or_none()

        insert_stmt = pg_insert(OrderContentsModel).from_select(
            [
                OrderContentsModel.order_id,
                OrderContentsModel.dish_id,
                OrderContentsModel.price_cents,
                OrderContentsModel.qty,
            ],
            select(
                literal(order_id),
                DishesModel.id,
                DishesModel.info["price_cents"].as_integer(),
                literal(qty),
            ).where(
                DishesModel.info["name"].as_string() == dish_name,
                DishesModel.is_available.is_(True),
            ),
        )

        add_pos_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[
                OrderContentsModel.order_id,
                OrderContentsModel.dish_id,
            ],  # composite PK
            set_={OrderContentsModel.qty: insert_stmt.excluded.qty},
        ).returning(OrderContentsModel.dish_id)

        add_pos_res = await session.execute(add_pos_stmt)
        if not add_pos_res.scalar_one_or_none():
            return ResultMessages.ALLEGEDLY_DISH_NOT_FOUND

        return ResultMessages.SUCCESS
