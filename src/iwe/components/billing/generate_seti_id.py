from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from iwe.core.dependencies import stripe_client

#######################################################################################
#######################################################################################


class SetupIntentResponse(BaseModel):
    seti_id: str = Field(validation_alias="seti-id", serialization_alias="seti-id")


#######################################################################################
#######################################################################################


router = APIRouter(prefix="/generate")


@router.post("/seti-id", status_code=status.HTTP_201_CREATED)
async def generate_setup_intent() -> SetupIntentResponse:
    """Frontend's business actually (ts a mock)"""

    intent = await stripe_client.setup_intents.create_async()
    return SetupIntentResponse(seti_id=intent.id)
