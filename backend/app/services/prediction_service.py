from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candle import Candle
from app.models.model_forecast import ModelForecast
from app.schemas.model import ForecastRequest
from app.services.data_service import ForecastCandleLoad, load_candles_for_forecast
from app.services.feature_service import build_features_for_forecast, minimum_required_samples, normalize_horizon, validate_min_samples
from app.services.instrument_service import get_current_price, get_lot_size, get_portfolio_position, lot_price
from app.services.recommendation_service import build_trade_recommendation

logger = logging.getLogger(__name__)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_model_type(value: str) -> str:
    model_type = (value or "adaptive").strip().lower()
    if model_type not in {"svr", "gpr", "adaptive"}:
        raise ValueError("model_type must be one of: svr, gpr, adaptive")
    return model_type


def _normalize_hyperparam_mode(value: str) -> str:
    mode = (value or "auto").strip().lower()
    if mode not in {"manual", "auto"}:
        raise ValueError("hyperparam_mode must be one of: manual, auto")
    return mode


def _required_samples_by_interval(horizon: str, lags: int) -> Dict[str, int]:
    return {
        "1min": minimum_required_samples(horizon=horizon, lags=lags, interval="1min"),
        "5min": minimum_required_samples(horizon=horizon, lags=lags, interval="5min"),
    }


def _load_candles(db: Session, user_id: int, figi: str, days: int, horizon: str, lags: int) -> ForecastCandleLoad:
    return load_candles_for_forecast(
        db,
        figi=figi,
        days=max(days, 1),
        user_id=user_id,
        min_required_by_interval=_required_samples_by_interval(horizon, lags),
    )


def _train_predict_svr(X: np.ndarray, y: np.ndarray, next_features: np.ndarray, params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    X_scaled = scaler_X.fit_transform(X)
    y_scaled = scaler_y.fit_transform(y.reshape(-1, 1)).ravel()

    model = SVR(
        kernel="rbf",
        C=_to_float(params.get("C"), 1.0),
        epsilon=_to_float(params.get("epsilon"), 0.1),
        gamma=params.get("gamma", "scale"),
    )
    model.fit(X_scaled, y_scaled)

    fitted = scaler_y.inverse_transform(model.predict(X_scaled).reshape(-1, 1)).ravel()
    prediction = scaler_y.inverse_transform(model.predict(scaler_X.transform(next_features)).reshape(-1, 1)).ravel()[0]
    return float(prediction), _metrics(y, fitted)


def _train_predict_gpr(X: np.ndarray, y: np.ndarray, next_features: np.ndarray, params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    X_scaled = scaler_X.fit_transform(X)
    y_scaled = scaler_y.fit_transform(y.reshape(-1, 1)).ravel()

    kernel = ConstantKernel(1.0) * Matern(
        length_scale=_to_float(params.get("length_scale"), 1.0),
        nu=_to_float(params.get("nu"), 1.5),
    )
    model = GaussianProcessRegressor(
        kernel=kernel,
        alpha=_to_float(params.get("alpha"), 1e-10),
        normalize_y=False,
        random_state=42,
    )
    model.fit(X_scaled, y_scaled)

    fitted = scaler_y.inverse_transform(model.predict(X_scaled).reshape(-1, 1)).ravel()
    predicted_scaled, predicted_std_scaled = model.predict(scaler_X.transform(next_features), return_std=True)
    prediction = scaler_y.inverse_transform(predicted_scaled.reshape(-1, 1)).ravel()[0]
    target_std = float(predicted_std_scaled[0] * scaler_y.scale_[0]) if len(predicted_std_scaled) else 0.0
    metrics = _metrics(y, fitted)
    metrics.update({
        "prediction_std": target_std,
        "confidence_interval_low": float(prediction - 1.96 * target_std),
        "confidence_interval_high": float(prediction + 1.96 * target_std),
    })
    return float(prediction), metrics


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "R2": float(r2_score(y_true, y_pred)) if len(y_true) > 1 else 0.0,
    }


def _finite_float_or_none(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def _validation_mae(model_type: str, X: np.ndarray, y: np.ndarray, params: Dict[str, Any]) -> float:
    if len(y) < 10:
        return float("inf")

    split = max(int(len(y) * 0.8), len(y) - 20)
    split = min(max(split, 5), len(y) - 2)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    if len(y_val) == 0:
        return float("inf")

    if model_type == "svr":
        return _validation_mae_svr(X_train, y_train, X_val, y_val, params)

    return _validation_mae_gpr(X_train, y_train, X_val, y_val, params)


def _validation_mae_svr(X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray, params: Dict[str, Any]) -> float:
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    X_train_scaled = scaler_X.fit_transform(X_train)
    y_train_scaled = scaler_y.fit_transform(y_train.reshape(-1, 1)).ravel()
    model = SVR(
        kernel="rbf",
        C=_to_float(params.get("C"), 1.0),
        epsilon=_to_float(params.get("epsilon"), 0.1),
        gamma=params.get("gamma", "scale"),
    )
    model.fit(X_train_scaled, y_train_scaled)
    val_scaled = model.predict(scaler_X.transform(X_val))
    val_pred = scaler_y.inverse_transform(val_scaled.reshape(-1, 1)).ravel()
    return float(mean_absolute_error(y_val, val_pred))


def _validation_mae_gpr(X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray, params: Dict[str, Any]) -> float:
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    X_train_scaled = scaler_X.fit_transform(X_train)
    y_train_scaled = scaler_y.fit_transform(y_train.reshape(-1, 1)).ravel()
    kernel = ConstantKernel(1.0) * Matern(
        length_scale=_to_float(params.get("length_scale"), 1.0),
        nu=_to_float(params.get("nu"), 1.5),
    )
    model = GaussianProcessRegressor(
        kernel=kernel,
        alpha=_to_float(params.get("alpha"), 1e-10),
        normalize_y=False,
        random_state=42,
    )
    model.fit(X_train_scaled, y_train_scaled)
    val_scaled = model.predict(scaler_X.transform(X_val))
    val_pred = scaler_y.inverse_transform(val_scaled.reshape(-1, 1)).ravel()
    return float(mean_absolute_error(y_val, val_pred))


def _auto_svr_params(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    candidates = [
        {"C": 0.1, "epsilon": 0.05, "gamma": "scale"},
        {"C": 1.0, "epsilon": 0.1, "gamma": "scale"},
        {"C": 10.0, "epsilon": 0.1, "gamma": "scale"},
        {"C": 10.0, "epsilon": 0.01, "gamma": "scale"},
        {"C": 100.0, "epsilon": 0.2, "gamma": "auto"},
    ]
    return min(candidates, key=lambda params: _validation_mae("svr", X, y, params))


def _auto_gpr_params(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    candidates = [
        {"nu": 0.5, "length_scale": 0.5, "alpha": 1e-8},
        {"nu": 1.5, "length_scale": 1.0, "alpha": 1e-10},
        {"nu": 1.5, "length_scale": 2.0, "alpha": 1e-8},
        {"nu": 2.5, "length_scale": 1.0, "alpha": 1e-6},
    ]
    return min(candidates, key=lambda params: _validation_mae("gpr", X, y, params))


def _resolve_params(request: ForecastRequest, X: np.ndarray, y: np.ndarray, model_type: str, mode: str) -> Dict[str, Any]:
    if mode == "manual":
        return {
            "svr": request.svr_params or {"C": 1.0, "epsilon": 0.1, "gamma": "scale"},
            "gpr": request.gpr_params or {"nu": 1.5, "length_scale": 1.0, "alpha": 1e-10},
            "adaptive": request.adaptive_params or {"volatility_threshold": 0.8, "ensemble_enabled": True},
        }

    params = {
        "svr": _auto_svr_params(X, y),
        "gpr": _auto_gpr_params(X, y),
        "adaptive": request.adaptive_params or {"volatility_threshold": 0.8, "ensemble_enabled": True},
    }
    if model_type == "svr":
        params["gpr"] = request.gpr_params or {"nu": 1.5, "length_scale": 1.0, "alpha": 1e-10}
    if model_type == "gpr":
        params["svr"] = request.svr_params or {"C": 1.0, "epsilon": 0.1, "gamma": "scale"}
    return params


def _predict_by_model(model_type: str, X: np.ndarray, y: np.ndarray, next_features: np.ndarray, params: Dict[str, Any]) -> Tuple[float, Dict[str, float], str]:
    if model_type == "svr":
        predicted, metrics = _train_predict_svr(X, y, next_features, params["svr"])
        metrics["validation_mae"] = _finite_float_or_none(_validation_mae("svr", X, y, params["svr"]))
        return predicted, metrics, "svr"

    if model_type == "gpr":
        predicted, metrics = _train_predict_gpr(X, y, next_features, params["gpr"])
        metrics["validation_mae"] = _finite_float_or_none(_validation_mae("gpr", X, y, params["gpr"]))
        return predicted, metrics, "gpr"

    svr_pred, svr_metrics = _train_predict_svr(X, y, next_features, params["svr"])
    gpr_pred, gpr_metrics = _train_predict_gpr(X, y, next_features, params["gpr"])
    svr_mae = _validation_mae("svr", X, y, params["svr"])
    gpr_mae = _validation_mae("gpr", X, y, params["gpr"])
    ensemble_enabled = bool(params.get("adaptive", {}).get("ensemble_enabled", True))

    if np.isfinite(svr_mae) and np.isfinite(gpr_mae):
        difference = abs(svr_mae - gpr_mae) / max(min(svr_mae, gpr_mae), 1e-9)
        if ensemble_enabled and difference <= 0.1:
            # Inverse-error weighted ensemble instead of a blind 50/50 average.
            svr_weight_raw = 1 / max(svr_mae, 1e-9)
            gpr_weight_raw = 1 / max(gpr_mae, 1e-9)
            total_weight = svr_weight_raw + gpr_weight_raw
            svr_weight = svr_weight_raw / total_weight
            gpr_weight = gpr_weight_raw / total_weight
            predicted = svr_pred * svr_weight + gpr_pred * gpr_weight
            metrics = {
                "SVR_MAE": float(svr_mae),
                "GPR_MAE": float(gpr_mae),
                "SVR_weight": float(svr_weight),
                "GPR_weight": float(gpr_weight),
                "validation_mae": float((svr_mae * svr_weight) + (gpr_mae * gpr_weight)),
                "MAE": float((svr_metrics["MAE"] * svr_weight) + (gpr_metrics["MAE"] * gpr_weight)),
                "RMSE": float((svr_metrics["RMSE"] * svr_weight) + (gpr_metrics["RMSE"] * gpr_weight)),
                "R2": float((svr_metrics["R2"] * svr_weight) + (gpr_metrics["R2"] * gpr_weight)),
            }
            return float(predicted), metrics, "ensemble"
        if svr_mae < gpr_mae:
            return svr_pred, {**svr_metrics, "SVR_MAE": float(svr_mae), "GPR_MAE": float(gpr_mae), "validation_mae": float(svr_mae)}, "svr"
        return gpr_pred, {**gpr_metrics, "SVR_MAE": float(svr_mae), "GPR_MAE": float(gpr_mae), "validation_mae": float(gpr_mae)}, "gpr"

    return float((svr_pred + gpr_pred) / 2), {
        "MAE": float((svr_metrics["MAE"] + gpr_metrics["MAE"]) / 2),
        "RMSE": float((svr_metrics["RMSE"] + gpr_metrics["RMSE"]) / 2),
        "R2": float((svr_metrics["R2"] + gpr_metrics["R2"]) / 2),
        "validation_mae": None,
    }, "ensemble"


def build_forecast(
    db: Session,
    user_id: int,
    request: ForecastRequest,
    candle_load: ForecastCandleLoad | None = None,
) -> Dict[str, Any]:
    figi = request.figi.strip().upper()
    if not figi:
        raise ValueError("figi is required")
    account_id = (request.account_id or "").strip() or None

    horizon = normalize_horizon(request.horizon)
    model_type = _normalize_model_type(request.model_type)
    mode = _normalize_hyperparam_mode(request.hyperparam_mode)
    threshold = max(_to_float(request.flat_threshold_percent, 1.0), 0.01)
    lags = min(max(int(request.lags or 10), 2), 30)

    candle_load = candle_load or _load_candles(db, user_id=user_id, figi=figi, days=request.days, horizon=horizon, lags=lags)
    candles = candle_load.candles
    candle_interval = candle_load.interval or "1min"
    validate_min_samples(candles, model_type=model_type, horizon=horizon, lags=lags, interval=candle_interval)
    feature_result = build_features_for_forecast(candles, horizon=horizon, lags=lags, interval=candle_interval)
    X, y, next_features = feature_result.X, feature_result.y, feature_result.next_features

    # GPR is cubic by sample count, so keep the MVP forecast bounded for API usage.
    max_training_samples_by_model = {
        "svr": int(settings.AI_FORECAST_MAX_SVR_SAMPLES),
        "gpr": int(settings.AI_FORECAST_MAX_GPR_SAMPLES),
        "adaptive": int(settings.AI_FORECAST_MAX_ADAPTIVE_SAMPLES),
    }
    max_training_samples = max(50, max_training_samples_by_model.get(model_type, 450))
    if len(y) > max_training_samples:
        X = X[-max_training_samples:]
        y = y[-max_training_samples:]

    model_params = _resolve_params(request, X, y, model_type, mode)
    predicted_price, metrics, effective_model = _predict_by_model(model_type, X, y, next_features, model_params)
    metrics.update({
        "train_samples": int(len(y)),
        "validation_samples": int(max(0, len(y) - max(int(len(y) * 0.8), 0))),
        "feature_count": int(len(feature_result.feature_names)),
        "model_type_used": effective_model,
        "candle_interval": candle_interval,
        "horizon_steps": int(feature_result.horizon_steps),
        "candle_count": int(len(candles)),
        "candle_source": candle_load.source,
    })

    fallback_price = _to_float(getattr(candles[-1], "close", None), predicted_price) if candles else predicted_price
    current_price = get_current_price(user_id=user_id, figi=figi, fallback_price=fallback_price)
    current_price = _to_float(current_price, fallback_price)

    price_delta = predicted_price - current_price
    price_delta_percent = (price_delta / current_price * 100) if current_price else 0.0
    lot = get_lot_size(user_id=user_id, figi=figi)
    current_lot_price = lot_price(current_price, lot) or 0.0
    predicted_lot_price = lot_price(predicted_price, lot) or 0.0

    position = get_portfolio_position(user_id=user_id, figi=figi, account_id=account_id)
    recommendation = build_trade_recommendation(
        price_delta_percent=price_delta_percent,
        flat_threshold_percent=threshold,
        position=position,
        current_price=current_price,
        predicted_price=predicted_price,
        lot=lot,
    )
    action = recommendation["action"]
    message = recommendation["message"]

    forecast = ModelForecast(
        user_id=user_id,
        figi=figi,
        ticker=request.ticker,
        horizon=horizon,
        model_type=model_type,
        model_type_effective=effective_model,
        hyperparam_mode=mode,
        model_params={
            **model_params,
            "lags": lags,
            "source": request.source,
            "account_id": account_id,
            "feature_names": feature_result.feature_names,
            "candle_interval": candle_interval,
            "horizon_steps": int(feature_result.horizon_steps),
            "candle_count": int(len(candles)),
            "candle_source": candle_load.source,
            "candle_attempts": candle_load.attempts,
        },
        metrics=metrics,
        current_price=Decimal(str(round(current_price, 6))),
        predicted_price=Decimal(str(round(predicted_price, 6))),
        price_delta=Decimal(str(round(price_delta, 6))),
        price_delta_percent=Decimal(str(round(price_delta_percent, 4))),
        recommendation=action,
        recommendation_message=message,
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)

    return {
        "status": "success",
        "forecast_id": forecast.id,
        "figi": figi,
        "ticker": request.ticker,
        "account_id": account_id,
        "source": request.source,
        "horizon": horizon,
        "model_type": model_type,
        "model_type_effective": effective_model,
        "hyperparam_mode": mode,
        "current_price": float(current_price),
        "predicted_price": float(predicted_price),
        "lot": int(lot),
        "lot_price": float(current_lot_price),
        "predicted_lot_price": float(predicted_lot_price),
        "price_delta": float(price_delta),
        "price_delta_percent": float(price_delta_percent),
        "flat_threshold_percent": float(threshold),
        "metrics": metrics,
        "model_params": {
            **model_params,
            "lags": lags,
            "source": request.source,
            "account_id": account_id,
            "feature_names": feature_result.feature_names,
            "candle_interval": candle_interval,
            "horizon_steps": int(feature_result.horizon_steps),
            "candle_count": int(len(candles)),
            "candle_source": candle_load.source,
            "candle_attempts": candle_load.attempts,
        },
        "candle_interval": candle_interval,
        "candle_source": candle_load.source,
        "recommendation": recommendation,
    }


def _request_to_dict(request: ForecastRequest) -> Dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump()
    return request.dict()


def _score_from_metrics(item: Dict[str, Any], *names: str, default: float = float("inf")) -> float:
    metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
    for name in names:
        value = metrics.get(name)
        score = _to_float(value, default)
        if np.isfinite(score):
            return score
    return default


def _comparison_failure_message(results: List[Dict[str, Any]]) -> str:
    details = []
    for item in results:
        detail = str(item.get("detail") or "").strip()
        if detail and detail not in details:
            details.append(detail)
    if not details:
        return "Не удалось построить сравнение моделей: все модели вернули ошибку"
    return "Не удалось построить сравнение моделей: " + " | ".join(details[:3])


def compare_forecast_models(db: Session, user_id: int, request: ForecastRequest) -> Dict[str, Any]:
    """Build SVR, GPR and adaptive forecasts with one stable response shape."""
    requested_models = ["svr", "gpr", "adaptive"]
    base_payload = _request_to_dict(request)
    results: List[Dict[str, Any]] = []
    horizon = normalize_horizon(request.horizon)
    lags = min(max(int(request.lags or 10), 2), 30)
    shared_candle_load = _load_candles(
        db,
        user_id=user_id,
        figi=request.figi.strip().upper(),
        days=request.days,
        horizon=horizon,
        lags=lags,
    )

    for model_type in requested_models:
        payload = {**base_payload, "model_type": model_type}
        try:
            model_request = ForecastRequest(**payload)
            result = build_forecast(db=db, user_id=user_id, request=model_request, candle_load=shared_candle_load)
            result["compare_status"] = "success"
            results.append(result)
        except ValueError as exc:
            db.rollback()
            results.append({"model_type": model_type, "compare_status": "error", "detail": str(exc)})
        except Exception as exc:  # noqa: BLE001 - comparison should return partial model errors
            db.rollback()
            results.append({"model_type": model_type, "compare_status": "error", "detail": str(exc)})

    successful = [item for item in results if item.get("compare_status") == "success"]
    if not successful:
        raise ValueError(_comparison_failure_message(results))

    best_by_validation = min(successful, key=lambda item: _score_from_metrics(item, "validation_mae", "MAE"))
    best_by_mae = min(successful, key=lambda item: _score_from_metrics(item, "MAE"))
    best_direction = max(
        successful,
        key=lambda item: _to_float((item.get("metrics") or {}).get("directional_accuracy"), -1.0),
    )

    return {
        "status": "success",
        "figi": request.figi.strip().upper(),
        "ticker": request.ticker,
        "account_id": request.account_id,
        "horizon": request.horizon,
        "hyperparam_mode": request.hyperparam_mode,
        "results": results,
        "summary": {
            "best_by_validation_mae": best_by_validation.get("model_type_effective") or best_by_validation.get("model_type"),
            "best_by_validation_mae_requested": best_by_validation.get("model_type"),
            "best_by_mae": best_by_mae.get("model_type_effective") or best_by_mae.get("model_type"),
            "best_by_mae_requested": best_by_mae.get("model_type"),
            "best_by_directional_accuracy": best_direction.get("model_type_effective") or best_direction.get("model_type"),
            "successful_models": len(successful),
            "failed_models": len(results) - len(successful),
            "best_forecast": best_by_validation,
        },
    }
