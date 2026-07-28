from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel
from sqlalchemy import Numeric, cast, func, literal, select, text, true, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.enums import OrderStatus
from iwe.shared.postgres.schema import (
    DishesModel,
    IngredientsSnapshotModel,
    OrderContentsModel,
    OrdersModel,
)

#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    DRAFT_NOT_FOUND = "draft order not found"
    CART_EMPTY = "cart is empty"
    ITEMS_UNAVAILABLE = "some items in cart are unavailable"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


#######################################################################################
#######################################################################################


class FreezeResponse(BaseModel):
    verdict: ResultMessages
    unavailable_items: list[dict[str, str]] | None = None


#######################################################################################
#######################################################################################


router = APIRouter()


@router.post("/cart/freeze")
async def freeze_cart(
    x_user_id: Annotated[UUID, Header()], response: Response
) -> FreezeResponse:

    async with pg_session() as session:
        verdict, unavailable_list = await process_freeze(
            session=session, user_id=x_user_id
        )

    match verdict:
        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_200_OK
            return FreezeResponse(verdict=verdict)

        case ResultMessages.DRAFT_NOT_FOUND | ResultMessages.CART_EMPTY:
            response.status_code = status.HTTP_404_NOT_FOUND
            return FreezeResponse(verdict=verdict)

        case ResultMessages.ITEMS_UNAVAILABLE:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return FreezeResponse(verdict=verdict, unavailable_items=unavailable_list)

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return FreezeResponse(verdict=ResultMessages.UNSUPPORTED_RESULT)


#######################################################################################
#######################################################################################


async def process_freeze(
    session: AsyncSession, user_id: UUID
) -> tuple[ResultMessages, list[dict[str, str]] | None]:

    locked_order = await session.execute(
        select(OrdersModel.id)
        .join(
            OrderContentsModel,
            OrderContentsModel.order_id == OrdersModel.id,
        )
        .where(
            OrdersModel.user_id == user_id,
            OrdersModel.status == OrderStatus.DRAFT,
            OrderContentsModel.qty > 0,
        )
        .with_for_update(of=OrdersModel)
    )
    order_id: UUID | None = locked_order.scalar_one_or_none()

    if not order_id:
        return ResultMessages.DRAFT_NOT_FOUND, None

    check_availability = (
        select(
            DishesModel.id,
            DishesModel.info["name"].as_string(),
            DishesModel.is_available,
        )
        .select_from(OrderContentsModel)
        .join(DishesModel, DishesModel.id == OrderContentsModel.dish_id)
        .where(
            OrderContentsModel.order_id == order_id,
            OrderContentsModel.qty > 0,
        )
    )

    result_rows = (await session.execute(check_availability)).all()
    if not result_rows:
        return ResultMessages.CART_EMPTY, None

    if unavailable_items := [
        {"dish_id": str(row[0]), "name": row[1]} for row in result_rows if not row[2]
    ]:
        return ResultMessages.ITEMS_UNAVAILABLE, unavailable_items

    aggregated_dishes = (
        select(
            OrderContentsModel.dish_id,
            OrderContentsModel.qty,
            DishesModel.info,
        )
        .join(
            DishesModel,
            DishesModel.id == OrderContentsModel.dish_id,
        )
        .where(
            OrderContentsModel.order_id == order_id,
            OrderContentsModel.qty > 0,
        )
        .subquery("aggregated_dishes")
    )

    merged_ingredients = aggregated_dishes.c.info["origin_and_recipe"][
        "ingredients_weight_g"
    ].concat(
        func.coalesce(
            aggregated_dishes.c.info["meta"]["micro_and_toxic"],
            text("'{}'::jsonb"),
        )
    )

    raw_data = (
        func.jsonb_each(merged_ingredients)
        .table_valued("key", "value")
        .lateral("raw_data")
    )

    weighted_summed = (
        select(
            raw_data.c.key.label("ingredient"),
            # Numeric to prevent integer rounding/truncation, maintain decimal precision
            func.sum(cast(raw_data.c.value, Numeric) * aggregated_dishes.c.qty).label(
                "total"
            ),
        )
        .select_from(aggregated_dishes)
        .join(raw_data, true())
        .group_by(raw_data.c.key)
        .subquery("weighted_summed")
    )

    insert_stmt = pg_insert(IngredientsSnapshotModel).from_select(
        [IngredientsSnapshotModel.order_id, IngredientsSnapshotModel.snapshot],
        select(
            literal(order_id),
            func.jsonb_object_agg(weighted_summed.c.ingredient, weighted_summed.c.total),
        ),
    )

    snapshot_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[IngredientsSnapshotModel.order_id],
        set_={IngredientsSnapshotModel.snapshot: insert_stmt.excluded.snapshot},
    )

    await session.execute(snapshot_stmt)
    await session.execute(
        update(OrdersModel)
        .where(OrdersModel.id == order_id)
        .values(status=OrderStatus.FROZEN)
    )

    return ResultMessages.SUCCESS, None
