from typing import Final

CREATE_STAGING_SQL: Final[str] = """
    CREATE TEMPORARY TABLE staging_ingredients (
        id uuid NOT NULL,
        weight_g double precision NOT NULL,
        name text NOT NULL
    ) ON COMMIT DROP;

    CREATE TEMPORARY TABLE staging_dishes (
        id uuid NOT NULL,
        info jsonb NOT NULL
    ) ON COMMIT DROP;
"""
