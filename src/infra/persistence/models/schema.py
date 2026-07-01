from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BIGINT,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from .enums import OrderStatus, OutboxEventStatus, OutboxEventType
from .mixins import TimestampMixin, UUIDv7Mixin


class UsersModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "users"

    email_verification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, sort_order=1
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False, sort_order=2)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, sort_order=3
    )

    __table_args__ = (
        Index(
            "uq_users_user_active",
            "email",
            unique=True,
            postgresql_where=text("is_deleted IS FALSE"),
        ),
    )


class WalletsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "wallets"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        sort_order=1,
    )
    balance: Mapped[int] = mapped_column(
        BIGINT, nullable=False, default=0, server_default=text("0"), sort_order=2
    )
    cashback_balance: Mapped[int] = mapped_column(
        BIGINT, nullable=False, default=0, server_default=text("0"), sort_order=3
    )
    is_frozen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, sort_order=4
    )
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 76%
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 76%


class DishesModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "dishes"

    price: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=1)
    name: Mapped[str] = mapped_column(String(50), nullable=False, sort_order=2)
    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, sort_order=3
    )

    __table_args__ = (
        Index(
            "uq_dishes_name_lowercase",
            func.lower(name),
            unique=True,
            postgresql_where=text("is_available IS TRUE"),
        ),
    )


class IngredientsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "ingredients"

    name: Mapped[str] = mapped_column(String(50), nullable=False, sort_order=1)
    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, sort_order=2
    )

    __table_args__ = (
        Index(
            "uq_ingredients_name_lowercase",
            func.lower(name),
            unique=True,
            postgresql_where=text("is_available IS TRUE"),
        ),
    )


class DishIngredientsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "dish_ingredients"

    dish_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("dishes.id", ondelete="CASCADE"), nullable=False, sort_order=1
    )
    ingredient_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
        sort_order=2,
    )

    __table_args__ = (
        UniqueConstraint(
            "dish_id",
            "ingredient_id",
            name="uq_dish_ingredient",
        ),
        Index(
            "idx_dish_ingredient",
            "ingredient_id",
        ),
    )


class WarehouseModel(Base, TimestampMixin):
    __tablename__ = "warehouse"

    ingredient_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        primary_key=True,
        sort_order=1,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=2)
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 67%
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 67%


class OrdersModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "orders"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, sort_order=1
    )
    total_price: Mapped[int] = mapped_column(BIGINT, nullable=False, sort_order=2)
    status: Mapped[OrderStatus] = mapped_column(
        SmallInteger, nullable=False, sort_order=3
    )

    __table_args__ = (
        Index(
            "idx_orders_user_active",
            "user_id",
            postgresql_where=text("status IN (1, 2, 3)"),
            # 1 --> CREATED
            # 2 --> COOKING
            # 3 --> DELIVERING
        ),
    )


class OrderItemsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "order_items"

    order_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, sort_order=1
    )
    dish_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("dishes.id", ondelete="RESTRICT"), nullable=False, sort_order=2
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=3)
    price_per_unit: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=4)


class OutboxEventsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "outbox_events"

    event_type: Mapped[OutboxEventType] = mapped_column(
        SmallInteger, nullable=False, sort_order=1
    )
    status: Mapped[OutboxEventStatus] = mapped_column(
        SmallInteger, nullable=False, sort_order=2
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, sort_order=3)

    __table_args__ = (
        Index(
            "idx_outbox_events_pending", "status", postgresql_where=text("status = 1")
        ),  # 1 --> PENDING
    )
