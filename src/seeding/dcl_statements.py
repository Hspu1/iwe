from typing import Final

LOCK_TABLES_SQL: Final[str] = """
    LOCK TABLE ingredients, dishes, warehouse IN EXCLUSIVE MODE NOWAIT;
"""
