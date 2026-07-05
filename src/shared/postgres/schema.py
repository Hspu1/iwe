from uuid import UUID

from sqlalchemy import (
    BIGINT,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Uuid,
    and_,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import OrderStatus, OutboxEventType, TopUpStatus
from .mixins import TimestampMixin, UUIDv7Mixin


class UsersModel(Base, UUIDv7Mixin):
    __tablename__ = "users"


class WalletTopUpsModel(Base, TimestampMixin, UUIDv7Mixin):
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 88%
    # op.execute("ALTER TABLE wallet_top_ups SET (fillfactor = 88)")
    __tablename__ = "wallet_top_ups"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        sort_order=1,
    )
    amount: Mapped[int] = mapped_column(
        BIGINT, nullable=False, sort_order=2
    )  # minor units
    status: Mapped[TopUpStatus] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
        sort_order=3,
    )  # 1 --> PENDING; 2 --> SUCCEEDED; 3 --> FAILED

    __table_args__ = (
        Index(
            "idx_wallet_top_ups_cleanup",
            "id",
            postgresql_where=(status == 1),
        ),  # speeds up cron cleanup for abandoned pendings
    )


class WalletsModel(Base):
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 76%
    # op.execute("ALTER TABLE wallets SET (fillfactor = 76)")
    __tablename__ = "wallets"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
        sort_order=1,
    )
    balance: Mapped[int] = mapped_column(
        BIGINT, nullable=False, default=0, server_default=text("0"), sort_order=2
    )  # minor units
    cashback_balance: Mapped[int] = mapped_column(
        BIGINT, nullable=False, default=0, server_default=text("0"), sort_order=3
    )  # minor units


class DishesModel(Base, UUIDv7Mixin):
    __tablename__ = "dishes"

    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, sort_order=1
    )
    info: Mapped[dict] = mapped_column(
        JSONB, nullable=False, sort_order=2
    )  # needed well designed data structure

    __table_args__ = (
        # !!! UPGRADE TO FULL SCHEMA VALIDATION LATER !!!
        CheckConstraint(
            text("info ? 'name'"),
            name="chk_dishes_info_must_define_name",
        ),  # !!! UPGRADE TO FULL SCHEMA VALIDATION LATER !!!
        # !!! UPGRADE TO FULL SCHEMA VALIDATION LATER !!!
        Index(
            "uq_dishes_name_lowercase",
            func.lower(info["name"].as_string()),
            unique=True,
            postgresql_where=and_(
                is_available.is_(True),
                info["name"].as_string().is_not(None),
            ),
        ),
        Index(
            "idx_dishes_info_path_gin",
            info,
            postgresql_using="gin",
            postgresql_ops={"info": "jsonb_path_ops"},
            postgresql_where=and_(
                is_available.is_(True),
                info["name"].as_string().is_not(None),
            ),
            postgresql_with={"fastupdate": False},
        ),
    )


class IngredientsModel(Base, UUIDv7Mixin):
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
            postgresql_where=is_available.is_(True),
        ),
    )


class DishIngredientsModel(Base):
    __tablename__ = "dish_ingredients"

    dish_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True, sort_order=1
    )
    ingredient_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        primary_key=True,
        sort_order=2,
    )

    __table_args__ = (
        Index(
            "idx_dish_ingredient",
            "ingredient_id",
        ),
    )


class WarehouseModel(Base):
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 67%
    # op.execute("ALTER TABLE warehouse SET (fillfactor = 67)")
    __tablename__ = "warehouse"

    ingredient_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        primary_key=True,
        sort_order=1,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=2)


class OrdersModel(Base, TimestampMixin, UUIDv7Mixin):
    __tablename__ = "orders"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, sort_order=1
    )
    total_price: Mapped[int] = mapped_column(BIGINT, nullable=False, sort_order=2)
    status: Mapped[OrderStatus] = mapped_column(
        SmallInteger, nullable=False, sort_order=3
    )
    items: Mapped[dict] = mapped_column(JSONB, nullable=False, sort_order=4)

    __table_args__ = (
        Index(
            "idx_orders_user_active",
            user_id,
            postgresql_where=status.in_([1, 2, 3]),
            # 1 --> CREATED; 2 --> COOKING; 3 --> DELIVERING
        ),
    )


class OutboxEventsModel(Base, TimestampMixin):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    event_type: Mapped[OutboxEventType] = mapped_column(
        SmallInteger, nullable=False, sort_order=1
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, sort_order=3)
