# app/routes/routes_model.py
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.db import get_db
from app.models.user import User
from app.models.ml_model import MLModel
from app.models.training_session import TrainingSession
from app.models.candle import Candle
from app.models.model_forecast import ModelForecast
from app.models.bot_trade import BotTrade
from app.schemas.model import ForecastRequest, ForecastResponse, MLModelResponse, TrainingSessionResponse
# Импортируем все функции обучения, включая новую train_adaptive_model
from app.services.ml_service import train_svr, train_gpr, train_adaptive_model
from app.services.prediction_service import build_forecast, compare_forecast_models
from app.services.feature_service import minimum_required_samples, normalize_horizon, horizon_to_steps
from app.services.stock_service import StockService
from app.core.auth import get_current_user
from sqlalchemy import func

router = APIRouter(prefix="/models", tags=["ML Models"])


@router.post("/forecast", response_model=ForecastResponse)
def forecast_model(
        forecast_request: ForecastRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Одноразовый прогноз цены и торговая рекомендация для вкладки AI-моделей.
    Сделки здесь не исполняются: endpoint только обучает модель, строит прогноз и сохраняет forecast.
    """
    try:
        return build_forecast(db=db, user_id=current_user.id, request=forecast_request)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Forecast failed: {str(exc)}")



def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _feature_names(lags: int) -> List[str]:
    normalized_lags = max(int(lags or 10), 2)
    names: List[str] = []
    names.extend([f"close_lag_{lag}" for lag in range(1, normalized_lags + 1)])
    names.extend([f"return_lag_{lag}" for lag in range(1, normalized_lags + 1)])
    names.extend(["rolling_mean_5", "rolling_mean_10", "rolling_std_5", "rolling_std_10"])
    names.extend([f"volume_lag_{lag}" for lag in range(1, normalized_lags + 1)])
    return names


def _forecast_to_dict(item: ModelForecast, trade_count: int = 0) -> Dict[str, Any]:
    metrics = item.metrics or {}
    model_params = item.model_params or {}
    return {
        "id": item.id,
        "forecast_id": item.id,
        "figi": item.figi,
        "ticker": item.ticker,
        "account_id": model_params.get("account_id"),
        "horizon": item.horizon,
        "model_type": item.model_type,
        "model_type_effective": item.model_type_effective,
        "hyperparam_mode": item.hyperparam_mode,
        "current_price": _safe_float(item.current_price),
        "predicted_price": _safe_float(item.predicted_price),
        "price_delta": _safe_float(item.price_delta),
        "price_delta_percent": _safe_float(item.price_delta_percent),
        "recommendation": item.recommendation,
        "recommendation_message": item.recommendation_message,
        "metrics": metrics,
        "model_params": model_params,
        "trade_count": trade_count,
        "has_trade": trade_count > 0,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.post("/compare", response_model=Dict[str, Any])
def compare_models(
        forecast_request: ForecastRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Builds the same forecast request with SVR, GPR and adaptive mode.
    Each successful result is persisted as a normal ModelForecast so the comparison
    remains visible in forecast history and analytics.
    """
    try:
        return compare_forecast_models(db=db, user_id=current_user.id, request=forecast_request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/forecasts", response_model=Dict[str, Any])
def list_forecasts(
        figi: Optional[str] = Query(default=None, max_length=32),
        model_type: Optional[str] = Query(default=None, pattern="^(svr|gpr|adaptive)$"),
        horizon: Optional[str] = Query(default=None, pattern="^(1h|1d)$"),
        recommendation: Optional[str] = Query(default=None, max_length=64),
        limit: int = Query(default=30, ge=1, le=200),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    query = db.query(ModelForecast).filter(ModelForecast.user_id == current_user.id)
    if figi:
        query = query.filter(ModelForecast.figi == figi.strip().upper())
    if model_type:
        query = query.filter(ModelForecast.model_type == model_type.strip().lower())
    if horizon:
        query = query.filter(ModelForecast.horizon == normalize_horizon(horizon))
    if recommendation:
        query = query.filter(ModelForecast.recommendation == recommendation)

    items = query.order_by(ModelForecast.created_at.desc()).limit(limit).all()
    ids = [item.id for item in items]
    trade_counts: Dict[int, int] = {}
    if ids:
        rows = (
            db.query(BotTrade.forecast_id, func.count(BotTrade.id))
            .filter(BotTrade.forecast_id.in_(ids))
            .group_by(BotTrade.forecast_id)
            .all()
        )
        trade_counts = {int(forecast_id): int(count) for forecast_id, count in rows if forecast_id is not None}

    return {
        "status": "success",
        "items": [_forecast_to_dict(item, trade_counts.get(item.id, 0)) for item in items],
    }


@router.get("/data-quality", response_model=Dict[str, Any])
def get_model_data_quality(
        figi: str = Query(..., min_length=1, max_length=32),
        horizon: str = Query(default="1h", pattern="^(1h|1d)$"),
        lags: int = Query(default=10, ge=2, le=120),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    normalized_figi = figi.strip().upper()
    normalized_horizon = normalize_horizon(horizon)
    normalized_lags = max(int(lags or 10), 2)
    required_svr = minimum_required_samples(normalized_horizon, normalized_lags)
    required_gpr = required_svr + 20
    candles = (
        db.query(Candle)
        .filter(Candle.user_id == current_user.id, Candle.figi == normalized_figi)
        .order_by(Candle.ts.asc())
        .all()
    )
    close_values = [_safe_float(candle.close, None) for candle in candles]
    valid_close_count = len([value for value in close_values if value is not None])
    candle_count = len(candles)
    first = candles[0].ts.isoformat() if candles and candles[0].ts else None
    last = candles[-1].ts.isoformat() if candles and candles[-1].ts else None

    if valid_close_count >= required_gpr:
        status = "ready_all"
        status_text = "Данных достаточно для SVR, GPR и adaptive."
    elif valid_close_count >= required_svr:
        status = "ready_svr_only"
        status_text = "Данных хватает для SVR, но для GPR/adaptive лучше загрузить больше свечей."
    else:
        status = "not_ready"
        status_text = f"Недостаточно свечей: нужно минимум {required_svr}, доступно {valid_close_count}."

    recent = []
    for candle in candles[-120:]:
        recent.append({
            "time": candle.ts.isoformat() if candle.ts else None,
            "open": _safe_float(candle.open),
            "high": _safe_float(candle.high),
            "low": _safe_float(candle.low),
            "close": _safe_float(candle.close),
            "volume": _safe_float(candle.volume),
        })

    return {
        "status": "success",
        "figi": normalized_figi,
        "horizon": normalized_horizon,
        "horizon_steps": horizon_to_steps(normalized_horizon),
        "lags": normalized_lags,
        "candle_count": candle_count,
        "valid_close_count": valid_close_count,
        "required_samples": {
            "svr": required_svr,
            "gpr": required_gpr,
            "adaptive": required_gpr,
        },
        "first_date": first,
        "last_date": last,
        "quality_status": status,
        "quality_message": status_text,
        "feature_count": len(_feature_names(normalized_lags)),
        "feature_names": _feature_names(normalized_lags),
        "recent_candles": recent,
    }


@router.post("/train/adaptive", response_model=Dict[str, Any])
def train_adaptive_rkhs_model(
        training_data: Dict[str, Any] = Body(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Обучение адаптивной модели RKHS (SVR + GPR) с переключением по волатильности.
    Реализует алгоритм из раздела 1.7.3 курсовой работы.
    """
    try:
        stock_service = StockService(db)

        # 1. Извлечение параметров запроса
        symbol = training_data.get("symbol")
        start_date = training_data.get("start_date")
        end_date = training_data.get("end_date")

        # Параметры адаптивности
        lags = training_data.get("lags", 10)
        threshold = training_data.get("volatility_threshold", 0.8)

        # Имя модели
        model_name = training_data.get("name", f"Adaptive RKHS {datetime.utcnow().strftime('%Y-%m-%d')}")

        if not all([symbol, start_date, end_date]):
            raise HTTPException(status_code=400, detail="Missing symbol, start_date, or end_date")

        # 2. Подготовка данных с лагами. Обработка ошибок данных.
        try:
            X, y = stock_service.prepare_adaptive_data(symbol, start_date, end_date, lags)
        except ValueError as ve:
            # Преобразование специфической ошибки данных в HTTPException 400
            raise HTTPException(status_code=400, detail=str(ve))

        # Это условие теперь должно быть практически недостижимо благодаря проверкам в сервисе
        if X.empty:
            raise HTTPException(status_code=400, detail="Недостаточно данных для генерации лагов после предобработки.")

        # 3. Конфигурация под-моделей
        svr_config = training_data.get("svr_params", {'C': 1.0, 'epsilon': 0.1, 'gamma': 'scale'})
        gpr_config = training_data.get("gpr_params", {'nu': 1.5, 'length_scale': 1.0})

        # 4. Обучение адаптивной модели
        model, metrics = train_adaptive_model(
            X.values,
            y.values,
            threshold=threshold,
            svr_config=svr_config,
            gpr_config=gpr_config
        )

        # 5. Сохранение метаданных модели в БД
        db_model = MLModel(
            user_id=current_user.id,
            name=model_name,
            description="Adaptive RKHS: SVR(RBF) for stable, GPR(Matern) for volatile regimes.",
            model_type="ADAPTIVE_RKHS",
            model_params={
                "volatility_threshold": threshold,
                "lags": lags,
                "svr_config": svr_config,
                "gpr_config": gpr_config
            },
            training_metrics=metrics,
            feature_columns=X.columns.tolist(),
            target_column="close",
            model_size_bytes=1024 * 1024,  # Mock size
            is_active=True
        )

        # 6. Запись сессии обучения
        stock_obj = stock_service.get_stock_by_symbol(symbol)
        stock_id = stock_obj.id if stock_obj else 0

        training_session = TrainingSession(
            user_id=current_user.id,
            stock_id=stock_id,
            ml_model=db_model,
            name=f"Training Session: {model_name}",
            feature_columns=X.columns.tolist(),
            target_column="close",
            train_start_date=start_date,
            train_end_date=end_date,
            train_samples=len(X),
            training_time_seconds=0.5  # Mock time
        )

        db.add(db_model)
        db.add(training_session)
        db.commit()
        db.refresh(db_model)

        return {
            "status": "success",
            "model_id": db_model.id,
            "metrics": metrics,
            "config": {
                "threshold": threshold,
                "lags": lags
            }
        }

    except HTTPException:
        # Перебрасываем HTTPException (400) с подробным описанием
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Adaptive training failed: {str(e)}")


# --- Оставляем старые эндпоинты для совместимости ---

@router.post("/train/svr", response_model=Dict[str, Any])
def train_svr_model(
        training_data: Dict[str, Any] = Body(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Обычный SVR (из предыдущих версий)"""
    try:
        stock_service = StockService(db)
        symbol = training_data.get("symbol")
        start_date = training_data.get("start_date")
        end_date = training_data.get("end_date")

        if "X" in training_data and "y" in training_data:
            X = training_data["X"]
            y = training_data["y"]
        else:
            X_df, y_series = stock_service.prepare_training_data(symbol, start_date, end_date)
            X = X_df.values
            y = y_series.values

        params = {
            'C': training_data.get('C', 1.0),
            'epsilon': training_data.get('epsilon', 0.1),
            'gamma': training_data.get('gamma', 'scale')
        }

        model, metrics = train_svr(X, y, **params)

        return {"status": "success", "metrics": metrics}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/gpr", response_model=Dict[str, Any])
def train_gpr_model(
        training_data: Dict[str, Any] = Body(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Обычный GPR (из предыдущих версий)"""
    try:
        stock_service = StockService(db)

        if "X" in training_data and "y" in training_data:
            X = training_data["X"]
            y = training_data["y"]
        else:
            symbol = training_data.get("symbol")
            X_df, y_series = stock_service.prepare_training_data(symbol, training_data.get("start_date"),
                                                                 training_data.get("end_date"))
            X = X_df.values
            y = y_series.values

        params = {
            'nu': training_data.get('nu', 1.5),
            'length_scale': training_data.get('length_scale', 1.0)
        }

        model, metrics = train_gpr(X, y, **params)
        return {"status": "success", "metrics": metrics}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-models", response_model=List[MLModelResponse])
def get_user_models(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    models = db.query(MLModel).filter(
        MLModel.user_id == current_user.id,
        MLModel.is_active == True
    ).order_by(MLModel.created_at.desc()).all()
    return models
