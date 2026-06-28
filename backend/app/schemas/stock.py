# app/schemas/routes_stock.py
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class StockBase(BaseModel):
    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    exchange: Optional[str] = None


class StockCreate(StockBase):
    pass


class StockResponse(StockBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class StockPriceBase(BaseModel):
    date: datetime
    close_price: float
    volume: Optional[int] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None


class StockPriceResponse(StockPriceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int


class StockWithPrices(StockResponse):
    prices: List[StockPriceResponse] = []
