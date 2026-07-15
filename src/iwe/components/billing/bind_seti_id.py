from enum import StrEnum
from uuid import UUID

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.schema import UserCardsModel

#######################################################################################
#######################################################################################


class BindRequest(BaseModel):
    user_id: UUID
    seti_id: str = Field(
        description="Stripe SetupIntent ID",
        pattern=r"^seti_[a-zA-Z0-9]{24}$",
    )


#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    USER_NOT_FOUND = "user not found"
    USER_ALREADY_EXISTS = "user already exists"
    SETI_ID_ALREADY_EXISTS = "seti-id already exists"
    UNSUPPORTED_RESULT = "ya forgot to handle new msg"


class ErrCauseState(StrEnum):
    OP_VIOLATES_FK_CONSTRAINT = "23503"
    DUPLICATE_KEY = "23505"


class ErrCauseConstraint(StrEnum):
    USER_CARDS_USER_ID_FK = "user_cards_user_id_fkey"
    UQ_USER_CARDS_USER_ID = "uq_user_cards_user_id"
    UQ_USER_CARDS_SETI_ID = "uq_user_cards_seti_id"


#######################################################################################
#######################################################################################

router = APIRouter(prefix="/bind")


@router.post("/seti-id")
async def bind_setup_intent(request: BindRequest, response: Response) -> ResultMessages:
    async with pg_session() as session:
        verdict = await bind_seti_id(
            session=session, user_id=request.user_id, seti_id=request.seti_id
        )

    match verdict:
        case ResultMessages.USER_NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
            return verdict

        case ResultMessages.USER_ALREADY_EXISTS | ResultMessages.SETI_ID_ALREADY_EXISTS:
            response.status_code = status.HTTP_409_CONFLICT
            return verdict

        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_201_CREATED
            return verdict

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return ResultMessages.UNSUPPORTED_RESULT  # for debugging


#######################################################################################
#######################################################################################


async def bind_seti_id(
    session: AsyncSession, user_id: UUID, seti_id: str
) -> ResultMessages:
    stmt = pg_insert(UserCardsModel).values(user_id=user_id, seti_id=seti_id)
    try:
        await session.execute(stmt)

    except IntegrityError as err:
        driver_err = err.__cause__.__cause__  # wtf

        match (driver_err.sqlstate, driver_err.constraint_name):
            case (
                ErrCauseState.OP_VIOLATES_FK_CONSTRAINT,
                ErrCauseConstraint.USER_CARDS_USER_ID_FK,
            ):
                return ResultMessages.USER_NOT_FOUND

            case (
                ErrCauseState.DUPLICATE_KEY,
                ErrCauseConstraint.UQ_USER_CARDS_USER_ID,
            ):
                return ResultMessages.USER_ALREADY_EXISTS

            case (
                ErrCauseState.DUPLICATE_KEY,
                ErrCauseConstraint.UQ_USER_CARDS_SETI_ID,
            ):
                # also triggers when 23505 fires
                # for both user_id and seti_id simultaneously
                return ResultMessages.SETI_ID_ALREADY_EXISTS

            case _:
                raise err

    else:
        return ResultMessages.SUCCESS
