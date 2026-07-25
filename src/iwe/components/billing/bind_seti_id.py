from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import exists, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_session
from iwe.shared.postgres.schema import UserCardsModel

#######################################################################################
#######################################################################################


class BindRequest(BaseModel):
    seti_id: str = Field(pattern=r"^seti_[a-zA-Z0-9]{24}$")
    card_brand: str = Field(min_length=3, max_length=20)
    card_last4: str = Field(pattern=r"^\d{4}$")
    make_default: bool


#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    USER_NOT_FOUND = "user not found"
    THIS_CARD_ALRDY_BOUND = "this card alrdy bound"
    USER_ALRDY_HAS_DEFAULT_CARD = "user alrdy has a default card"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


class ErrCauseState(StrEnum):
    OP_VIOLATES_FK_CONSTRAINT = "23503"
    DUPLICATE_KEY = "23505"


class ErrCauseConstraint(StrEnum):
    USER_CARDS_USER_ID_FK = "user_cards_user_id_fkey"
    UQ_USER_CARDS_SETI_ID = "uq_user_cards_seti_id"
    UQ_USER_CARDS_USER_DEFAULT_CARD = "uq_user_cards_user_default_card"


#######################################################################################
#######################################################################################

router = APIRouter()


@router.post("/bind-card")
async def bind_setup_intent(
    x_user_id: Annotated[UUID, Header()], payload: BindRequest, response: Response
) -> dict[str, ResultMessages]:

    async with pg_session() as session:
        verdict = await manage_card(
            session=session,
            user_id=x_user_id,
            seti_id=payload.seti_id,
            card_brand=payload.card_brand,
            card_last4=payload.card_last4,
            make_default=payload.make_default,
        )

    match verdict:
        case ResultMessages.SUCCESS:
            response.status_code = status.HTTP_201_CREATED
            return {
                "verdict": verdict,
            }

        case ResultMessages.USER_NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                "verdict": verdict,
            }

        case (
            ResultMessages.THIS_CARD_ALRDY_BOUND
            | ResultMessages.USER_ALRDY_HAS_DEFAULT_CARD
        ):
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


async def manage_card(  # noqa PLR0913
    session: AsyncSession,
    user_id: UUID,
    seti_id: str,
    card_brand: str,
    card_last4: str,
    make_default: bool,
) -> ResultMessages:

    if make_default:
        await session.execute(
            update(UserCardsModel)
            .where(
                UserCardsModel.user_id == user_id,
                UserCardsModel.is_default.is_(True),
            )
            .values(is_default=False)
        )
    else:
        has_cards = await session.execute(
            select(exists().where(UserCardsModel.user_id == user_id))
        )
        if not has_cards.scalar_one():
            make_default = True

    stmt = pg_insert(UserCardsModel).values(
        user_id=user_id,
        seti_id=seti_id,
        card_brand=card_brand,
        card_last4=card_last4,
        is_default=make_default,
    )

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
                ErrCauseConstraint.UQ_USER_CARDS_SETI_ID,
            ):
                # also triggers when 23503 (user not found) and 23505 on seti-id
                # and
                # also triggers when 23505 fires
                # for both user_id and seti_id simultaneously
                return ResultMessages.THIS_CARD_ALRDY_BOUND

            case (
                ErrCauseState.DUPLICATE_KEY,
                ErrCauseConstraint.UQ_USER_CARDS_USER_DEFAULT_CARD,
            ):
                return ResultMessages.USER_ALRDY_HAS_DEFAULT_CARD

            case _:
                print(
                    f"IntegrityError unexpected shi in bind_seti_id: {
                        driver_err.sqlstate, driver_err.constraint_name
                    }"
                )
                raise err

    else:
        return ResultMessages.SUCCESS
