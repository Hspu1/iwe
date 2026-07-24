from fastapi import APIRouter

from .bind_seti_id import router as bind_seti_id
from .create_topup_request import router as create_topup_request
from .generate_seti_id import router as generate_seti_id
from .get_cards import router as get_cards
from .set_default_card import router as set_default_card

billing_router = APIRouter(prefix="/billing", tags=["billing"])
service_router = APIRouter(prefix="/service", tags=["service"])

billing_router.include_router(bind_seti_id)
billing_router.include_router(create_topup_request)
billing_router.include_router(get_cards)
billing_router.include_router(set_default_card)

service_router.include_router(generate_seti_id)


__all__ = (
    "billing_router",
    "service_router",
)
