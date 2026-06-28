# app/models/user.py (обновленная)
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.core.db import Base
from app.core.crypto import mask_secret


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    tinkoff_token = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def has_tinkoff_token(self) -> bool:
        return bool((self.tinkoff_token or "").strip())

    @property
    def tinkoff_token_masked(self) -> str | None:
        return mask_secret(self.tinkoff_token)

    # Добавляем отношения
    ml_models = relationship("MLModel", back_populates="user")
    backtest_results = relationship("BacktestResult", back_populates="user")
    training_sessions = relationship("TrainingSession", back_populates="user")
    bot_trades = relationship("BotTrade", back_populates="user")
    model_forecasts = relationship("ModelForecast", back_populates="user")
