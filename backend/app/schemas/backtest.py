# app/schemas/routes_backtest.py
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class BacktestRequest(BaseModel):
    ml_model_id: int
    stock_symbols: List[str]
    start_date: datetime
    end_date: datetime
    initial_balance: float = 1000.0
    threshold: float = 0.001
    name: str
    description: Optional[str] = None


class BacktestResultBase(BaseModel):
    name: str
    description: Optional[str] = None
    final_balance: float
    total_return: float
    total_trades: int
    win_rate: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None


class BacktestResultResponse(BacktestResultBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    ml_model_id: Optional[int] = None
    stock_symbols: List[str]
    start_date: datetime
    end_date: datetime
    initial_balance: float
    threshold: float
    trades: List[Dict[str, Any]]
    created_at: datetime
