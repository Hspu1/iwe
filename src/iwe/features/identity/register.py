from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from iwe.bootstrap.dependencies import pg_session
from iwe.infra.postgres.schema import UsersModel, WalletsModel

#######################################################################################
#######################################################################################


class RegisterResponse(BaseModel):
    user_id: UUID


#######################################################################################
#######################################################################################


router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register() -> RegisterResponse:
    async with pg_session() as session:
        user_id: UUID = await create_user_with_wallet(session=session)

    return RegisterResponse(user_id=user_id)


#######################################################################################
#######################################################################################


async def create_user_with_wallet(session: AsyncSession) -> UUID:
    user_result = await session.execute(
        pg_insert(UsersModel).returning(UsersModel.id),
    )
    user_id = user_result.scalar_one()

    await session.execute(pg_insert(WalletsModel).values(user_id=user_id))
    return user_id
