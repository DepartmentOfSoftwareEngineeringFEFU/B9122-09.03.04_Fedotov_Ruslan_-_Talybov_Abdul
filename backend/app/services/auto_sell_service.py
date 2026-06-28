import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.bot_trade import BotTrade
from app.services.instrument_service import get_current_price, get_lot_size
from app.services.trade_service import execute_order

logger = logging.getLogger(__name__)

AUTO_SELL_STATUSES = {"scheduled_sell"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _money(value: float) -> Decimal:
    return Decimal(str(round(float(value or 0.0), 6)))


def _percent(value: float) -> Decimal:
    return Decimal(str(round(float(value or 0.0), 4)))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)




def _acquire_worker_lock(db: Session) -> bool:
    try:
        value = db.execute(
            text("SELECT GET_LOCK(:name, 0)"),
            {"name": settings.AUTO_SELL_LOCK_NAME},
        ).scalar()
        return value == 1
    except Exception as exc:  # noqa: BLE001 - non-MySQL tests may not support named locks
        logger.debug("Auto-sell DB lock is unavailable, continuing without distributed lock: %s", exc)
        return True


def _release_worker_lock(db: Session) -> None:
    try:
        db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": settings.AUTO_SELL_LOCK_NAME})
    except Exception as exc:  # noqa: BLE001
        logger.debug("Auto-sell DB lock release skipped: %s", exc)


def _result_failed(result: Dict[str, Any]) -> bool:
    status = str(result.get("status") or "").lower()
    return status == "error"


def _get_current_price(user_id: int, figi: str) -> Optional[float]:
    price = get_current_price(user_id=user_id, figi=figi, fallback_price=None)
    if price is None:
        logger.warning("Auto-sell price lookup returned no price for figi=%s user_id=%s", figi, user_id)
        return None
    price_value = _to_float(price, 0.0)
    return price_value if price_value > 0 else None


def _should_sell(trade: BotTrade, current_price: Optional[float], now: datetime) -> bool:
    scheduled_at = _as_aware_utc(trade.scheduled_sell_at)
    if scheduled_at and scheduled_at <= now:
        return True

    target_price = _to_float(trade.sell_target_price, 0.0)
    target_enabled = bool(getattr(trade, "auto_sell_target_enabled", True))
    if target_enabled and target_price > 0 and current_price is not None and current_price >= target_price:
        return True

    return False


def _realized_base_price(trade: BotTrade) -> float:
    if trade.side == "buy" and trade.price is not None:
        return _to_float(trade.price, 0.0)
    return _to_float(trade.average_buy_price, 0.0)


def _append_auto_sell_response(trade: BotTrade, result: Dict[str, Any]) -> Dict[str, Any]:
    raw = trade.raw_response if isinstance(trade.raw_response, dict) else {}
    history = raw.get("auto_sell_attempts") if isinstance(raw.get("auto_sell_attempts"), list) else []
    history.append({
        "at": _utc_now().isoformat(),
        "result": result,
    })
    return {**raw, "auto_sell_attempts": history, "last_auto_sell_result": result}


def _order_lots_for_trade(trade: BotTrade) -> int:
    quantity = int(trade.quantity or 0)
    lot = max(int(get_lot_size(user_id=trade.user_id, figi=trade.figi) or 1), 1)
    if quantity <= 0:
        return 0
    if quantity % lot != 0:
        raise ValueError(f"Количество должно быть кратно размеру лота: {lot} шт.")
    return quantity // lot


def process_due_auto_sells(
    db: Session,
    limit: int = 50,
    user_id: Optional[int] = None,
    batch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Backend-side auto-sell processor.

    It sells only BotTrade rows that were explicitly confirmed earlier with
    auto_sell_enabled=true and status=scheduled_sell. This function is safe to
    call from a scheduler/worker; it does not create signals by itself.
    """
    if not _acquire_worker_lock(db):
        return {"processed": 0, "closed": 0, "failed": 0, "skipped": 0, "candidates": 0, "detail": "auto-sell worker is already running elsewhere"}

    now = _utc_now()
    query = db.query(BotTrade).filter(
        BotTrade.auto_sell_enabled.is_(True),
        BotTrade.status.in_(AUTO_SELL_STATUSES),
        BotTrade.quantity > 0,
    )
    if user_id is not None:
        query = query.filter(BotTrade.user_id == user_id)
    if batch_id is not None:
        query = query.filter(BotTrade.batch_id == batch_id)

    candidates = (
        query
        .order_by(BotTrade.scheduled_sell_at.asc(), BotTrade.id.asc())
        .limit(max(1, min(int(limit or 50), 200)))
        .all()
    )

    processed = 0
    skipped = 0
    failed = 0
    closed = 0

    try:
        if not settings.USE_SANDBOX and not settings.AI_BOT_REAL_TRADING_ENABLED:
            return {
                "processed": 0,
                "closed": 0,
                "failed": 0,
                "skipped": len(candidates),
                "candidates": len(candidates),
                "detail": "real trading is disabled",
            }

        for trade in candidates:
            current_price = _get_current_price(trade.user_id, trade.figi)
            if not _should_sell(trade, current_price, now):
                skipped += 1
                continue

            if settings.AUTO_SELL_DRY_RUN:
                skipped += 1
                logger.info("Auto-sell dry-run user_id=%s trade_id=%s figi=%s", trade.user_id, trade.id, trade.figi)
                continue

            processed += 1
            try:
                order_lots = _order_lots_for_trade(trade)
                result = execute_order(
                    trade.figi,
                    "sell",
                    order_lots,
                    user_id=trade.user_id,
                    account_id=trade.account_id,
                    source="auto_sell",
                    idempotency_key=f"auto-sell:{trade.id}",
                )
            except Exception as exc:  # noqa: BLE001 - keep processing other scheduled trades
                result = {"status": "error", "message": str(exc)}
            trade.raw_response = _append_auto_sell_response(trade, result)

            if _result_failed(result):
                failed += 1
                trade.status = "failed"
                trade.error_message = result.get("message", "Auto-sell execution failed")
                db.add(trade)
                continue

            sell_price = _to_float(result.get("price"), current_price or _to_float(trade.current_price, 0.0))
            executed_quantity = int(result.get("qty") or int(trade.quantity or 0))
            executed_amount = _to_float(result.get("amount"), 0.0)
            base_price = _realized_base_price(trade)
            quantity = executed_quantity

            trade.status = "closed"
            trade.closed_at = now
            trade.executed_at = trade.executed_at or now
            trade.price = trade.price or _money(base_price or sell_price)
            trade.amount = trade.amount or _money(executed_amount or (base_price or sell_price) * quantity)
            trade.order_id = trade.order_id or (str(result.get("order_id")) if result.get("order_id") is not None else None)
            trade.broker_order_id = trade.broker_order_id or (
                str(result.get("broker_order_id") or result.get("order_id"))
                if (result.get("broker_order_id") or result.get("order_id")) is not None
                else None
            )

            if base_price > 0 and quantity > 0:
                realized_pnl = (sell_price - base_price) * quantity
                realized_base = base_price * quantity
                trade.realized_pnl = _money(realized_pnl)
                trade.realized_pnl_percent = _percent((realized_pnl / realized_base) * 100 if realized_base > 0 else 0.0)

            closed += 1
            db.add(trade)

        db.commit()
    finally:
        _release_worker_lock(db)

    return {
        "processed": processed,
        "closed": closed,
        "failed": failed,
        "skipped": skipped,
        "candidates": len(candidates),
    }


def count_auto_sell_candidates(db: Session, user_id: Optional[int] = None, batch_id: Optional[int] = None) -> Dict[str, int]:
    """Return lightweight counts for UI/status endpoints without executing orders."""
    now = _utc_now()
    base_query = db.query(BotTrade).filter(
        BotTrade.auto_sell_enabled.is_(True),
        BotTrade.status.in_(AUTO_SELL_STATUSES),
        BotTrade.quantity > 0,
    )
    if user_id is not None:
        base_query = base_query.filter(BotTrade.user_id == user_id)
    if batch_id is not None:
        base_query = base_query.filter(BotTrade.batch_id == batch_id)

    scheduled_count = base_query.count()
    due_count = base_query.filter(
        BotTrade.scheduled_sell_at.isnot(None),
        BotTrade.scheduled_sell_at <= now,
    ).count()
    return {"scheduled_count": scheduled_count, "due_count": due_count}


async def run_auto_sell_worker(poll_seconds: int = 60) -> None:
    """Small optional backend worker. Disabled by default through config."""
    poll_seconds = max(15, int(poll_seconds or 60))
    logger.info("Auto-sell backend worker started; poll_seconds=%s", poll_seconds)

    while True:
        db = SessionLocal()
        try:
            summary = process_due_auto_sells(db)
            if summary.get("processed"):
                logger.info("Auto-sell cycle summary: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - worker must keep running
            logger.exception("Auto-sell worker cycle failed: %s", exc)
        finally:
            db.close()

        await asyncio.sleep(poll_seconds)
