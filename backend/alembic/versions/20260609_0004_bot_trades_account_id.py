"""Add account_id to bot trades.

Revision ID: 20260609_0004
Revises: 20260531_0003
Create Date: 2026-06-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260609_0004"
down_revision: Union[str, None] = "20260531_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    columns = _columns("bot_trades")
    if not columns:
        return

    if "account_id" not in columns:
        op.add_column("bot_trades", sa.Column("account_id", sa.String(length=128), nullable=True))

    indexes = _indexes("bot_trades")
    if "ix_bot_trades_account_id" not in indexes:
        op.create_index("ix_bot_trades_account_id", "bot_trades", ["account_id"])
    if "ix_bot_trades_user_account_created" not in indexes:
        op.create_index(
            "ix_bot_trades_user_account_created",
            "bot_trades",
            ["user_id", "account_id", "created_at"],
        )


def downgrade() -> None:
    columns = _columns("bot_trades")
    if not columns:
        return

    indexes = _indexes("bot_trades")
    if "ix_bot_trades_user_account_created" in indexes:
        op.drop_index("ix_bot_trades_user_account_created", table_name="bot_trades")
    if "ix_bot_trades_account_id" in indexes:
        op.drop_index("ix_bot_trades_account_id", table_name="bot_trades")
    if "account_id" in columns:
        op.drop_column("bot_trades", "account_id")
