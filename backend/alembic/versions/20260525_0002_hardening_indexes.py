"""hardening indexes and idempotency columns

Revision ID: 20260525_0002
Revises: 20260525_0001
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "20260525_0002"
down_revision = "20260525_0001"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    indexes.update({constraint["name"] for constraint in inspector.get_unique_constraints(table_name) if constraint.get("name")})
    return indexes


def upgrade() -> None:
    order_columns = _columns("orders")
    if order_columns and "idempotency_key" not in order_columns:
        op.add_column("orders", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    bot_columns = _columns("bot_trades")
    if bot_columns and "idempotency_key" not in bot_columns:
        op.add_column("bot_trades", sa.Column("idempotency_key", sa.String(length=128), nullable=True))

    candle_indexes = _indexes("candles")
    if "uq_candles_user_figi_ts" not in candle_indexes:
        op.create_unique_constraint("uq_candles_user_figi_ts", "candles", ["user_id", "figi", "ts"])
    if "ix_candles_user_figi_ts" not in candle_indexes:
        op.create_index("ix_candles_user_figi_ts", "candles", ["user_id", "figi", "ts"])

    order_indexes = _indexes("orders")
    if "uq_orders_user_idempotency_key" not in order_indexes:
        op.create_unique_constraint("uq_orders_user_idempotency_key", "orders", ["user_id", "idempotency_key"])

    bot_indexes = _indexes("bot_trades")
    if "uq_bot_trades_user_idempotency_key" not in bot_indexes:
        op.create_unique_constraint("uq_bot_trades_user_idempotency_key", "bot_trades", ["user_id", "idempotency_key"])


def downgrade() -> None:
    # Conservative downgrade for local dev: drop constraints/columns when present.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "bot_trades" in inspector.get_table_names():
        try:
            op.drop_constraint("uq_bot_trades_user_idempotency_key", "bot_trades", type_="unique")
        except Exception:
            pass
        if "idempotency_key" in _columns("bot_trades"):
            op.drop_column("bot_trades", "idempotency_key")
    if "orders" in inspector.get_table_names():
        try:
            op.drop_constraint("uq_orders_user_idempotency_key", "orders", type_="unique")
        except Exception:
            pass
        if "idempotency_key" in _columns("orders"):
            op.drop_column("orders", "idempotency_key")
    if "candles" in inspector.get_table_names():
        try:
            op.drop_index("ix_candles_user_figi_ts", table_name="candles")
        except Exception:
            pass
        try:
            op.drop_constraint("uq_candles_user_figi_ts", "candles", type_="unique")
        except Exception:
            pass
