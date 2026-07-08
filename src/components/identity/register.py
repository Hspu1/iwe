from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import PgSession
from src.core.exceptions import RaceConditionCreatingWalletError
from src.shared.postgres.schema import UsersModel, WalletsModel

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(session: PgSession) -> dict[str, str]:
    user_id: UUID = await create_user_with_wallet(session=session)
    return {
        "user_id": str(user_id),
    }


#######################################################################################
#######################################################################################


async def create_user_with_wallet(session: AsyncSession) -> UUID:
    user_result = await session.execute(
        insert(UsersModel).returning(UsersModel.id),
    )
    user_id = user_result.scalar_one()

    try:
        await session.execute(insert(WalletsModel).values(user_id=user_id))
        return user_id

    except IntegrityError as e:
        raise RaceConditionCreatingWalletError from e
