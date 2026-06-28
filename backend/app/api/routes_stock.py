# app/routes/routes_stock.py
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.stock import Stock
from app.models.user import User
from app.schemas.stock import StockPriceResponse, StockResponse, StockWithPrices
from app.services.stock_service import StockService

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("/", response_model=List[StockResponse])
def get_stocks(
    skip: int = 0,
    limit: int = 100,
    sector: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Stock)
    if sector:
        query = query.filter(Stock.sector == sector)
    return query.offset(skip).limit(limit).all()


@router.get("/{symbol}", response_model=StockWithPrices)
def get_stock_with_prices(
    symbol: str,
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stock_service = StockService(db)
    stock = stock_service.get_stock_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    prices = stock_service.get_stock_prices(symbol, start_date, end_date)
    return StockWithPrices(
        id=stock.id,
        symbol=stock.symbol,
        name=stock.name,
        sector=stock.sector,
        industry=stock.industry,
        exchange=stock.exchange,
        created_at=stock.created_at,
        prices=prices,
    )


@router.get("/{symbol}/prices", response_model=List[StockPriceResponse])
def get_stock_prices(
    symbol: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stock_service = StockService(db)
    if not stock_service.get_stock_by_symbol(symbol):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    prices = stock_service.get_stock_prices(symbol, start_date, end_date)
    if not prices:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No price data found")
    return prices


@router.get("/{symbol}/features")
def get_stock_features(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stock_service = StockService(db)
    if not stock_service.get_stock_by_symbol(symbol):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    X, y = stock_service.prepare_training_data(symbol, start_date, end_date)
    if X.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data available for the given period")
    return {"features": X.to_dict("records"), "target": y.tolist(), "feature_columns": X.columns.tolist(), "samples": len(X)}
