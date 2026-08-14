from asyncio import wait_for
from collections.abc import Coroutine

from iwe.shared.exceptions import SafeStartError


async def safe_start(service_name: str, coro: Coroutine, atimeout: float) -> None:
    try:
        await wait_for(coro, timeout=atimeout)

    except (TimeoutError, Exception) as err:
        print(
            f"STARTUP FUCKED UP for service: {service_name} w/ err: {err!r}",
            flush=True,
        )
        raise SafeStartError from err


async def silent_close(service_name: str, coro: Coroutine, atimeout: float = 5.0) -> None:
    try:
        await wait_for(coro, timeout=atimeout)

    except (TimeoutError, Exception) as err:
        print(
            f"SHUTDOWN FUCKED UP for service: {service_name} w/ exc: {err!r}",
            flush=True,
        )
