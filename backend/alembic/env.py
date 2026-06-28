from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.core.db import Base

# Import models so Base.metadata is complete.
from app.models.asset import Asset  # noqa: F401
from app.models.backtest_result import BacktestResult  # noqa: F401
from app.models.bot_trade import BotTrade  # noqa: F401
from app.models.bulk_trade import BulkTradeBatch, BulkTradeItem  # noqa: F401
from app.models.candle import Candle  # noqa: F401
from app.models.ml_model import MLModel  # noqa: F401
from app.models.model_forecast import ModelForecast  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.stock import Stock, StockPrice  # noqa: F401
from app.models.trade import Trade  # noqa: F401
from app.models.training_session import TrainingSession  # noqa: F401
from app.models.user import User  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def db_url() -> str:
    return (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@"
        f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
    )


def run_migrations_offline() -> None:
    context.configure(url=db_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    connectable = create_engine(db_url(), pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
