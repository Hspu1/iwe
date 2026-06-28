from asyncio import TimeoutError as AsyncioTimeoutError
from asyncio import wait_for
from collections.abc import Coroutine

from src.core.exceptions import SafeStartError


async def safe_start(service_name: str, coro: Coroutine, timeout: float) -> None:
    try:
        await wait_for(coro, timeout=timeout)
    except (AsyncioTimeoutError, Exception) as e:
        print(f"STARTUP FUCKED UP for service: {service_name} w/ exc: {e}", flush=True)
        raise SafeStartError from e


async def silent_close(
    service_name: str, coro: Coroutine, timeout: float = 5.0
) -> None:
    try:
        await wait_for(coro, timeout=timeout)
    except (AsyncioTimeoutError, Exception) as e:
        print(f"SHUTDOWN FUCKED UP for service: {service_name} w/ exc: {e}", flush=True)
