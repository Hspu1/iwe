from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import PgSession
from src.shared.postgres.schema import WalletsModel

router = APIRouter(prefix="/bind")


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


@router.post("/seti-id", status_code=status.HTTP_200_OK)
async def bind_setup_intent(session: PgSession, request: BindRequest) -> dict[str, str]:
    await bind_seti_id(session=session, user_id=request.user_id, seti_id=request.seti_id)
    return {
        "status": "ghey",
    }


#######################################################################################
#######################################################################################


async def bind_seti_id(session: AsyncSession, user_id: UUID, seti_id: str) -> None:
    stmt = (
        update(WalletsModel)
        .where(
            WalletsModel.user_id == user_id,
            WalletsModel.seti_id.is_(None),
        )
        .values(seti_id=seti_id)
    )
    await session.execute(stmt)
