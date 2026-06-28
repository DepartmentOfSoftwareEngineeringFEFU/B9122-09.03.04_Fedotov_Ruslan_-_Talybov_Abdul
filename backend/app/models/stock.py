# app/models/routes_stock.py
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base
from datetime import datetime


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    sector = Column(String(100))
    industry = Column(String(100))
    exchange = Column(String(50))
    country = Column(String(50))
    market_cap = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    prices = relationship("StockPrice", back_populates="stock")
    training_sessions = relationship("TrainingSession", back_populates="stock")

    def __repr__(self):
        return f"<Stock(id={self.id}, symbol='{self.symbol}', name='{self.name}')>"


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer)
    adjusted_close = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    stock = relationship("Stock", back_populates="prices")

    def __repr__(self):
        return f"<StockPrice(id={self.id}, stock_id={self.stock_id}, date={self.date}, close={self.close_price})>"