import asyncio

from fastapi import APIRouter, HTTPException, status

from iwe.shared.dependencies import pg_manager

healthz_router = APIRouter(prefix="/healthz", tags=["[System]"])


@healthz_router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness() -> dict[str, str]:
    try:
        async with asyncio.timeout(5.0):
            await pg_manager.ping()

        print("[INFO] [HEALTHZ] allez", flush=True)
        return {
            "status": "allez",
        }

    except Exception as err:
        print(f"[ERROR] [HEALTHZ] w/: {err}", flush=True)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connectivity unreachable",
        ) from err
