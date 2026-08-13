from fastapi import APIRouter

from .billing import billing_router, service_router
from .identity import identity_router
from .orders import orders_router

features_router = APIRouter()
features_router.include_router(identity_router)
features_router.include_router(billing_router)
features_router.include_router(service_router)
features_router.include_router(orders_router)

__all__ = ("features_router",)
