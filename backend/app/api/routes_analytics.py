from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import logging
from typing import Any, Dict, Iterable, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from fastapi.params import Query as QueryParam
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.api.routes_trade import format_portfolio
from app.core.db import get_db
from app.models.backtest_result import BacktestResult
from app.models.bot_trade import BotTrade
from app.models.model_forecast import ModelForecast
from app.models.order import Order
from app.models.user import User
from app.services.bot_analytics_service import calculate_bot_trade_analytics
from app.services.trade_service import get_portfolio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round(value: Any, digits: int = 2) -> float:
    return round(_to_float(value), digits)


def _nullable_round(value: Any, digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(_to_float(value), digits)


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _query_default(value: Any) -> Any:
    if isinstance(value, QueryParam):
        return value.default
    return value


def _clean_datetime(value: Any) -> Optional[datetime]:
    value = _query_default(value)
    return value if isinstance(value, datetime) else None


def _clean_text(value: Any) -> Optional[str]:
    value = _query_default(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metric(metrics: Any, *names: str) -> Optional[float]:
    if not isinstance(metrics, dict):
        return None
    lowered = {str(key).lower(): value for key, value in metrics.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return _to_float(value)
    return None


def _avg(values: Iterable[Optional[float]]) -> Optional[float]:
    clean = [float(value) for value in values if value is not None]
    return (sum(clean) / len(clean)) if clean else None


def _safe_ordered_query(query: Any, *order_by: Any) -> Any:
    try:
        return query.order_by(*order_by)
    except Exception:
        return query


def _safe_limit(query: Any, limit: int) -> Any:
    try:
        return query.limit(limit)
    except Exception:
        return query


def _all(query: Any) -> list:
    try:
        return query.all()
    except Exception:
        logger.exception("Analytics query failed")
        return []


def _apply_common_filters(
    query: Any,
    model: Any,
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    figi: Optional[str] = None,
    model_type: Optional[str] = None,
    horizon: Optional[str] = None,
) -> Any:
    if date_from is not None and hasattr(model, "created_at"):
        query = query.filter(model.created_at >= date_from)
    if date_to is not None and hasattr(model, "created_at"):
        query = query.filter(model.created_at <= date_to)
    if figi and hasattr(model, "figi"):
        query = query.filter(model.figi == figi.strip().upper())
    if horizon and hasattr(model, "horizon"):
        query = query.filter(model.horizon == horizon)

    if model_type:
        normalized = model_type.strip().lower()
        if model is BotTrade:
            query = query.filter(
                (BotTrade.model_type_used == normalized) | (BotTrade.model_type_requested == normalized)
            )
        elif model is ModelForecast:
            query = query.filter(
                (ModelForecast.model_type == normalized) | (ModelForecast.model_type_effective == normalized)
            )
    return query


def _empty_portfolio() -> Dict[str, Any]:
    return {
        "total_value": 0.0,
        "cash_balance": 0.0,
        "total_stocks_value": 0.0,
        "total_profit": 0.0,
        "total_profit_percent": 0.0,
        "positions_count": 0,
        "positions": [],
    }


def _empty_bot_analytics() -> Dict[str, Any]:
    return {
        "total_trades": 0,
        "closed_trades": 0,
        "open_trades": 0,
        "scheduled_auto_sells": 0,
        "failed_trades": 0,
        "realized_pnl": 0.0,
        "realized_pnl_percent": 0.0,
        "win_rate": 0.0,
        "avg_trade_return_percent": 0.0,
        "best_trade_percent": 0.0,
        "worst_trade_percent": 0.0,
        "by_model": {},
    }


def _serialize_manual_order(order: Order) -> Dict[str, Any]:
    return {
        "id": order.id,
        "figi": order.figi,
        "side": order.side,
        "quantity": order.qty,
        "price": _round(order.price, 6),
        "amount": _round(order.amount),
        "average_price_after": _round(order.average_price_after, 6),
        "position_qty_after": order.position_qty_after,
        "realized_pnl": _nullable_round(order.realized_pnl),
        "realized_pnl_percent": _nullable_round(order.realized_pnl_percent),
        "status": order.status,
        "source": order.source,
        "created_at": _iso(order.created_at),
    }


def _manual_trade_summary(
    db: Session,
    user_id: int,
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    figi: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    query = db.query(Order).filter(Order.user_id == user_id)
    if account_id:
        query = query.filter(Order.account_id == account_id)
    query = _apply_common_filters(query, Order, date_from=date_from, date_to=date_to, figi=figi)
    orders = _all(query)

    buy_orders = [order for order in orders if _lower(order.side) == "buy"]
    sell_orders = [order for order in orders if _lower(order.side) == "sell"]
    buy_amount = sum(_to_float(order.amount) for order in buy_orders)
    sell_amount = sum(_to_float(order.amount) for order in sell_orders)
    realized_values = [_to_float(order.realized_pnl) for order in orders if order.realized_pnl is not None]
    realized_percent_values = [
        _to_float(order.realized_pnl_percent)
        for order in orders
        if order.realized_pnl_percent is not None
    ]

    recent_query = db.query(Order).filter(Order.user_id == user_id)
    if account_id:
        recent_query = recent_query.filter(Order.account_id == account_id)
    recent_query = _apply_common_filters(recent_query, Order, date_from=date_from, date_to=date_to, figi=figi)
    recent_query = _safe_ordered_query(recent_query, Order.created_at.desc(), Order.id.desc())
    recent_orders = _all(_safe_limit(recent_query, 30))

    return {
        "total_trades": len(orders),
        "buy_trades": len(buy_orders),
        "sell_trades": len(sell_orders),
        "buy_amount": round(buy_amount, 2),
        "sell_amount": round(sell_amount, 2),
        "net_cash_flow": round(sell_amount - buy_amount, 2),
        "realized_pnl": round(sum(realized_values), 2),
        "avg_realized_pnl_percent": round(_avg(realized_percent_values) or 0.0, 2),
        "recent": [_serialize_manual_order(order) for order in recent_orders],
    }


def _serialize_bot_trade(trade: BotTrade) -> Dict[str, Any]:
    return {
        "id": trade.id,
        "forecast_id": trade.forecast_id,
        "figi": trade.figi,
        "ticker": trade.ticker,
        "instrument_name": trade.instrument_name,
        "side": trade.side,
        "quantity": trade.quantity,
        "price": _round(trade.price, 6),
        "amount": _round(trade.amount),
        "current_price": _nullable_round(trade.current_price, 6),
        "predicted_price": _nullable_round(trade.predicted_price, 6),
        "price_delta_percent": _nullable_round(trade.price_delta_percent),
        "average_buy_price": _nullable_round(trade.average_buy_price, 6),
        "cash_balance_at_signal": _nullable_round(trade.cash_balance_at_signal),
        "status": trade.status,
        "source": trade.source,
        "account_id": trade.account_id,
        "recommendation_action": trade.recommendation_action,
        "horizon": trade.horizon,
        "model_type_requested": trade.model_type_requested,
        "model_type_used": trade.model_type_used,
        "order_id": trade.order_id,
        "broker_order_id": trade.broker_order_id,
        "auto_sell_enabled": bool(trade.auto_sell_enabled),
        "scheduled_sell_at": _iso(trade.scheduled_sell_at),
        "sell_target_price": _nullable_round(trade.sell_target_price, 6),
        "realized_pnl": _nullable_round(trade.realized_pnl),
        "realized_pnl_percent": _nullable_round(trade.realized_pnl_percent),
        "error_message": trade.error_message,
        "created_at": _iso(trade.created_at),
        "confirmed_at": _iso(trade.confirmed_at),
        "executed_at": _iso(trade.executed_at),
        "closed_at": _iso(trade.closed_at),
    }


def _recent_bot_trades(
    db: Session,
    user_id: int,
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    figi: Optional[str] = None,
    model_type: Optional[str] = None,
    horizon: Optional[str] = None,
    account_id: Optional[str] = None,
) -> list:
    account_id = (account_id or "").strip() or None
    query = db.query(BotTrade).filter(BotTrade.user_id == user_id)
    if account_id:
        query = query.filter(BotTrade.account_id == account_id)
    query = _apply_common_filters(
        query,
        BotTrade,
        date_from=date_from,
        date_to=date_to,
        figi=figi,
        model_type=model_type,
        horizon=horizon,
    )
    query = _safe_ordered_query(query, BotTrade.created_at.desc())
    trades = _all(_safe_limit(query, 80))
    if account_id:
        trades = [trade for trade in trades if getattr(trade, "account_id", None) == account_id]
    return [_serialize_bot_trade(trade) for trade in trades]


def _bot_timeline(history: list) -> list:
    closed = [trade for trade in history if trade.get("realized_pnl") not in (None, 0)]
    closed.sort(key=lambda item: item.get("closed_at") or item.get("executed_at") or item.get("created_at") or "")
    cumulative = 0.0
    points = []
    for trade in closed:
        pnl = _to_float(trade.get("realized_pnl"))
        cumulative += pnl
        points.append({
            "date": (trade.get("closed_at") or trade.get("executed_at") or trade.get("created_at") or "")[:10],
            "ticker": trade.get("ticker") or trade.get("figi"),
            "model": trade.get("model_type_used") or trade.get("model_type_requested") or "unknown",
            "pnl": round(pnl, 2),
            "cumulative_pnl": round(cumulative, 2),
            "return_percent": _round(trade.get("realized_pnl_percent")),
        })
    return points


def _forecast_account_id(forecast: ModelForecast) -> Optional[str]:
    model_params = forecast.model_params if isinstance(forecast.model_params, dict) else {}
    value = model_params.get("account_id")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _serialize_forecast(forecast: ModelForecast) -> Dict[str, Any]:
    metrics = forecast.metrics if isinstance(forecast.metrics, dict) else {}
    return {
        "id": forecast.id,
        "figi": forecast.figi,
        "ticker": forecast.ticker,
        "account_id": _forecast_account_id(forecast),
        "horizon": forecast.horizon,
        "model_type": forecast.model_type,
        "model_type_effective": forecast.model_type_effective,
        "hyperparam_mode": forecast.hyperparam_mode,
        "mae": _metric(metrics, "MAE"),
        "rmse": _metric(metrics, "RMSE"),
        "r2": _metric(metrics, "R2"),
        "train_samples": _metric(metrics, "train_samples"),
        "validation_samples": _metric(metrics, "validation_samples"),
        "current_price": _round(forecast.current_price, 6),
        "predicted_price": _round(forecast.predicted_price, 6),
        "price_delta_percent": _round(forecast.price_delta_percent),
        "recommendation": forecast.recommendation,
        "created_at": _iso(forecast.created_at),
    }


def _model_quality(
    db: Session,
    user_id: int,
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    figi: Optional[str] = None,
    model_type: Optional[str] = None,
    horizon: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    account_id = (account_id or "").strip() or None
    query = db.query(ModelForecast).filter(ModelForecast.user_id == user_id)
    query = _apply_common_filters(
        query,
        ModelForecast,
        date_from=date_from,
        date_to=date_to,
        figi=figi,
        model_type=model_type,
        horizon=horizon,
    )
    forecasts = _all(_safe_ordered_query(query, ModelForecast.created_at.desc()))
    if account_id:
        forecasts = [forecast for forecast in forecasts if _forecast_account_id(forecast) == account_id]

    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    effective_distribution: Dict[str, int] = defaultdict(int)
    recommendation_distribution: Dict[str, int] = defaultdict(int)
    horizon_distribution: Dict[str, int] = defaultdict(int)

    for forecast in forecasts:
        requested = _lower(forecast.model_type) or "unknown"
        effective = _lower(forecast.model_type_effective) or requested
        horizon_key = forecast.horizon or "unknown"
        key = (effective, horizon_key)
        bucket = grouped.setdefault(key, {
            "model": effective,
            "horizon": horizon_key,
            "forecast_count": 0,
            "mae_values": [],
            "rmse_values": [],
            "r2_values": [],
            "train_samples": [],
            "avg_delta_values": [],
            "requested_models": defaultdict(int),
        })
        metrics = forecast.metrics if isinstance(forecast.metrics, dict) else {}
        bucket["forecast_count"] += 1
        bucket["mae_values"].append(_metric(metrics, "MAE"))
        bucket["rmse_values"].append(_metric(metrics, "RMSE"))
        bucket["r2_values"].append(_metric(metrics, "R2"))
        bucket["train_samples"].append(_metric(metrics, "train_samples"))
        bucket["avg_delta_values"].append(_to_float(forecast.price_delta_percent))
        bucket["requested_models"][requested] += 1
        effective_distribution[effective] += 1
        recommendation_distribution[forecast.recommendation or "unknown"] += 1
        horizon_distribution[horizon_key] += 1

    rows = []
    for bucket in grouped.values():
        rows.append({
            "model": bucket["model"],
            "horizon": bucket["horizon"],
            "forecast_count": bucket["forecast_count"],
            "avg_mae": _round(_avg(bucket["mae_values"])),
            "avg_rmse": _round(_avg(bucket["rmse_values"])),
            "avg_r2": _round(_avg(bucket["r2_values"]), 4),
            "avg_train_samples": _round(_avg(bucket["train_samples"]), 0),
            "avg_predicted_delta_percent": _round(_avg(bucket["avg_delta_values"])),
            "requested_models": dict(bucket["requested_models"]),
        })
    rows.sort(key=lambda row: (row["model"], row["horizon"]))

    return {
        "total_forecasts": len(forecasts),
        "rows": rows,
        "effective_distribution": dict(effective_distribution),
        "recommendation_distribution": dict(recommendation_distribution),
        "horizon_distribution": dict(horizon_distribution),
        "recent_forecasts": [_serialize_forecast(forecast) for forecast in forecasts[:40]],
    }


def _backtest_summary(
    db: Session,
    user_id: int,
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Dict[str, Any]:
    query = db.query(BacktestResult).filter(BacktestResult.user_id == user_id)
    query = _apply_common_filters(query, BacktestResult, date_from=date_from, date_to=date_to)
    results = _all(_safe_ordered_query(query, BacktestResult.created_at.desc()))
    recent = results[:20]
    returns = [_to_float(item.total_return) for item in results]
    sharpes = [_to_float(item.sharpe_ratio) for item in results if item.sharpe_ratio is not None]
    drawdowns = [_to_float(item.max_drawdown) for item in results if item.max_drawdown is not None]

    return {
        "total_backtests": len(results),
        "best_return": round(max(returns), 4) if returns else 0.0,
        "avg_return": round(sum(returns) / len(returns), 4) if returns else 0.0,
        "avg_sharpe": round(sum(sharpes) / len(sharpes), 4) if sharpes else 0.0,
        "worst_drawdown": round(min(drawdowns), 4) if drawdowns else 0.0,
        "recent": [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "stock_symbols": item.stock_symbols or [],
                "start_date": _iso(item.start_date),
                "end_date": _iso(item.end_date),
                "initial_balance": _round(item.initial_balance),
                "final_balance": _round(item.final_balance),
                "total_return": _nullable_round(_to_float(item.total_return) * 100 if abs(_to_float(item.total_return)) <= 1 else item.total_return),
                "total_trades": item.total_trades,
                "win_rate": _nullable_round(item.win_rate),
                "sharpe_ratio": _nullable_round(item.sharpe_ratio, 4),
                "max_drawdown": _nullable_round(_to_float(item.max_drawdown) * 100 if item.max_drawdown is not None and abs(_to_float(item.max_drawdown)) <= 1 else item.max_drawdown),
                "created_at": _iso(item.created_at),
            }
            for item in recent
        ],
    }


def _chart_payload(bot_analytics: Dict[str, Any], bot_history: list, model_quality: Dict[str, Any]) -> Dict[str, Any]:
    model_pnl = []
    for model, values in (bot_analytics.get("by_model") or {}).items():
        model_pnl.append({
            "model": model,
            "trades": int(values.get("total_trades") or 0),
            "closed_trades": int(values.get("closed_trades") or 0),
            "pnl": _round(values.get("realized_pnl")),
            "avg_return": _round(values.get("avg_trade_return_percent")),
        })

    status_distribution: Dict[str, int] = defaultdict(int)
    for trade in bot_history:
        status_distribution[trade.get("status") or "unknown"] += 1

    forecast_timeline = []
    for forecast in reversed(model_quality.get("recent_forecasts", [])[:30]):
        forecast_timeline.append({
            "date": (forecast.get("created_at") or "")[:10],
            "ticker": forecast.get("ticker") or forecast.get("figi"),
            "model": forecast.get("model_type_effective") or forecast.get("model_type"),
            "delta": _round(forecast.get("price_delta_percent")),
        })

    return {
        "bot_pnl_timeline": _bot_timeline(bot_history),
        "model_pnl": model_pnl,
        "trade_status_distribution": [{"name": key, "value": value} for key, value in status_distribution.items()],
        "forecast_timeline": forecast_timeline,
        "model_forecast_counts": [
            {"model": key, "count": value}
            for key, value in (model_quality.get("effective_distribution") or {}).items()
        ],
        "recommendation_distribution": [
            {"name": key, "value": value}
            for key, value in (model_quality.get("recommendation_distribution") or {}).items()
        ],
    }


def _risk_warnings(
    portfolio: Dict[str, Any],
    bot_analytics: Dict[str, Any],
    model_quality: Dict[str, Any],
    backtests: Dict[str, Any],
) -> list:
    warnings = []

    total_stocks = _to_float(portfolio.get("total_stocks_value"))
    for position in portfolio.get("positions") or []:
        value = _to_float(position.get("value"))
        share = (value / total_stocks * 100) if total_stocks else 0.0
        if share >= 60:
            warnings.append({
                "severity": "warning",
                "title": "Высокая концентрация портфеля",
                "message": f"{position.get('ticker') or position.get('figi')} занимает {share:.1f}% стоимости акций. Риск зависит от одного инструмента.",
                "metric": f"{share:.1f}%",
            })

    total_value = _to_float(portfolio.get("total_value"))
    cash = _to_float(portfolio.get("cash_balance"))
    if total_value > 0 and cash / total_value < 0.05:
        warnings.append({
            "severity": "info",
            "title": "Мало свободных денег",
            "message": "Свободные средства меньше 5% портфеля. Новые BUY-рекомендации могут быть неисполнимы.",
            "metric": f"{cash / total_value * 100:.1f}%",
        })

    if _to_float(bot_analytics.get("failed_trades")) > 0:
        warnings.append({
            "severity": "warning",
            "title": "Есть ошибки ML-сделок",
            "message": "В истории ML-бота есть failed-сделки. Проверь токен, sandbox-счет, доступность брокера и параметры заявки.",
            "metric": str(int(_to_float(bot_analytics.get("failed_trades")))),
        })

    closed = int(_to_float(bot_analytics.get("closed_trades")))
    win_rate = _to_float(bot_analytics.get("win_rate"))
    if closed >= 5 and win_rate < 50:
        warnings.append({
            "severity": "warning",
            "title": "Низкий win rate ML-бота",
            "message": "Доля прибыльных закрытых сделок ниже 50%. Рекомендации модели стоит перепроверять вручную.",
            "metric": f"{win_rate:.1f}%",
        })

    scheduled = int(_to_float(bot_analytics.get("scheduled_auto_sells")))
    if scheduled > 0:
        warnings.append({
            "severity": "info",
            "title": "Есть отложенные auto-sell сценарии",
            "message": "Часть позиций ожидает условия автоматической продажи. Исполнение все равно должно контролироваться пользователем.",
            "metric": str(scheduled),
        })

    for row in model_quality.get("rows") or []:
        if _to_float(row.get("avg_train_samples")) and _to_float(row.get("avg_train_samples")) < 50:
            warnings.append({
                "severity": "info",
                "title": "Маленькая выборка обучения",
                "message": f"{row.get('model', '').upper()} / {row.get('horizon')} обучался на малом числе наблюдений. Прогноз менее надежен.",
                "metric": str(int(_to_float(row.get("avg_train_samples")))),
            })
            break

    if not warnings:
        warnings.append({
            "severity": "success",
            "title": "Критичных предупреждений нет",
            "message": "По текущим сохраненным данным не найдено явных проблем. Это не является гарантией доходности.",
            "metric": "OK",
        })

    return warnings[:8]


@router.get("/overview")
def overview(
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    figi: Optional[str] = Query(default=None),
    model_type: Optional[str] = Query(default=None),
    horizon: Optional[str] = Query(default=None),
    account_id: Optional[str] = Query(default=None, max_length=128),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    date_from = _clean_datetime(date_from)
    date_to = _clean_datetime(date_to)
    figi = _clean_text(figi)
    model_type = _clean_text(model_type)
    horizon = _clean_text(horizon)
    account_id = _clean_text(account_id)

    portfolio_error = None
    try:
        raw_portfolio = get_portfolio(user_id=current_user.id, account_id=account_id)
        if raw_portfolio.get("status") == "error":
            portfolio_error = raw_portfolio.get("message", "Portfolio unavailable")
            portfolio = _empty_portfolio()
        else:
            portfolio = format_portfolio(raw_portfolio, user_id=current_user.id)
    except Exception as exc:
        logger.warning("Portfolio analytics unavailable user_id=%s: %s", current_user.id, exc)
        portfolio_error = str(exc)
        portfolio = _empty_portfolio()

    analytics_errors = []

    try:
        bot_analytics = calculate_bot_trade_analytics(
            db,
            current_user.id,
            date_from=date_from,
            date_to=date_to,
            figi=figi,
            model_type=model_type,
            horizon=horizon,
            account_id=account_id,
        )
    except Exception as exc:  # noqa: BLE001 - analytics page must stay available with partial data
        logger.exception("Bot analytics unavailable user_id=%s: %s", current_user.id, exc)
        analytics_errors.append("Не удалось загрузить показатели ML-бота")
        bot_analytics = _empty_bot_analytics()

    try:
        bot_history = _recent_bot_trades(
            db,
            current_user.id,
            date_from=date_from,
            date_to=date_to,
            figi=figi,
            model_type=model_type,
            horizon=horizon,
            account_id=account_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bot trade history unavailable user_id=%s: %s", current_user.id, exc)
        analytics_errors.append("Не удалось загрузить историю ML-сделок")
        bot_history = []

    try:
        manual_trades = _manual_trade_summary(
            db,
            current_user.id,
            date_from=date_from,
            date_to=date_to,
            figi=figi,
            account_id=account_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Manual trade analytics unavailable user_id=%s: %s", current_user.id, exc)
        analytics_errors.append("Не удалось загрузить ручные сделки")
        manual_trades = {
            "total_trades": 0,
            "buy_trades": 0,
            "sell_trades": 0,
            "buy_amount": 0.0,
            "sell_amount": 0.0,
            "net_cash_flow": 0.0,
            "realized_pnl": 0.0,
            "avg_realized_pnl_percent": 0.0,
            "recent": [],
        }

    try:
        model_quality = _model_quality(
            db,
            current_user.id,
            date_from=date_from,
            date_to=date_to,
            figi=figi,
            model_type=model_type,
            horizon=horizon,
            account_id=account_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Model quality analytics unavailable user_id=%s: %s", current_user.id, exc)
        analytics_errors.append("Не удалось загрузить качество моделей")
        model_quality = {
            "total_forecasts": 0,
            "rows": [],
            "effective_distribution": {},
            "recommendation_distribution": {},
            "horizon_distribution": {},
            "recent_forecasts": [],
        }

    try:
        backtests = _backtest_summary(db, current_user.id, date_from=date_from, date_to=date_to)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Backtest analytics unavailable user_id=%s: %s", current_user.id, exc)
        analytics_errors.append("Не удалось загрузить backtest")
        backtests = {
            "total_backtests": 0,
            "best_return": 0.0,
            "avg_return": 0.0,
            "avg_sharpe": 0.0,
            "worst_drawdown": 0.0,
            "recent": [],
        }

    charts = _chart_payload(bot_analytics, bot_history, model_quality)

    return {
        "status": "ok",
        "filters": {
            "date_from": _iso(date_from),
            "date_to": _iso(date_to),
            "figi": figi,
            "model_type": model_type,
            "horizon": horizon,
            "account_id": account_id,
        },
        "data_scope": {
            "account_id": account_id,
            "portfolio": "selected_account" if account_id else "all_user_accounts",
            "manual_trades": "selected_account" if account_id else "all_user_accounts",
            "bot_trades": "selected_account" if account_id else "all_user_history",
            "model_forecasts": "selected_account" if account_id else "user_history",
        },
        "portfolio": portfolio,
        "portfolio_error": portfolio_error,
        "manual_trades": manual_trades,
        "bot_analytics": bot_analytics,
        "bot_history": bot_history,
        "model_quality": model_quality,
        "backtests": backtests,
        "charts": charts,
        "risk_warnings": _risk_warnings(portfolio, bot_analytics, model_quality, backtests),
        "analytics_errors": analytics_errors,
    }
