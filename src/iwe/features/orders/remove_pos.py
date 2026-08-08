from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.bootstrap.dependencies import pg_session
from iwe.infra.postgres.enums import OrderStatus
from iwe.infra.postgres.schema import OrderContentsModel, OrdersModel

#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    ALLEGEDLY_SMTH_NOT_FOUND = "ALLEGEDLY smth (user or draft order) not found (how tf?!)"
    ALLEGEDLY_DISH_NOT_FOUND = "ALLEGEDLY dish not found (how tf?!)"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


#######################################################################################
#######################################################################################


class RemovePositionRequest(BaseModel):
    dish_id: UUID


class RemovePositionResponse(BaseModel):
    verdict: ResultMessages


#######################################################################################
#######################################################################################


router = APIRouter()


@router.patch("/cart/remove-pos")
async def remove_pos(
    x_user_id: Annotated[UUID, Header()],
    payload: RemovePositionRequest,
    response: Response,
) -> RemovePositionResponse:

    async with pg_session() as session:
        verdict = await remove_position(
            session=session, user_id=x_user_id, dish_id=payload.dish_id
        )

    match verdict:
        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_201_CREATED
            return RemovePositionResponse(verdict=verdict)

        case (
            ResultMessages.ALLEGEDLY_SMTH_NOT_FOUND
            | ResultMessages.ALLEGEDLY_DISH_NOT_FOUND
        ):
            response.status_code = status.HTTP_404_NOT_FOUND
            return RemovePositionResponse(verdict=verdict)

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return RemovePositionResponse(verdict=ResultMessages.UNSUPPORTED_RESULT)


#######################################################################################
#######################################################################################


async def remove_position(
    session: AsyncSession, user_id: UUID, dish_id: UUID
) -> ResultMessages:

    order_res = await session.execute(
        select(OrdersModel.id)
        .where(
            OrdersModel.user_id == user_id,
            OrdersModel.status == OrderStatus.DRAFT,
        )
        .with_for_update()
    )

    order_id = order_res.scalar_one_or_none()
    if not order_id:
        return ResultMessages.ALLEGEDLY_SMTH_NOT_FOUND

    upd_res = await session.execute(
        update(OrderContentsModel)
        .where(
            OrderContentsModel.order_id == order_id,
            OrderContentsModel.dish_id == dish_id,
        )
        .values(qty=0)
        .returning(OrderContentsModel.order_id)
    )

    if not upd_res.scalar_one_or_none():
        return ResultMessages.ALLEGEDLY_DISH_NOT_FOUND

    return ResultMessages.SUCCESS
