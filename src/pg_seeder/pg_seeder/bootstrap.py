import asyncio
import csv
from pathlib import Path
from typing import Annotated, Final

import asyncpg
import orjson
from pydantic import AfterValidator, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from uuid6 import uuid7

from .statements import (
    CREATE_STAGING_SQL,
    LOCK_TABLES_SQL,
    UPSERT_DISHES_SQL,
    UPSERT_INGREDIENTS_SQL,
    UPSERT_WAREHOUSE_SQL,
)

DADDY: Final[int] = 1
SEEDS_DIR: Final[Path] = Path(__file__).resolve().parents[DADDY] / "data" / "seeds"
ENV_FILE: Final[Path] = Path(__file__).resolve().parents[DADDY] / ".env"
CFG = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")


class PostgresSettings(BaseSettings):
    model_config = CFG
    postgres_url: Annotated[PostgresDsn, AfterValidator(str)]


def to_asyncpg_dsn(url: str) -> str:
    return url.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )  # asyncpg requires either postgresql or postgres acshually


def get_ingredients_data() -> list[dict]:
    ingredients_dir = SEEDS_DIR / "ingredients"
    if not ingredients_dir.exists():
        print("[PG SEEDER] u fucked up with paths", flush=True)
        return []

    records = []
    for file_path in ingredients_dir.glob("*.csv"):
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({"name": row["name"], "weight_g": float(row["weight_g"])})

    return records


def get_burgers_data() -> list[dict]:
    burgers_dir = SEEDS_DIR / "dishes" / "burgers"
    if not burgers_dir.exists():
        print("[PG SEEDER] u fucked up with paths", flush=True)
        return []

    records = []
    for file_path in burgers_dir.glob("*.json"):
        with open(file_path, encoding="utf-8") as f:
            records.append(orjson.loads(f.read()))

    return records


#######################################################################################
# VALIDATION OUT OF THE BOX
#######################################################################################
# overall --> src/iwe/shared/postgres/schema.py
# dishes (JSONB shi) --> src/iwe/shared/postgres/check_constraints.py
#######################################################################################
# VALIDATION OUT OF THE BOX
#######################################################################################


async def seed() -> None:
    ingredients = get_ingredients_data()
    burgers = get_burgers_data()

    if not ingredients and not burgers:
        return

    ingredient_rows = [(uuid7(), i["weight_g"], i["name"]) for i in ingredients]
    dish_rows = [(uuid7(), orjson.dumps(b).decode()) for b in burgers]

    pg_stg = PostgresSettings()
    conn = await asyncpg.connect(dsn=to_asyncpg_dsn(pg_stg.postgres_url))
    async with conn.transaction():
        await conn.execute(CREATE_STAGING_SQL)
        await conn.execute(LOCK_TABLES_SQL)

        if ingredient_rows:
            await conn.copy_records_to_table(
                "staging_ingredients",
                records=ingredient_rows,
                columns=["id", "weight_g", "name"],
            )

        if dish_rows:
            await conn.copy_records_to_table(
                "staging_dishes",
                records=dish_rows,
                columns=["id", "info"],
            )

        if ingredient_rows:
            await conn.execute(UPSERT_INGREDIENTS_SQL)

        if dish_rows:
            await conn.execute(UPSERT_DISHES_SQL)

        if ingredient_rows:
            await conn.execute(UPSERT_WAREHOUSE_SQL)

    print(
        f"[PG SEEDER] Seeded {len(ingredient_rows)} ingredients and {
            len(dish_rows)
        } dishes",
        flush=True,
    )


if __name__ == "__main__":
    try:
        asyncio.run(seed())

    except asyncpg.PostgresError as err:
        if (err.sqlstate == "55P03") or ("could not obtain lock" in str(err).lower()):
            print("[PG SEEDER] PG is busy currently", flush=True)
        else:
            print(
                f"[PG SEEDER] Seed expected shi: {err!r} (sqlstate: {err.sqlstate})",
                flush=True,
            )

    except Exception as err:
        print(f"[PG SEEDER] Seed unexpected shi: {err!r}", flush=True)
