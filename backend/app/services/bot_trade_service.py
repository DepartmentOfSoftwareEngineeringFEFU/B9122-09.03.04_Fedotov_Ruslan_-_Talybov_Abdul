from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bot_trade import BotTrade
from app.models.model_forecast import ModelForecast
from app.schemas.model import BotTradeConfirmRequest
from app.services.bot_analytics_service import calculate_bot_trade_analytics
from app.services.instrument_service import get_current_price, get_instrument_by_figi, get_portfolio_snapshot
from app.services.trade_service import execute_order


EXECUTED_STATUSES = {"executed", "closed", "scheduled_sell"}
OPEN_STATUSES = {"confirmed", "executed", "scheduled_sell"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _money(value: float) -> Decimal:
    return Decimal(str(round(float(value or 0.0), 6)))


def _percent(value: float) -> Decimal:
    return Decimal(str(round(float(value or 0.0), 4)))



def _assert_bot_trading_allowed() -> None:
    """Block accidental real-money AI-bot orders unless explicitly enabled."""
    if not settings.USE_SANDBOX and not settings.AI_BOT_REAL_TRADING_ENABLED:
        raise HTTPException(
            status_code=403,
            detail=(
                "AI-bot trading is disabled in real broker mode. "
                "Use sandbox or set AI_BOT_REAL_TRADING_ENABLED=true only after manual risk review."
            ),
        )


def _normalize_side(request: BotTradeConfirmRequest, forecast: ModelForecast) -> str:
    side = (request.side or "").strip().lower()
    if side:
        if side not in {"buy", "sell", "schedule_sell"}:
            raise HTTPException(status_code=400, detail="side must be one of: buy, sell, schedule_sell")
        return side

    action = (request.action or forecast.recommendation or "").strip().upper()
    if action in {"BUY_OPTIONAL", "HOLD_AND_OPTIONAL_BUY"}:
        return "buy"
    if action == "SELL":
        return "sell"
    raise HTTPException(status_code=400, detail="This recommendation does not require a trade confirmation")


def _default_scheduled_sell_at(horizon: Optional[str]) -> datetime:
    now = datetime.now(timezone.utc)
    if horizon == "1d":
        return now + timedelta(days=1)
    return now + timedelta(hours=1)


def _realized_for_sell(executed_price: float, average_buy_price: float, quantity: int) -> Tuple[Optional[float], Optional[float]]:
    if average_buy_price <= 0 or quantity <= 0:
        return None, None
    pnl = (executed_price - average_buy_price) * quantity
    base = average_buy_price * quantity
    pnl_percent = (pnl / base * 100) if base > 0 else 0.0
    return pnl, pnl_percent


def _default_requested_shares(side: str, snapshot: Dict[str, float], lot: int) -> int:
    if side in {"sell", "schedule_sell"}:
        return int(snapshot["quantity"])
    if side == "buy":
        return max(int(lot or 1), 1)
    return 0


def _order_lots_from_shares(requested_shares: int, lot: int) -> int:
    lot_size = max(int(lot or 1), 1)
    if requested_shares <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    if requested_shares % lot_size != 0:
        raise HTTPException(
            status_code=400,
            detail=f"Количество должно быть кратно размеру лота: {lot_size} шт.",
        )
    return requested_shares // lot_size


def _base_trade_from_forecast(
    *,
    forecast: ModelForecast,
    user_id: int,
    side: str,
    requested_quantity: int,
    current_price: float,
    amount: float,
    snapshot: Dict[str, float],
    request: BotTradeConfirmRequest,
    scheduled_sell_at: Optional[datetime],
) -> BotTrade:
    auto_sell_enabled = bool(request.auto_sell_enabled)
    auto_sell_target_enabled = bool(request.auto_sell_target_enabled)
    account_id = (request.account_id or "").strip() or None
    return BotTrade(
        user_id=user_id,
        forecast_id=forecast.id,
        figi=forecast.figi,
        ticker=forecast.ticker,
        source=(forecast.model_params or {}).get("source", "ai_model_bot") if isinstance(forecast.model_params, dict) else "ai_model_bot",
        idempotency_key=(request.idempotency_key or None),
        account_id=account_id,
        horizon=forecast.horizon,
        model_type_requested=forecast.model_type,
        model_type_used=forecast.model_type_effective,
        hyperparam_mode=forecast.hyperparam_mode,
        model_params=forecast.model_params,
        metrics=forecast.metrics,
        recommendation_action=forecast.recommendation,
        side="sell" if side == "schedule_sell" else side,
        quantity=requested_quantity,
        price=_money(current_price),
        amount=_money(amount),
        current_price=_money(current_price),
        predicted_price=_money(_to_float(forecast.predicted_price, current_price)),
        price_delta_percent=_percent(_to_float(forecast.price_delta_percent, 0.0)),
        average_buy_price=_money(snapshot["average_buy_price"]),
        cash_balance_at_signal=_money(snapshot["cash_balance"]),
        status="scheduled_sell" if side == "schedule_sell" else "confirmed",
        auto_sell_enabled=auto_sell_enabled,
        auto_sell_target_enabled=auto_sell_target_enabled,
        scheduled_sell_at=scheduled_sell_at,
        sell_target_price=(
            _money(request.sell_target_price)
            if request.sell_target_price and auto_sell_target_enabled
            else (_money(_to_float(forecast.predicted_price, current_price)) if auto_sell_target_enabled and (auto_sell_enabled or side == "schedule_sell") else None)
        ),
        confirmed_at=datetime.now(timezone.utc),
    )


def confirm_bot_trade(db: Session, user_id: int, request: BotTradeConfirmRequest) -> BotTrade:
    idem_key = (request.idempotency_key or "").strip() or None
    account_id = (request.account_id or "").strip() or None
    if idem_key:
        existing = db.query(BotTrade).filter(
            BotTrade.user_id == user_id,
            BotTrade.idempotency_key == idem_key,
        ).first()
        if existing:
            return existing

    forecast = (
        db.query(ModelForecast)
        .filter(ModelForecast.id == request.forecast_id, ModelForecast.user_id == user_id)
        .first()
    )
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")

    side = _normalize_side(request, forecast)
    _assert_bot_trading_allowed()

    instrument = get_instrument_by_figi(user_id=user_id, figi=forecast.figi)
    if (instrument.get("currency") or "RUB").upper() != "RUB":
        raise HTTPException(status_code=400, detail="AI-bot trading is allowed only for RUB instruments")
    if (instrument.get("instrument_type") or "share") != "share":
        raise HTTPException(status_code=400, detail="AI-bot trading is allowed only for shares")

    current_price = _to_float(get_current_price(user_id=user_id, figi=forecast.figi, fallback_price=forecast.current_price), 0.0)
    if current_price <= 0:
        raise HTTPException(status_code=400, detail="Forecast does not contain a valid current price")
    lot = max(int(instrument.get("lot") or 1), 1)

    snapshot = get_portfolio_snapshot(user_id=user_id, figi=forecast.figi, account_id=account_id)
    requested_shares = _to_int(request.quantity, 0)

    if requested_shares <= 0:
        requested_shares = _default_requested_shares(side, snapshot, lot)

    if requested_shares <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    if side in {"sell", "schedule_sell"} and requested_shares > int(snapshot["quantity"]):
        raise HTTPException(status_code=400, detail="Not enough shares in portfolio for this sell action")

    order_lots = _order_lots_from_shares(requested_shares, lot)

    amount = current_price * requested_shares
    if side == "buy" and amount > snapshot["cash_balance"]:
        raise HTTPException(status_code=400, detail="Not enough cash balance for this buy action")

    scheduled_sell_at = request.scheduled_sell_at
    if request.auto_sell_enabled and scheduled_sell_at is None:
        scheduled_sell_at = _default_scheduled_sell_at(forecast.horizon)

    trade = _base_trade_from_forecast(
        forecast=forecast,
        user_id=user_id,
        side=side,
        requested_quantity=requested_shares,
        current_price=current_price,
        amount=amount,
        snapshot=snapshot,
        request=request,
        scheduled_sell_at=scheduled_sell_at,
    )

    if side == "schedule_sell":
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return trade

    # Реальная сделка выполняется только после явного POST /bot-trades/confirm.
    result = execute_order(
        forecast.figi,
        side,
        order_lots,
        user_id=user_id,
        account_id=account_id,
        source="ai_bot",
        idempotency_key=f"bot:{idem_key}:order" if idem_key else None,
    )
    trade.raw_response = {
        **result,
        "requested_shares": requested_shares,
        "requested_lots": order_lots,
        "lot": lot,
    }

    if result.get("status") == "error":
        trade.status = "failed"
        trade.error_message = result.get("message", "Trading error")
        db.add(trade)
        db.commit()
        db.refresh(trade)
        raise HTTPException(status_code=400, detail=trade.error_message)

    executed_price = _to_float(result.get("price"), current_price) or current_price
    executed_quantity = int(result.get("qty") or requested_shares)
    trade.quantity = executed_quantity
    trade.price = _money(executed_price)
    trade.amount = _money(_to_float(result.get("amount"), executed_price * executed_quantity))
    trade.order_id = str(result.get("order_id")) if result.get("order_id") is not None else None
    trade.broker_order_id = str(result.get("broker_order_id") or result.get("order_id")) if (result.get("broker_order_id") or result.get("order_id")) is not None else None
    trade.executed_at = datetime.now(timezone.utc)

    if side == "sell":
        realized_pnl, realized_pnl_percent = _realized_for_sell(
            executed_price,
            snapshot["average_buy_price"],
            executed_quantity,
        )
        trade.realized_pnl = _money(realized_pnl) if realized_pnl is not None else None
        trade.realized_pnl_percent = _percent(realized_pnl_percent) if realized_pnl_percent is not None else None
        trade.status = "closed"
        trade.closed_at = datetime.now(timezone.utc)
    elif request.auto_sell_enabled:
        trade.status = "scheduled_sell"
    else:
        trade.status = "executed"

    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def list_bot_trades(
    db: Session,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    account_id: Optional[str] = None,
) -> List[BotTrade]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    account_id = (account_id or "").strip() or None
    query = db.query(BotTrade).filter(BotTrade.user_id == user_id)
    if account_id:
        query = query.filter(BotTrade.account_id == account_id)
    return query.order_by(BotTrade.created_at.desc(), BotTrade.id.desc()).offset(offset).limit(limit).all()



def get_bot_trade_analytics(db: Session, user_id: int, account_id: Optional[str] = None) -> Dict[str, Any]:
    return calculate_bot_trade_analytics(db=db, user_id=user_id, account_id=account_id)
