from fastapi import APIRouter, status

from src.core.dependencies import PgSession

from .usecases import register_new_user

identity_router = APIRouter(prefix="/identity")


@identity_router.post("", status_code=status.HTTP_201_CREATED)
async def register(session: PgSession) -> str:
    return await register_new_user(session=session)
