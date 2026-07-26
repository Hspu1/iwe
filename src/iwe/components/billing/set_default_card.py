from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.schema import UserCardsModel

#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    CARD_NOT_FOUND = "card not found"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


#######################################################################################
#######################################################################################


class SetDefCardRequest(BaseModel):
    seti_id: str


class SetDefCardResponse(BaseModel):
    verdict: ResultMessages


#######################################################################################
#######################################################################################


router = APIRouter()


@router.patch("/cards/set-default")
async def set_default_card(
    x_user_id: Annotated[UUID, Header()],
    payload: SetDefCardRequest,
    response: Response,
) -> SetDefCardResponse:

    async with pg_session() as session:
        verdict = await update_default_card(
            session=session, user_id=x_user_id, seti_id=payload.seti_id
        )

    match verdict:
        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_201_CREATED
            return SetDefCardResponse(verdict=verdict)

        case ResultMessages.CARD_NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
            return SetDefCardResponse(verdict=verdict)

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return SetDefCardResponse(verdict=ResultMessages.UNSUPPORTED_RESULT)


#######################################################################################
#######################################################################################


async def update_default_card(
    session: AsyncSession, user_id: UUID, seti_id: str
) -> ResultMessages:

    lock_stmt = (
        select(UserCardsModel.seti_id)
        .where(UserCardsModel.user_id == user_id)
        .order_by(UserCardsModel.seti_id)
        .with_for_update()
    )

    res = await session.execute(lock_stmt)

    card_found = any(id_ == seti_id for id_ in res.scalars())
    if not card_found:
        return ResultMessages.CARD_NOT_FOUND

    update_stmt = (
        update(UserCardsModel)
        .where(
            UserCardsModel.user_id == user_id,
            UserCardsModel.is_default != (UserCardsModel.seti_id == seti_id),
        )
        .values(is_default=(UserCardsModel.seti_id == seti_id))
    )

    await session.execute(update_stmt)
    return ResultMessages.SUCCESS
