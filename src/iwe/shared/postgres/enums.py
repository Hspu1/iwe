from enum import IntEnum


class TopUpStatus(IntEnum):
    PENDING = 1
    SUCCEEDED = 2
    FAILED = 3


class OrderStatus(IntEnum):
    DRAFT = 1
    FROZEN = 2
    COOKING = 3
    DELIVERING = 4
    COMPLETED = 5
    CANCELLED = 6
    FAILED = 7


class OutboxEventType(IntEnum):
    HOLD_FUNDS_REQUESTED = 1
    # еще чето для ингредиентов
