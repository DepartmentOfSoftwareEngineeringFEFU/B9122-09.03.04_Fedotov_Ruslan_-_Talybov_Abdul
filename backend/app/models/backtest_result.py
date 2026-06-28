# app/models/backtest_result.py
from sqlalchemy import Column, Integer, String, JSON, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.db import Base
from datetime import datetime


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ml_model_id = Column(Integer, ForeignKey("ml_models.id"))
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Backtest parameters
    stock_symbols = Column(JSON)  # List of stock symbols used
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    initial_balance = Column(Float, default=1000.0)
    threshold = Column(Float, default=0.001)

    # Results
    final_balance = Column(Float, nullable=False)
    total_return = Column(Float, nullable=False)  # ROI
    total_trades = Column(Integer, nullable=False)
    win_rate = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    trades = Column(JSON)  # Detailed trades list

    # Metadata
    backtest_config = Column(JSON)  # Full configuration
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="backtest_results")
    ml_model = relationship("MLModel", back_populates="backtest_results")

    def __repr__(self):
        return f"<BacktestResult(id={self.id}, name='{self.name}', return={self.total_return:.2%})>"