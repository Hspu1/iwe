from enum import StrEnum
from uuid import UUID

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.schema import UserCardsModel

#######################################################################################
#######################################################################################


class SetDefaultCardRequest(BaseModel):
    user_id: UUID
    seti_id: str


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


router = APIRouter()


@router.patch("/cards/set-default")
async def set_default_card(
    request: SetDefaultCardRequest, response: Response
) -> dict[str, ResultMessages]:

    async with pg_session() as session:
        verdict = await update_default_card(
            session=session, user_id=request.user_id, seti_id=request.seti_id
        )

    match verdict:
        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_201_CREATED
            return {
                "verdict": verdict,
            }

        case ResultMessages.CARD_NOT_FOUND:
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
                "huh": ResultMessages.UNSUPPORTED_RESULT,
            }  # for debugging


#######################################################################################
#######################################################################################


async def update_default_card(
    session: AsyncSession, user_id: UUID, seti_id: str
) -> ResultMessages:
    stmt = (
        select(UserCardsModel)
        .where(UserCardsModel.user_id == user_id)
        .order_by(UserCardsModel.seti_id)
        .with_for_update(nowait=True)
    )

    try:
        res = await session.execute(stmt)

    except DBAPIError as err:
        driver_err = err.__cause__.__cause__  # wtf
        if driver_err.sqlstate == ErrCauseState.LOCK_NOT_AVAILABLE:
            return ResultMessages.CONCURRENT_LOCK_TRY_AGAIN

        print(
            f"DBAPIError unexpected shi in create_topup_request: {
                driver_err.sqlstate, driver_err.constraint_name
            }"
        )
        raise err

    card_found = False
    for card in res.scalars().all():
        if card.seti_id == seti_id:
            card.is_default = True
            card_found = True

        elif card.is_default:
            card.is_default = False

    if not card_found:
        return ResultMessages.CARD_NOT_FOUND

    return ResultMessages.SUCCESS
