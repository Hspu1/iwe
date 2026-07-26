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
    ITEMS_UNAVAILABLE = "some items in cart are unavailable"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


#######################################################################################
#######################################################################################


class UnavailableDish(BaseModel):
    id: UUID
    name: str


class FreezeResponse(BaseModel):
    verdict: ResultMessages
    unavailable_items: list[str] | None = None


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
            return {
                "verdict": verdict,
            }

        case ResultMessages.DRAFT_NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                "verdict": verdict,
            }

        case ResultMessages.ITEMS_UNAVAILABLE:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return {
                "verdict": verdict,
                "unavailable_items": unavailable_list,
            }

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {
                "verdict": ResultMessages.UNSUPPORTED_RESULT,
            }  # for debugging


#######################################################################################
#######################################################################################


async def process_freeze(
    session: AsyncSession, user_id: UUID
) -> tuple[ResultMessages, list[str] | None]:

    check_order = (
        select(OrdersModel.id, DishesModel.info["name"].as_string())
        .select_from(OrdersModel)
        .join(
            OrderContentsModel,
            OrderContentsModel.order_id == OrdersModel.id,
            isouter=True,
        )
        .join(
            DishesModel,
            (DishesModel.id == OrderContentsModel.dish_id)
            & (DishesModel.is_available.is_(False)),
            isouter=True,
        )
        .where(
            OrdersModel.user_id == user_id,
            OrdersModel.status == OrderStatus.DRAFT,
        )
    )

    result_order = await session.execute(check_order)
    if not (rows := result_order.all()):
        return ResultMessages.DRAFT_NOT_FOUND, None

    if unavailable_items := [row[1] for row in rows if row[1] is not None]:
        return ResultMessages.ITEMS_UNAVAILABLE, unavailable_items

    order_id = rows[0][0]
    await session.execute(
        update(OrdersModel)
        .where(OrdersModel.id == order_id)
        .values(status=OrderStatus.FROZEN)
    )

    aggregated_dishes = (
        select(
            OrderContentsModel.dish_id,
            OrderContentsModel.qty,
            DishesModel.info,
        )
        .select_from(OrderContentsModel)
        .join(DishesModel, DishesModel.id == OrderContentsModel.dish_id)
        .where(OrderContentsModel.order_id == order_id)
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
        ["order_id", "snapshot"],
        select(
            literal(order_id),
            func.jsonb_object_agg(weighted_summed.c.ingredient, weighted_summed.c.total),
        ).select_from(weighted_summed),
    )

    snapshot_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[IngredientsSnapshotModel.order_id],
        set_={"snapshot": insert_stmt.excluded.snapshot},
    )

    await session.execute(snapshot_stmt)
    return ResultMessages.SUCCESS, None
