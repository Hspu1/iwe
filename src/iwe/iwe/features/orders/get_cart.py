from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.infra.postgres.enums import OrderStatus
from iwe.infra.postgres.schema import DishesModel, OrderContentsModel, OrdersModel
from iwe.shared.dependencies import pg_ro_session

#######################################################################################
#######################################################################################


class Position(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dish_id: UUID
    dish_name: str
    qty: int
    position_cost_cents: int


class CartResponse(BaseModel):
    items: list[Position]
    total_cost_cents: int


#######################################################################################
#######################################################################################


router = APIRouter()


@router.get("/cart", status_code=status.HTTP_200_OK)
async def get_cart(x_user_id: Annotated[UUID, Header()]) -> CartResponse:
    async with pg_ro_session() as session:
        positions_raw = await get_cart_positions(session=session, user_id=x_user_id)

    if not positions_raw:
        return CartResponse(
            items=[],
            total_cost_cents=0,
        )

    total_cost_cents = sum(item["position_cost_cents"] for item in positions_raw)
    items = [Position.model_validate(item) for item in positions_raw]

    return CartResponse(
        items=items,
        total_cost_cents=total_cost_cents,
    )


#######################################################################################
#######################################################################################


async def get_cart_positions(session: AsyncSession, user_id: UUID) -> list[RowMapping]:
    stmt = (
        select(
            DishesModel.id.label("dish_id"),
            DishesModel.info["name"].as_string().label("dish_name"),
            OrderContentsModel.qty,
            (OrderContentsModel.price_cents * OrderContentsModel.qty).label(
                "position_cost_cents"
            ),
        )
        .select_from(OrdersModel)
        .join(OrderContentsModel, OrderContentsModel.order_id == OrdersModel.id)
        .join(DishesModel, DishesModel.id == OrderContentsModel.dish_id)
        .where(
            OrdersModel.user_id == user_id,
            OrdersModel.status == OrderStatus.DRAFT,
            OrderContentsModel.qty > 0,
        )
    )

    result = await session.execute(stmt)
    return result.mappings().all()
