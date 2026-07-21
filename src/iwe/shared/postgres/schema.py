from uuid import UUID

from sqlalchemy import (
    BIGINT,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    and_,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .check_constraints import (
    CHK_DISHES_INGREDIENTS_WEIGHT_VALID,
    CHK_DISHES_META_METRICS,
    CHK_DISHES_NAME_RULES,
    CHK_DISHES_RECIPE_AND_SUPPLY_CHAIN_RULES,
    CHK_DISHES_ROOT_STRUCTURE_AND_TYPES,
)
from .enums import OrderStatus, OutboxEventType, TopUpStatus
from .mixins import TimestampMixin, UUIDv7Mixin

# op.execute("ALTER TABLE orders SET (fillfactor = 88)")
# op.execute("ALTER TABLE wallet_top_ups SET (fillfactor = 88)")
# op.execute("ALTER TABLE wallets SET (fillfactor = 76)")
# op.execute("ALTER TABLE warehouse SET (fillfactor = 67)")
# op.execute("ALTER TABLE order_contents SET (fillfactor = 80)")


class UsersModel(Base, UUIDv7Mixin):
    __tablename__ = "users"


class WalletsModel(Base):
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 76%
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


class UserCardsModel(Base, UUIDv7Mixin):
    __tablename__ = "user_cards"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        sort_order=1,
    )
    seti_id: Mapped[str] = mapped_column(String(29), nullable=False, sort_order=2)

    __table_args__ = (
        Index("uq_user_cards_user_id", user_id, unique=True),
        Index("uq_user_cards_seti_id", seti_id, unique=True),
    )


class WalletTopUpsModel(Base, UUIDv7Mixin, TimestampMixin):
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 88%
    __tablename__ = "wallet_top_ups"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        sort_order=1,
    )
    idempotency_key: Mapped[UUID] = mapped_column(
        Uuid, nullable=False, sort_order=2
    )  # !!! from the client !!!
    amount: Mapped[int] = mapped_column(
        BIGINT, nullable=False, sort_order=3
    )  # minor units
    status: Mapped[TopUpStatus] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
        sort_order=4,
    )  # 1 --> PENDING; 2 --> SUCCEEDED; 3 --> FAILED

    __table_args__ = (
        UniqueConstraint(
            user_id, idempotency_key, name="uq_wallet_top_ups_user_idempotency"
        ),
        Index(
            "idx_wallet_top_ups_cleanup",
            "created_at",
            postgresql_where=(status == 1),
        ),  # speeds up cron cleanup for abandoned pendings
    )


class DishesModel(Base, UUIDv7Mixin):
    __tablename__ = "dishes"

    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, sort_order=1
    )
    info: Mapped[dict] = mapped_column(JSONB, nullable=False, sort_order=2)

    __table_args__ = (
        CHK_DISHES_ROOT_STRUCTURE_AND_TYPES,
        CHK_DISHES_NAME_RULES,
        CHK_DISHES_META_METRICS,
        CHK_DISHES_RECIPE_AND_SUPPLY_CHAIN_RULES,
        CHK_DISHES_INGREDIENTS_WEIGHT_VALID,
        Index(
            "uq_dishes_name_lowercase",
            func.lower(info["name"].as_string()),
            unique=True,
            postgresql_where=and_(is_available.is_(True)),
        ),
        Index(
            "idx_dishes_info_path_gin",
            info,
            postgresql_using="gin",
            postgresql_ops={"info": "jsonb_path_ops"},
            postgresql_where=and_(is_available.is_(True)),
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
            ingredient_id,
        ),
    )


class WarehouseModel(Base):
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 67%
    __tablename__ = "warehouse"

    ingredient_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        primary_key=True,
        sort_order=1,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=2)


class OrdersModel(Base, UUIDv7Mixin, TimestampMixin):
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 88%
    __tablename__ = "orders"

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, sort_order=1
    )
    status: Mapped[OrderStatus] = mapped_column(
        SmallInteger, nullable=False, sort_order=2
    )

    __table_args__ = (
        Index(
            "idx_orders_user_active",
            user_id,
            postgresql_where=status.in_([1, 2, 3]),
            # 1 --> CREATED; 2 --> COOKING; 3 --> DELIVERING
        ),
    )


class OrderContentsModel(Base):
    # !!! SET FILLFACTOR IN ALEMBIC SCRIPTS !!! --> 80%
    __tablename__ = "order_contents"

    id: Mapped[int] = mapped_column(
        BIGINT, primary_key=True, autoincrement=True, sort_order=1
    )  # dummy
    order_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, sort_order=2
    )
    cost_usd: Mapped[int] = mapped_column(
        BIGINT, nullable=False, sort_order=3
    )  # dish price * qty
    qty: Mapped[int] = mapped_column(SmallInteger, nullable=False, sort_order=4)
    dish_name: Mapped[str] = mapped_column(String(67), nullable=False, sort_order=5)


class OutboxEventsModel(Base, UUIDv7Mixin, TimestampMixin):
    __tablename__ = "outbox_events"

    event_type: Mapped[OutboxEventType] = mapped_column(
        SmallInteger, nullable=False, sort_order=1
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, sort_order=2)
