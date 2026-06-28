# routes_market.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
import logging

from app.services.data_service import fetch_and_store_candles
from app.core.auth import get_current_user
from app.core.tinkoff_client import TinkoffClient
from app.core.db import SessionLocal, get_db  # ← ДОБАВИТЬ ИМПОРТ
from app.models.candle import Candle  # ← ДОБАВИТЬ ИМПОРТ
from app.schemas.market import CurrentPriceResponse, InstrumentResponse, PopularSharesResponse, TradingModeResponse
from app.services.instrument_service import get_instrument_by_figi, get_trading_mode, list_moex_shares, list_popular_moex_shares, lot_price

router = APIRouter(prefix="/market", tags=["Market"])
logger = logging.getLogger(__name__)


@router.get("/popular-shares", response_model=PopularSharesResponse)
def get_popular_shares(current_user=Depends(get_current_user)):
    """Статичный seed-список популярных акций MOEX для выбора во вкладке AI-моделей."""
    return {
        "status": "ok",
        "items": list_popular_moex_shares(user_id=current_user.id),
    }


@router.get("/shares", response_model=PopularSharesResponse)
def get_shares(
    limit: int = Query(1000, ge=1, le=1000),
    current_user=Depends(get_current_user),
):
    """Расширенный список акций MOEX для поиска инструмента в разделе рынка."""
    return {
        "status": "ok",
        "items": list_moex_shares(user_id=current_user.id, limit=limit),
    }


@router.get("/trading-mode", response_model=TradingModeResponse)
def trading_mode(current_user=Depends(get_current_user)):
    """Expose sandbox/real mode so the UI can warn before broker actions."""
    return {"status": "ok", **get_trading_mode(user_id=current_user.id)}


@router.get("/instrument/{figi}", response_model=InstrumentResponse)
def get_instrument(figi: str, current_user=Depends(get_current_user)):
    """Стабильный контракт проверки инструмента по FIGI для вкладки AI-моделей."""
    try:
        instrument = get_instrument_by_figi(user_id=current_user.id, figi=figi)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "status": "ok",
        **instrument,
    }


# Эндпоинт для загрузки свечей
@router.get("/candles/{figi}")
def load_candles(
    figi: str,
    days: int = Query(1, ge=1, le=365),
    interval: str = Query("1min", pattern="^(1min|1m|5min|5m|15min|15m|hour|1h|day|1d)$"),
    current_user=Depends(get_current_user),
):
    candles = fetch_and_store_candles(figi, days, user_id=current_user.id, interval=interval)
    return {
        "status": "ok",
        "candles_saved": len(candles),
        "candles": candles
    }


# Эндпоинт для получения текущей цены
@router.get("/current-price/{figi}", response_model=CurrentPriceResponse)
def get_current_price(figi: str, current_user=Depends(get_current_user)):
    logger.info(f"Запрос текущей цены для FIGI: {figi} от пользователя {current_user.id}")

    try:
        client = TinkoffClient(user_id=current_user.id)
        price_info = client.get_current_prices([figi])

        logger.debug(f"Ответ Tinkoff API для {figi}: {price_info}")

        if price_info:
            current_price = price_info[0]["price"]
            lot = price_info[0].get("lot") or get_instrument_by_figi(user_id=current_user.id, figi=figi).get("lot") or 1
            logger.info(f"Текущая цена для {figi}: {current_price} ₽ за 1 шт., лот {lot} шт.")
            return {
                "status": "ok",
                "figi": figi,
                "current_price": current_price,
                "lot": lot,
                "lot_price": lot_price(current_price, lot),
            }
        else:
            logger.warning(f"Цена не найдена для FIGI: {figi}")
            raise HTTPException(status_code=404, detail="Price not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении цены для {figi}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching price: {str(e)}")


# НОВЫЕ ЭНДПОИНТЫ ДЛЯ УПРАВЛЕНИЯ СВЕЧАМИ ПОЛЬЗОВАТЕЛЯ

@router.get("/user-candles")
def get_user_candles(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)  # ← Используем зависимость get_db
):
    """Получить список всех FIGI, по которым пользователь запрашивал свечи"""
    try:
        # Группируем по FIGI с информацией о количестве свечей и датах
        candle_stats = db.query(
            Candle.figi,
            func.count(Candle.id).label('candle_count'),
            func.min(Candle.ts).label('first_date'),
            func.max(Candle.ts).label('last_date')
        ).filter(
            Candle.user_id == current_user.id
        ).group_by(Candle.figi).offset(skip).limit(limit).all()

        result = []
        for figi, count, first_date, last_date in candle_stats:
            result.append({
                "figi": figi,
                "candle_count": count,
                "first_date": first_date.isoformat() if first_date else None,
                "last_date": last_date.isoformat() if last_date else None
            })

        return {
            "status": "ok",
            "total_figi": len(result),
            "candles_by_figi": result
        }
    except Exception as e:
        logger.error(f"Ошибка при получении списка свечей пользователя: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/user-candles/{figi}")
def delete_user_candles(
        figi: str,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)  # ← Используем зависимость get_db
):
    """Удалить все свечи пользователя для указанной FIGI"""
    try:
        # Считаем сколько будет удалено
        count = db.query(Candle).filter(
            Candle.user_id == current_user.id,
            Candle.figi == figi
        ).count()

        # Удаляем
        deleted_count = db.query(Candle).filter(
            Candle.user_id == current_user.id,
            Candle.figi == figi
        ).delete()

        db.commit()

        logger.info(f"User {current_user.id} deleted {deleted_count} candles for FIGI {figi}")

        return {
            "status": "ok",
            "deleted_count": deleted_count,
            "figi": figi,
            "message": f"Deleted {deleted_count} candles for {figi}"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting candles for user {current_user.id}, FIGI {figi}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error deleting candles")


@router.get("/user-candles/{figi}/data")
def get_candle_data_for_ml(
        figi: str,
        start_date: str = None,
        end_date: str = None,
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db)  # ← Используем зависимость get_db
):
    """Получить данные свечей для ML модели"""
    try:
        query = db.query(Candle).filter(
            Candle.user_id == current_user.id,
            Candle.figi == figi
        )

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Candle.ts >= start_dt)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid start_date format: {str(e)}")

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Candle.ts <= end_dt)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid end_date format: {str(e)}")

        candles = query.order_by(Candle.ts).all()

        ml_data = []
        for candle in candles:
            ml_data.append({
                "datetime": candle.ts.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume
            })

        return {
            "status": "ok",
            "figi": figi,
            "candle_count": len(ml_data),
            "data": ml_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении данных для ML: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
