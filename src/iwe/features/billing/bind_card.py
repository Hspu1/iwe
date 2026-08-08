from enum import StrEnum
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Header, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.bootstrap.dependencies import pg_session
from iwe.infra.postgres.schema import UserCardsModel

#######################################################################################
#######################################################################################


class ResultMessages(StrEnum):
    SUCCESS = "success"
    ALLEGEDLY_USER_NOT_FOUND = "ALLEGEDLY user not found (how tf?!)"
    UNSUPPORTED_RESULT = "ya forgot to handle smth"


class ErrCauseState(StrEnum):
    OP_VIOLATES_FK_CONSTRAINT = "23503"


class ErrCauseConstraint(StrEnum):
    USER_CARDS_USER_ID_FK = "user_cards_user_id_fkey"


#######################################################################################
#######################################################################################


class BindSetiRequest(BaseModel):
    seti_id: str = Field(pattern=r"^seti_[a-zA-Z0-9]{24}$")
    card_brand: str = Field(min_length=3, max_length=20)
    card_last4: str = Field(pattern=r"^\d{4}$")
    make_default: bool


class BindSetiResponse(BaseModel):
    verdict: ResultMessages


#######################################################################################
#######################################################################################

router = APIRouter()


@router.post("/bind-card")
async def bind_setup_intent(
    x_user_id: Annotated[UUID, Header()], payload: BindSetiRequest, response: Response
) -> BindSetiResponse:

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
            return BindSetiResponse(verdict=verdict)

        case ResultMessages.ALLEGEDLY_USER_NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
            return BindSetiResponse(verdict=verdict)

        case _:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return BindSetiResponse(verdict=ResultMessages.UNSUPPORTED_RESULT)


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
                UserCardsModel.seti_id != seti_id,
            )
            .values(is_default=False)
        )

    is_default_query = (
        select(func.count(UserCardsModel.seti_id) == 0)
        .where(UserCardsModel.user_id == user_id)
        .scalar_subquery()
    )
    insert_stmt = pg_insert(UserCardsModel).values(
        user_id=user_id,
        seti_id=seti_id,
        card_brand=card_brand,
        card_last4=card_last4,
        is_default=func.coalesce(make_default or None, is_default_query),
    )

    stmt_manage_card = insert_stmt.on_conflict_do_update(
        index_elements=[UserCardsModel.seti_id],
        set_={
            UserCardsModel.card_brand: insert_stmt.excluded.card_brand,
            UserCardsModel.card_last4: insert_stmt.excluded.card_last4,
            UserCardsModel.is_default: insert_stmt.excluded.is_default,
        },
        where=(
            insert_stmt.excluded.is_default.is_(True)
            | (UserCardsModel.is_default.is_(False))
        ),
    )

    try:
        await session.execute(stmt_manage_card)

    except IntegrityError as err:
        driver_err: asyncpg.PostgresError | None = (
            err.orig.__cause__ if err.orig else None
        )  # wtf
        sqlstate: str = driver_err.sqlstate if driver_err else "unknown"
        constraint: str = (driver_err.constraint_name if driver_err else None) or "none"

        match (sqlstate, constraint):
            case (
                ErrCauseState.OP_VIOLATES_FK_CONSTRAINT,
                ErrCauseConstraint.USER_CARDS_USER_ID_FK,
            ):
                return ResultMessages.ALLEGEDLY_USER_NOT_FOUND

            case _:
                print(
                    f"IntegrityError unexpected shi in manage_card: {
                        sqlstate, constraint
                    }",
                    flush=True,
                )
                raise err

    else:
        return ResultMessages.SUCCESS
