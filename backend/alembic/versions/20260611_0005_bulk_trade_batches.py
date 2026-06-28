"""Add random bulk trade batches.

Revision ID: 20260611_0005
Revises: 20260609_0004
Create Date: 2026-06-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260611_0005"
down_revision: Union[str, None] = "20260609_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


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


def _fk_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if table_name in _tables() and index_name not in _indexes(table_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    tables = _tables()

    if "bulk_trade_batches" not in tables:
        op.create_table(
            "bulk_trade_batches",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("target_count", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("growth_threshold_percent", sa.DECIMAL(10, 4), nullable=False, server_default="0"),
            sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("scanned_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("bought_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("closed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mode", sa.String(length=16), nullable=False, server_default="sandbox"),
            sa.Column("csv_path", sa.String(length=512), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("raw_summary", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing("bulk_trade_batches", "ix_bulk_trade_batches_id", ["id"])
    _create_index_if_missing("bulk_trade_batches", "ix_bulk_trade_batches_user_id", ["user_id"])
    _create_index_if_missing("bulk_trade_batches", "ix_bulk_trade_batches_account_id", ["account_id"])
    _create_index_if_missing("bulk_trade_batches", "ix_bulk_trade_batches_status", ["status"])

    tables = _tables()
    if "bulk_trade_items" not in tables:
        op.create_table(
            "bulk_trade_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("batch_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("figi", sa.String(length=32), nullable=False),
            sa.Column("ticker", sa.String(length=32), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("reason", sa.String(length=128), nullable=True),
            sa.Column("forecast_id", sa.Integer(), nullable=True),
            sa.Column("bot_trade_id", sa.Integer(), nullable=True),
            sa.Column("model_type_used", sa.String(length=32), nullable=True),
            sa.Column("validation_mae", sa.DECIMAL(15, 6), nullable=True),
            sa.Column("current_price", sa.DECIMAL(15, 6), nullable=True),
            sa.Column("predicted_price", sa.DECIMAL(15, 6), nullable=True),
            sa.Column("price_delta_percent", sa.DECIMAL(10, 4), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=True),
            sa.Column("buy_price", sa.DECIMAL(15, 6), nullable=True),
            sa.Column("buy_amount", sa.DECIMAL(15, 6), nullable=True),
            sa.Column("scheduled_sell_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("realized_pnl", sa.DECIMAL(15, 6), nullable=True),
            sa.Column("realized_pnl_percent", sa.DECIMAL(10, 4), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("raw_result", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.ForeignKeyConstraint(["batch_id"], ["bulk_trade_batches.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["bot_trade_id"], ["bot_trades.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["forecast_id"], ["model_forecasts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing("bulk_trade_items", "ix_bulk_trade_items_id", ["id"])
    _create_index_if_missing("bulk_trade_items", "ix_bulk_trade_items_batch_id", ["batch_id"])
    _create_index_if_missing("bulk_trade_items", "ix_bulk_trade_items_user_id", ["user_id"])
    _create_index_if_missing("bulk_trade_items", "ix_bulk_trade_items_figi", ["figi"])
    _create_index_if_missing("bulk_trade_items", "ix_bulk_trade_items_status", ["status"])
    _create_index_if_missing("bulk_trade_items", "ix_bulk_trade_items_forecast_id", ["forecast_id"])
    _create_index_if_missing("bulk_trade_items", "ix_bulk_trade_items_bot_trade_id", ["bot_trade_id"])

    bot_columns = _columns("bot_trades")
    if bot_columns:
        if "batch_id" not in bot_columns:
            op.add_column("bot_trades", sa.Column("batch_id", sa.Integer(), nullable=True))
        if "auto_sell_target_enabled" not in bot_columns:
            op.add_column(
                "bot_trades",
                sa.Column("auto_sell_target_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            )

        _create_index_if_missing("bot_trades", "ix_bot_trades_batch_id", ["batch_id"])
        if "fk_bot_trades_batch_id_bulk_trade_batches" not in _fk_names("bot_trades"):
            op.create_foreign_key(
                "fk_bot_trades_batch_id_bulk_trade_batches",
                "bot_trades",
                "bulk_trade_batches",
                ["batch_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    if "bot_trades" in _tables():
        fks = _fk_names("bot_trades")
        if "fk_bot_trades_batch_id_bulk_trade_batches" in fks:
            op.drop_constraint("fk_bot_trades_batch_id_bulk_trade_batches", "bot_trades", type_="foreignkey")
        indexes = _indexes("bot_trades")
        if "ix_bot_trades_batch_id" in indexes:
            op.drop_index("ix_bot_trades_batch_id", table_name="bot_trades")
        columns = _columns("bot_trades")
        if "auto_sell_target_enabled" in columns:
            op.drop_column("bot_trades", "auto_sell_target_enabled")
        if "batch_id" in columns:
            op.drop_column("bot_trades", "batch_id")

    if "bulk_trade_items" in _tables():
        op.drop_table("bulk_trade_items")
    if "bulk_trade_batches" in _tables():
        op.drop_table("bulk_trade_batches")
