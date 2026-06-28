from sqlalchemy import Column, DateTime, DECIMAL, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class BulkTradeBatch(Base):
    __tablename__ = "bulk_trade_batches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String(128), nullable=True, index=True)

    status = Column(String(32), default="queued", nullable=False, index=True)
    target_count = Column(Integer, default=30, nullable=False)
    growth_threshold_percent = Column(DECIMAL(10, 4), default=0, nullable=False)
    candidate_count = Column(Integer, default=0, nullable=False)
    scanned_count = Column(Integer, default=0, nullable=False)
    bought_count = Column(Integer, default=0, nullable=False)
    skipped_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    closed_count = Column(Integer, default=0, nullable=False)

    mode = Column(String(16), default="sandbox", nullable=False)
    csv_path = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    raw_summary = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("BulkTradeItem", back_populates="batch", cascade="all, delete-orphan")


class BulkTradeItem(Base):
    __tablename__ = "bulk_trade_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("bulk_trade_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    figi = Column(String(32), nullable=False, index=True)
    ticker = Column(String(32), nullable=True)
    status = Column(String(32), default="pending", nullable=False, index=True)
    reason = Column(String(128), nullable=True)

    forecast_id = Column(Integer, ForeignKey("model_forecasts.id", ondelete="SET NULL"), nullable=True, index=True)
    bot_trade_id = Column(Integer, ForeignKey("bot_trades.id", ondelete="SET NULL"), nullable=True, index=True)
    model_type_used = Column(String(32), nullable=True)
    validation_mae = Column(DECIMAL(15, 6), nullable=True)

    current_price = Column(DECIMAL(15, 6), nullable=True)
    predicted_price = Column(DECIMAL(15, 6), nullable=True)
    price_delta_percent = Column(DECIMAL(10, 4), nullable=True)
    quantity = Column(Integer, nullable=True)
    buy_price = Column(DECIMAL(15, 6), nullable=True)
    buy_amount = Column(DECIMAL(15, 6), nullable=True)

    scheduled_sell_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    realized_pnl = Column(DECIMAL(15, 6), nullable=True)
    realized_pnl_percent = Column(DECIMAL(10, 4), nullable=True)

    error_message = Column(Text, nullable=True)
    raw_result = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    batch = relationship("BulkTradeBatch", back_populates="items")
    bot_trade = relationship("BotTrade")
    forecast = relationship("ModelForecast")
