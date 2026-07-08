from fastapi import APIRouter

from .billing import billing_router, internal_router, service_router
from .identity import identity_router

components_router = APIRouter()
components_router.include_router(identity_router)
components_router.include_router(billing_router)
components_router.include_router(service_router)
components_router.include_router(internal_router)

__all__ = ("components_router",)
