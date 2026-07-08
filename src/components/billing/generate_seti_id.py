import stripe
from fastapi import APIRouter, status

from src.core.dependencies import StripeClientDep

router = APIRouter(prefix="/generate")


@router.post("/seti-id", status_code=status.HTTP_201_CREATED)
async def generate_setup_intent(stripe_client: StripeClientDep) -> dict[str, str]:
    try:
        intent = await stripe_client.setup_intents.create_async()
        return {"seti-id": intent.id}

    except (stripe.error.StripeError, Exception) as err:
        raise err
