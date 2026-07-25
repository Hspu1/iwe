from fastapi import APIRouter

from .get_cart import router as get_cart
from .positions import router as positions

orders_router = APIRouter(prefix="/orders", tags=["orders"])
orders_router.include_router(positions)
orders_router.include_router(get_cart)

__all__ = ("orders_router",)
