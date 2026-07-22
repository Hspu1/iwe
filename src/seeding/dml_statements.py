from typing import Final

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
