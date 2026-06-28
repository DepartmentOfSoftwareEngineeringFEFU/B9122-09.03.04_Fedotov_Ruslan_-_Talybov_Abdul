from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.bot_trade import BotTrade


EXECUTED_STATUSES = {"executed", "closed", "scheduled_sell"}
OPEN_STATUSES = {"confirmed", "executed", "scheduled_sell"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _empty_model_bucket() -> Dict[str, float]:
    return {
        "total_trades": 0,
        "closed_trades": 0,
        "open_trades": 0,
        "failed_trades": 0,
        "realized_pnl": 0.0,
        "avg_trade_return_percent": 0.0,
        "win_rate": 0.0,
    }


def _apply_filters(
    query: Any,
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    figi: Optional[str] = None,
    model_type: Optional[str] = None,
    horizon: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Any:
    if date_from is not None:
        query = query.filter(BotTrade.created_at >= date_from)
    if date_to is not None:
        query = query.filter(BotTrade.created_at <= date_to)
    if figi:
        query = query.filter(BotTrade.figi == figi.strip().upper())
    if horizon:
        query = query.filter(BotTrade.horizon == horizon)
    if model_type:
        normalized = model_type.strip().lower()
        query = query.filter(
            (BotTrade.model_type_used == normalized) | (BotTrade.model_type_requested == normalized)
        )
    if account_id:
        query = query.filter(BotTrade.account_id == account_id)
    return query


def calculate_bot_trade_analytics(
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
    query = db.query(BotTrade).filter(BotTrade.user_id == user_id)
    query = _apply_filters(
        query,
        date_from=date_from,
        date_to=date_to,
        figi=figi,
        model_type=model_type,
        horizon=horizon,
        account_id=account_id,
    )
    trades: List[BotTrade] = query.all()
    if account_id:
        trades = [trade for trade in trades if getattr(trade, "account_id", None) == account_id]

    total_trades = len(trades)
    closed_trades = [
        trade for trade in trades
        if trade.status == "closed" or (trade.side == "sell" and trade.status in EXECUTED_STATUSES)
    ]
    open_trades = [trade for trade in trades if trade not in closed_trades and trade.status in OPEN_STATUSES]
    scheduled_auto_sells = [trade for trade in trades if trade.status == "scheduled_sell" and bool(trade.auto_sell_enabled)]
    failed_trades = [trade for trade in trades if trade.status == "failed"]

    realized_values = [_to_float(trade.realized_pnl, 0.0) for trade in closed_trades]
    realized_percent_values = [
        _to_float(trade.realized_pnl_percent, 0.0)
        for trade in closed_trades
        if trade.realized_pnl_percent is not None
    ]

    realized_pnl = sum(realized_values)
    winning_trades = sum(1 for value in realized_values if value > 0)
    win_rate = (winning_trades / len(closed_trades) * 100) if closed_trades else 0.0
    avg_return = (sum(realized_percent_values) / len(realized_percent_values)) if realized_percent_values else 0.0
    best_trade = max(realized_percent_values) if realized_percent_values else 0.0
    worst_trade = min(realized_percent_values) if realized_percent_values else 0.0

    by_model: Dict[str, Dict[str, float]] = {}
    for trade in trades:
        key = trade.model_type_used or trade.model_type_requested or "unknown"
        bucket = by_model.setdefault(key, _empty_model_bucket())
        bucket["total_trades"] += 1
        if trade in open_trades:
            bucket["open_trades"] += 1
        if trade in failed_trades:
            bucket["failed_trades"] += 1
        if trade in closed_trades:
            bucket["closed_trades"] += 1
            bucket["realized_pnl"] += _to_float(trade.realized_pnl, 0.0)

    for key, bucket in by_model.items():
        model_closed = [
            trade for trade in closed_trades
            if (trade.model_type_used or trade.model_type_requested or "unknown") == key
        ]
        returns = [
            _to_float(trade.realized_pnl_percent, 0.0)
            for trade in model_closed
            if trade.realized_pnl_percent is not None
        ]
        wins = sum(1 for trade in model_closed if _to_float(trade.realized_pnl, 0.0) > 0)
        bucket["avg_trade_return_percent"] = round((sum(returns) / len(returns)) if returns else 0.0, 2)
        bucket["win_rate"] = round((wins / len(model_closed) * 100) if model_closed else 0.0, 2)
        bucket["realized_pnl"] = round(bucket["realized_pnl"], 2)

    return {
        "total_trades": total_trades,
        "closed_trades": len(closed_trades),
        "open_trades": len(open_trades),
        "scheduled_auto_sells": len(scheduled_auto_sells),
        "failed_trades": len(failed_trades),
        "realized_pnl": round(realized_pnl, 2),
        "realized_pnl_percent": round(avg_return, 2),
        "win_rate": round(win_rate, 2),
        "avg_trade_return_percent": round(avg_return, 2),
        "best_trade_percent": round(best_trade, 2),
        "worst_trade_percent": round(worst_trade, 2),
        "by_model": by_model,
    }
