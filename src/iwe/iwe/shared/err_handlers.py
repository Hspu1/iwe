from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import asyncpg
import sqlalchemy

#######################################################################################
#######################################################################################


@dataclass
class PgErrCtx:
    sqlstate: str
    constraint_name: str

    @classmethod
    def from_err(cls, err: sqlalchemy.DBAPIError) -> PgErrCtx:
        driver_err: asyncpg.PostgresError | None = (
            err.orig.__cause__ if err.orig else None
        )
        return cls(
            sqlstate=getattr(driver_err, "sqlstate", "unknown"),
            constraint_name=getattr(driver_err, "constraint_name", "none"),
        )


#######################################################################################
#######################################################################################


async def catch_asyncpg(
    err: sqlalchemy.DBAPIError,
    pg_err_ctx: PgErrCtx,
    section: str,
    res: StrEnum,
) -> StrEnum:

    current_ctx = PgErrCtx.from_err(err=err)
    match current_ctx:
        case PgErrCtx(
            sqlstate=pg_err_ctx.sqlstate, constraint_name=pg_err_ctx.constraint_name
        ):
            return res

        case _:
            print(
                f"{err!r} unexpected shi in {section}: {
                    current_ctx.sqlstate, current_ctx.constraint_name
                }",
                flush=True,
            )
            raise err
