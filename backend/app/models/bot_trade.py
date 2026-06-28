from sqlalchemy import Boolean, Column, Integer, String, DECIMAL, DateTime, ForeignKey, JSON, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class BotTrade(Base):
    __tablename__ = "bot_trades"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_bot_trades_user_idempotency_key"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    forecast_id = Column(Integer, ForeignKey("model_forecasts.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id = Column(Integer, ForeignKey("bulk_trade_batches.id", ondelete="SET NULL"), nullable=True, index=True)

    figi = Column(String(32), nullable=False, index=True)
    ticker = Column(String(32), nullable=True)
    instrument_name = Column(String(255), nullable=True)
    source = Column(String(64), default="ai_model_bot", nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    account_id = Column(String(128), nullable=True, index=True)

    horizon = Column(String(10), nullable=True)
    model_type_requested = Column(String(32), nullable=True)
    model_type_used = Column(String(32), nullable=True)
    hyperparam_mode = Column(String(16), nullable=True)
    model_params = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)

    recommendation_action = Column(String(64), nullable=True)
    side = Column(String(20), nullable=False)  # buy / sell / schedule_sell
    quantity = Column(Integer, nullable=False)

    price = Column(DECIMAL(15, 6), nullable=False)
    amount = Column(DECIMAL(15, 6), nullable=False)
    current_price = Column(DECIMAL(15, 6), nullable=True)
    predicted_price = Column(DECIMAL(15, 6), nullable=True)
    price_delta_percent = Column(DECIMAL(10, 4), nullable=True)
    average_buy_price = Column(DECIMAL(15, 6), nullable=True)
    cash_balance_at_signal = Column(DECIMAL(15, 6), nullable=True)

    status = Column(String(50), default="planned", nullable=False)
    order_id = Column(String(128), nullable=True)
    broker_order_id = Column(String(128), nullable=True)
    raw_response = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    auto_sell_enabled = Column(Boolean, default=False, nullable=False)
    auto_sell_target_enabled = Column(Boolean, default=True, nullable=False)
    scheduled_sell_at = Column(DateTime(timezone=True), nullable=True)
    sell_target_price = Column(DECIMAL(15, 6), nullable=True)
    realized_pnl = Column(DECIMAL(15, 6), nullable=True)
    realized_pnl_percent = Column(DECIMAL(10, 4), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="bot_trades")
    forecast = relationship("ModelForecast", back_populates="bot_trades")
