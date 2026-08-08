import asyncio

from fastapi import APIRouter, HTTPException, status

from iwe.bootstrap import dependencies

healthz_router = APIRouter(prefix="/healthz", tags=["[System]"])


@healthz_router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness() -> dict[str, str]:
    pg = dependencies.pg_manager
    try:
        async with asyncio.timeout(5.0):
            await pg.ping()

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
