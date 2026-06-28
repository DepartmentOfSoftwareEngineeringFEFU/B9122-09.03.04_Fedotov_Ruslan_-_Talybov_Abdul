"""baseline schema managed by Alembic

Revision ID: 20260525_0001
Revises:
Create Date: 2026-05-25
"""
from alembic import op

# Import all models before using Base.metadata.
from app.core.db import Base
from app.models.asset import Asset  # noqa: F401
from app.models.backtest_result import BacktestResult  # noqa: F401
from app.models.bot_trade import BotTrade  # noqa: F401
from app.models.candle import Candle  # noqa: F401
from app.models.ml_model import MLModel  # noqa: F401
from app.models.model_forecast import ModelForecast  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.stock import Stock, StockPrice  # noqa: F401
from app.models.trade import Trade  # noqa: F401
from app.models.training_session import TrainingSession  # noqa: F401
from app.models.user import User  # noqa: F401

revision = "20260525_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
