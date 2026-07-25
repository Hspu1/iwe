from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import literal, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.enums import OrderStatus
from iwe.shared.postgres.schema import DishesModel, OrderContentsModel, OrdersModel

#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    INVALID_DISH_NAME = "dish not found"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


#######################################################################################
#######################################################################################


class PositionRequest(BaseModel):
    dish_name: str = Field(min_length=6, max_length=67, pattern=r"(?i)burger")
    qty: int = Field(ge=1, le=100)


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
            return {
                "verdict": verdict,
            }

        case ResultMessages.INVALID_DISH_NAME:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                "verdict": verdict,
            }

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {
                "huh": ResultMessages.UNSUPPORTED_RESULT,
            }  # for debugging


#######################################################################################
#######################################################################################


async def add_position(
    session: AsyncSession, user_id: UUID, dish_name: str, qty: int
) -> ResultMessages:

    raw_order_id = (
        pg_insert(OrdersModel)
        .values(user_id=user_id, status=OrderStatus.DRAFT)
        .on_conflict_do_update(
            index_elements=[OrdersModel.user_id],
            index_where=text("status = 1"),  # OrderStatus.DRAFT
            set_={"status": OrdersModel.status},
        )
        .returning(OrdersModel.id)
    )

    retrieve_order_id = await session.execute(raw_order_id)
    order_id = retrieve_order_id.scalar_one_or_none()

    stmt = (
        pg_insert(OrderContentsModel)
        .from_select(
            ["order_id", "dish_id", "price_cents", "qty"],
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
        .on_conflict_do_update(
            index_elements=["order_id", "dish_id"],  # composite PK
            set_={"qty": qty},
        )
        .returning(OrderContentsModel.dish_id)
    )

    res = await session.execute(stmt)
    if not res.scalar_one_or_none():
        return ResultMessages.INVALID_DISH_NAME

    return ResultMessages.SUCCESS
