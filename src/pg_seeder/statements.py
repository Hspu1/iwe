from typing import Final

#######################################################################################
# DDL
#######################################################################################

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


#######################################################################################
# DCL
#######################################################################################


LOCK_TABLES_SQL: Final[str] = """
    LOCK TABLE ingredients, dishes, warehouse IN EXCLUSIVE MODE NOWAIT;
"""


#######################################################################################
# DML
#######################################################################################


UPSERT_INGREDIENTS_SQL: Final[str] = """
    INSERT INTO ingredients (id, name)
    SELECT id, name FROM staging_ingredients
    ON CONFLICT (lower(name)) WHERE is_available IS true
    DO UPDATE SET name = EXCLUDED.name;
"""

UPSERT_DISHES_SQL: Final[str] = """
    INSERT INTO dishes (id, is_available, info)
    SELECT id, true, info FROM staging_dishes
    ON CONFLICT (lower(CAST(info ->> 'name' AS varchar))) WHERE is_available IS true
    DO UPDATE SET info = EXCLUDED.info;
"""

UPSERT_WAREHOUSE_SQL: Final[str] = """
    INSERT INTO warehouse (ingredient_id, weight_g)
    SELECT i.id, s.weight_g
    FROM staging_ingredients s
    JOIN ingredients i
      ON lower(i.name) = lower(s.name) AND i.is_available IS true
    ON CONFLICT (ingredient_id)
    DO UPDATE SET weight_g = EXCLUDED.weight_g;
"""
