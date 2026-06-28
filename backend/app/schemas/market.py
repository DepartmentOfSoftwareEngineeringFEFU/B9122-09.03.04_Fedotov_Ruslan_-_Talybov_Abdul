from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class PopularShareItem(BaseModel):
    figi: str
    ticker: Optional[str] = None
    name: Optional[str] = None
    exchange: str = "MOEX"
    currency: str = "RUB"
    current_price: Optional[float] = None
    lot: int = 1
    lot_price: Optional[float] = None
    instrument_type: Optional[str] = "share"


class PopularSharesResponse(BaseModel):
    status: str = "ok"
    items: List[PopularShareItem]


class InstrumentResponse(BaseModel):
    status: str = "ok"
    figi: str
    ticker: Optional[str] = None
    name: Optional[str] = None
    currency: str = "RUB"
    exchange: Optional[str] = None
    current_price: Optional[float] = None
    lot: int = 1
    lot_price: Optional[float] = None
    instrument_type: Optional[str] = "share"


class CurrentPriceResponse(BaseModel):
    status: str
    figi: str
    current_price: float
    lot: int = 1
    lot_price: Optional[float] = None


class TradingModeResponse(BaseModel):
    status: str = "ok"
    mode: str
    sandbox: bool
    auto_sell_worker_enabled: bool
    auto_sell_poll_seconds: int
    auto_sell_dry_run: bool = True
    bulk_trade_worker_enabled: bool = False
    bulk_trade_worker_poll_seconds: int = 60
    real_trading_enabled: bool = False
