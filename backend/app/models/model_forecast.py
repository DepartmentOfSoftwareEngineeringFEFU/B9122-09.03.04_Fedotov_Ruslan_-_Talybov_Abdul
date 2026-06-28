from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class ModelForecast(Base):
    __tablename__ = "model_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    figi = Column(String(32), nullable=False, index=True)
    ticker = Column(String(32), nullable=True)
    horizon = Column(String(10), nullable=False)  # 1h / 1d
    model_type = Column(String(32), nullable=False)  # svr / gpr / adaptive
    model_type_effective = Column(String(32), nullable=True)
    hyperparam_mode = Column(String(16), nullable=False, default="auto")
    model_params = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    current_price = Column(DECIMAL(15, 6), nullable=False)
    predicted_price = Column(DECIMAL(15, 6), nullable=False)
    price_delta = Column(DECIMAL(15, 6), nullable=False)
    price_delta_percent = Column(DECIMAL(10, 4), nullable=False)
    recommendation = Column(String(64), nullable=False)
    recommendation_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="model_forecasts")
    bot_trades = relationship("BotTrade", back_populates="forecast")
