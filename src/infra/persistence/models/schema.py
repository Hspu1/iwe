from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BIGINT,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
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

########################################################################################################


class UsersModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), nullable=False)
    email_verification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index(
            "uq_users_user_active", "email", unique=True, where="is_deleted IS FALSE"
        ),
    )


class WalletsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "wallets"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    balance: Mapped[int] = mapped_column(
        BIGINT, nullable=False, default=0, server_default=text("0")
    )
    cashback_balance: Mapped[int] = mapped_column(
        BIGINT, nullable=False, default=0, server_default=text("0")
    )
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!!


########################################################################################################


class DishesModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "dishes"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "uq_dishes_name_lowercase",
            func.lower(name),
            unique=True,
            where="is_available IS TRUE",
        ),
    )


class IngredientsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "ingredients"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "uq_ingredients_name_lowercase",
            func.lower(name),
            unique=True,
            where="is_available IS TRUE",
        ),
    )


class DishIngredientsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "dish_ingredients"

    dish_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("dishes.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
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


########################################################################################################


class WarehouseModel(Base, TimestampMixin):
    __tablename__ = "warehouse"

    ingredient_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!!


########################################################################################################


class OrdersModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "orders"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    total_price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False)

    __table_args__ = (
        Index(
            "idx_orders_user_active",
            "user_id",
            where="status IN ('CREATED', 'COOKING', 'DELIVERING')",
        ),
    )


class OrderItemsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "order_items"

    order_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    dish_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("dishes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_unit: Mapped[int] = mapped_column(Integer, nullable=False)


########################################################################################################


class OutboxEventsModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "outbox_events"

    event_type: Mapped[OutboxEventType] = mapped_column(
        Enum(OutboxEventType), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[OutboxEventStatus] = mapped_column(
        Enum(OutboxEventStatus), nullable=False
    )

    __table_args__ = (
        Index("idx_outbox_events_pending", "status", where="status = 'PENDING'"),
    )
