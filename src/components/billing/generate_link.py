from uuid import UUID

from fastapi import APIRouter, status
from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeClient, error

from src.core.dependencies import PgRoSession, StripeClientDep
from src.core.env_conf import stripe_stg
from src.shared.postgres.schema import WalletTopUpsModel

router = APIRouter()


#######################################################################################
#######################################################################################


# class SensitiveData:
#     user_id: UUID
#     top_up_id: UUID
#     total_amount: int


#######################################################################################
#######################################################################################


@router.post("/test-pay-link/{top_up_id}", status_code=status.HTTP_201_CREATED)
async def fetch_sensitive_data():
    return "Hey"
    # amount, user_id = await get_top_up_info(session=session, top_up_id=request.top_up_id)
    # try:
    #     checkout_url = await create_stripe_checkout_session(
    #         stripe_client=stripe_client,
    #         top_up_id=request.top_up_id,
    #         amount=amount,
    #         user_id=user_id,
    #         success_url=stripe_stg.stripe_success_url,
    #         cancel_url=stripe_stg.stripe_cancel_url,
    #     )

    # except error.StripeError as e:
    #     raise e

    # return checkout_url


#######################################################################################
#######################################################################################


async def create_stripe_checkout_session(  # noqa: PLR0913
    stripe_client: StripeClient,
    top_up_id: UUID,
    amount: int,
    user_id: UUID,
    success_url: str,
    cancel_url: str,
) -> HttpUrl:

    checkout_session = await stripe_client.checkout.sessions.create_async(
        params={
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price_data": {
                        "currency": "rub",
                        "product_data": {
                            "name": f"Top Up wallet #{top_up_id}",
                        },
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                }
            ],
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"top_up_id": str(top_up_id), "user_id": str(user_id)},
        },
        options={"idempotency_key": str(top_up_id)},
    )

    return checkout_session.url


#######################################################################################
#######################################################################################


async def get_top_up_info(session: AsyncSession, top_up_id: UUID) -> tuple[int, UUID]:
    stmt = select(WalletTopUpsModel.amount, WalletTopUpsModel.user_id).where(
        WalletTopUpsModel.id == top_up_id
    )
    result = await session.execute(stmt)

    return result.one()
