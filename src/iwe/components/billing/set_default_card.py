from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.schema import UserCardsModel

#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    CARD_NOT_FOUND = "card not found"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"
    CONCURRENT_LOCK_TRY_AGAIN = "oopsie smth went wrong, try again"


class ErrCauseState(StrEnum):
    LOCK_NOT_AVAILABLE = "55P03"


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
            return {
                "verdict": verdict,
            }

        case ResultMessages.CARD_NOT_FOUND:
            # also triggers when the user is missing
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                "verdict": verdict,
            }

        case ResultMessages.CONCURRENT_LOCK_TRY_AGAIN:
            response.status_code = status.HTTP_409_CONFLICT
            return {
                "verdict": verdict,
            }

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {
                "verdict": ResultMessages.UNSUPPORTED_RESULT,
            }  # for debugging


#######################################################################################
#######################################################################################


async def update_default_card(
    session: AsyncSession, user_id: UUID, seti_id: str
) -> ResultMessages:

    lock_stmt = (
        select(UserCardsModel.seti_id)
        .where(UserCardsModel.user_id == user_id)
        .order_by(UserCardsModel.seti_id)
        .with_for_update(nowait=True)
    )

    try:
        res = await session.execute(lock_stmt)

    except DBAPIError as err:
        driver_err = err.__cause__.__cause__  # wtf
        if driver_err.sqlstate == ErrCauseState.LOCK_NOT_AVAILABLE:
            return ResultMessages.CONCURRENT_LOCK_TRY_AGAIN

        print(
            f"DBAPIError unexpected shi in update_default_card: {
                driver_err.sqlstate, driver_err.constraint_name
            }"
        )
        raise err

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
