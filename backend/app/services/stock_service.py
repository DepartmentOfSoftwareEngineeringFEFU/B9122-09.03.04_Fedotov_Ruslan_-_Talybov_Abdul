# app/services/stock_service.py
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.stock import Stock, StockPrice


class StockService:
    def __init__(self, db: Session):
        self.db = db

    def get_stocks(self, skip: int = 0, limit: int = 100) -> List[Stock]:
        return self.db.query(Stock).offset(skip).limit(limit).all()

    def get_stock_by_symbol(self, symbol: str) -> Optional[Stock]:
        """Read stock metadata without creating rows as a side effect."""
        normalized = (symbol or "").strip().upper()
        if not normalized:
            return None
        return self.db.query(Stock).filter(Stock.symbol == normalized).first()

    def create_stock_metadata(
        self,
        symbol: str,
        name: str,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> Stock:
        normalized = (symbol or "").strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        existing = self.get_stock_by_symbol(normalized)
        if existing:
            return existing
        stock = Stock(
            symbol=normalized,
            name=name or normalized,
            sector=sector,
            industry=industry,
            exchange=exchange,
        )
        self.db.add(stock)
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def get_stock_prices(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[StockPrice]:
        stock = self.get_stock_by_symbol(symbol)
        if not stock:
            return []

        query = self.db.query(StockPrice).filter(StockPrice.stock_id == stock.id)
        if start_date:
            query = query.filter(StockPrice.date >= start_date)
        if end_date:
            query = query.filter(StockPrice.date <= end_date)
        return query.order_by(StockPrice.date).all()

    def get_stock_prices_dataframe(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        prices = self.get_stock_prices(symbol, start_date, end_date)
        if not prices:
            return pd.DataFrame()

        df = pd.DataFrame([
            {
                "date": price.date,
                "open": price.open_price,
                "high": price.high_price,
                "low": price.low_price,
                "close": price.close_price,
                "volume": price.volume,
            }
            for price in prices
        ])
        if not df.empty:
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
        return df

    def calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create a deterministic base feature table for legacy backtest calls."""
        if df.empty or "close" not in df.columns:
            return pd.DataFrame()
        features = df.copy()
        features["returns"] = features["close"].pct_change().replace([np.inf, -np.inf], np.nan)
        features["ma_5"] = features["close"].rolling(window=5, min_periods=1).mean()
        features["ma_10"] = features["close"].rolling(window=10, min_periods=1).mean()
        features["volatility_5"] = features["returns"].rolling(window=5, min_periods=1).std().fillna(0.0)
        return features.dropna()

    def create_lagged_features(self, df: pd.DataFrame, lags: int = 10) -> Tuple[pd.DataFrame, List[str]]:
        df_lags = df.copy()
        feature_cols = []
        for i in range(1, lags + 1):
            col_name = f"lag_{i}"
            df_lags[col_name] = df_lags["close"].shift(i)
            feature_cols.append(col_name)
        df_lags.dropna(inplace=True)
        return df_lags, feature_cols

    def prepare_adaptive_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        lags: int = 10,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        stock_obj = self.get_stock_by_symbol(symbol)
        if not stock_obj:
            raise ValueError(f"Символ '{symbol}' не найден в таблице stocks")

        df = self.get_stock_prices_dataframe(symbol, start_date, end_date)
        if df.empty:
            raise ValueError(
                f"Не найдены ценовые данные для символа '{symbol}' в диапазоне "
                f"с {start_date.strftime('%Y-%m-%d')} по {end_date.strftime('%Y-%m-%d')}."
            )

        required_samples = lags + 1
        if len(df) < required_samples:
            raise ValueError(
                f"Недостаточно ценовых данных. Для {lags} лагов требуется минимум "
                f"{required_samples} точек данных, найдено только {len(df)}."
            )

        df_features, feature_cols = self.create_lagged_features(df, lags=lags)
        if df_features.empty:
            raise ValueError("Ошибка при создании лагов. Недостаточно последовательных записей.")
        return df_features[feature_cols], df_features["close"]

    def prepare_training_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        target_column: str = "returns",
        feature_columns: Optional[List[str]] = None,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        if feature_columns is None:
            feature_columns = ["close"]

        df = self.get_stock_prices_dataframe(symbol, start_date, end_date)
        if df.empty:
            return pd.DataFrame(), pd.Series(dtype=float)

        df["returns"] = df["close"].pct_change()
        df["target"] = df["close"].shift(-1)
        df.dropna(inplace=True)

        available_cols = [c for c in feature_columns if c in df.columns] or ["close"]
        return df[available_cols], df["target"]
