from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.core.dependencies import pg_ro_session
from iwe.shared.postgres.schema import UserCardsModel

#######################################################################################
#######################################################################################


class UserCardSchema(BaseModel):
    user_id: UUID
    is_default: bool
    card_last4: str
    card_brand: str
    seti_id: str


class CardsResponse(BaseModel):
    cards: list[UserCardSchema]


#######################################################################################
#######################################################################################


router = APIRouter()


@router.get("/cards", status_code=status.HTTP_200_OK)
async def get_cards(x_user_id: Annotated[UUID, Header()]) -> CardsResponse:
    async with pg_ro_session() as session:
        cards = await get_all_cards(session=session, user_id=x_user_id)

    return {
        "cards": cards,
    }


#######################################################################################
#######################################################################################


async def get_all_cards(session: AsyncSession, user_id: UUID) -> list[UserCardsModel]:
    raw_cards = await session.execute(
        select(UserCardsModel).where(UserCardsModel.user_id == user_id)
    )
    return raw_cards.scalars().all()
