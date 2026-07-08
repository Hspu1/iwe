from uuid import UUID

from fastapi import APIRouter, Header, Request, status
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from stripe import Webhook

from src.core.dependencies import PgSession
from src.core.env_conf import stripe_stg
from src.core.exceptions import WalletBalanceOverflowError
from src.shared.postgres.enums import TopUpStatus
from src.shared.postgres.schema import WalletsModel, WalletTopUpsModel

router = APIRouter(prefix="/webhooks")


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    session: PgSession,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
) -> dict[str, str]:

    if not stripe_signature:
        return {"status": "bad_signature"}

    payload = await request.body()
    try:
        event = Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=stripe_stg.stripe_webhook_secret,
        )
    except Exception:
        return {"status": "bad_signature"}

    if event["type"] != "checkout.session.completed":
        return {"status": "ignored_event_type"}

    session_data = event["data"]["object"]
    metadata = session_data["metadata"]
    top_up_id_raw = metadata["top_up_id"] if metadata else None
    user_id_raw = metadata["user_id"] if metadata else None
    amount = session_data["amount_total"]

    if not top_up_id_raw or not user_id_raw or amount is None:
        return {"status": "missing_metadata_fields"}

    try:
        top_up_id = UUID(top_up_id_raw)
        user_id = UUID(user_id_raw)

    except ValueError:
        return {"status": "invalid_uuid_format"}

    return await i_am_gay(
        session=session, top_up_id=top_up_id, user_id=user_id, amount=amount
    )


#######################################################################################
#######################################################################################


async def i_am_gay(
    session: PgSession, top_up_id: UUID, user_id: UUID, amount: int
) -> dict[str, str]:

    stmt = (
        select(WalletTopUpsModel.status)
        .where(WalletTopUpsModel.id == top_up_id)
        .with_for_update(nowait=True)
    )
    result = await session.execute(stmt)
    top_up_status = result.scalar_one_or_none()

    if top_up_status is None:
        return {"status": "not_found"}

    if top_up_status != TopUpStatus.PENDING:
        return {"status": "already_processed"}

    await session.execute(
        update(WalletTopUpsModel)
        .where(WalletTopUpsModel.id == top_up_id)
        .values(status=TopUpStatus.SUCCEEDED)
    )

    try:
        await session.execute(
            update(WalletsModel)
            .where(WalletsModel.user_id == user_id)
            .values(balance=WalletsModel.balance + amount)
        )

    except DBAPIError as e:
        overflow_markers = (
            # "value out of int64 range",  # asyncpg.exceptions.DataError  FOR WHAT
            # FOR WHATFOR WHATFOR WHATFOR WHATFOR WHATFOR WHATFOR WHATFOR WHAT
            "bigint out of range",  # asyncpg.exceptions.NumericValueOutOfRangeError
        )
        if any(marker in str(e.orig) for marker in overflow_markers):
            raise WalletBalanceOverflowError(user_id=user_id) from e

        raise e

    return {"status": "success"}
