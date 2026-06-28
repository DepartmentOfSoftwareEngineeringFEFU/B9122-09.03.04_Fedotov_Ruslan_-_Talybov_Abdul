from __future__ import annotations

import asyncio
import csv
import logging
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.bot_trade import BotTrade
from app.models.bulk_trade import BulkTradeBatch, BulkTradeItem
from app.schemas.model import BotTradeConfirmRequest, ForecastRequest
from app.services.auto_sell_service import count_auto_sell_candidates, process_due_auto_sells
from app.services.bot_trade_service import confirm_bot_trade
from app.services.instrument_service import get_current_price, list_moex_shares, list_popular_moex_shares
from app.services.prediction_service import compare_forecast_models

logger = logging.getLogger(__name__)

TERMINAL_BATCH_STATUSES = {"completed", "partial_completed", "failed"}
OPEN_BATCH_STATUSES = {"queued", "running", "scheduled_sell", "closing"}
CSV_COLUMNS = [
    "batch_id",
    "item_id",
    "figi",
    "ticker",
    "status",
    "reason",
    "forecast_id",
    "bot_trade_id",
    "model_type_used",
    "validation_mae",
    "current_price",
    "predicted_price",
    "price_delta_percent",
    "quantity",
    "buy_price",
    "buy_amount",
    "scheduled_sell_at",
    "closed_at",
    "realized_pnl",
    "realized_pnl_percent",
    "error_message",
]

BATCH_STATUS_LABELS = {
    "queued": "В очереди",
    "running": "Сканируем акции",
    "scheduled_sell": "Ожидаем продажу",
    "closing": "Продаём",
    "completed": "Завершено",
    "partial_completed": "Частично завершено",
    "failed": "Ошибка",
}

ITEM_STATUS_LABELS = {
    "pending": "Ожидает",
    "scanning": "Проверяем",
    "skipped": "Пропущено",
    "bought": "Куплено",
    "closed": "Продано",
    "failed": "Ошибка",
}

REASON_LABELS = {
    "scheduled_sell": "Куплено, ждём продажу через 1 час",
    "predicted_not_positive": "Прогноз не показал рост",
    "no_successful_model": "Не удалось выбрать рабочую модель",
    "insufficient_candles": "Недостаточно свечей для прогноза",
    "candle_load_unavailable": "Свечи недоступны у брокера",
    "invalid_instrument": "Инструмент не подходит для bulk-покупки",
    "no_current_price": "Нет текущей цены",
    "invalid_lot": "Некорректный размер лота",
    "trade_rejected": "Сделка отклонена",
    "trade_error": "Ошибка сделки",
    "missing_forecast": "Нет сохранённого прогноза",
    "unexpected_error": "Неожиданная ошибка",
}

DATA_UNAVAILABLE_MARKERS = (
    "свеч",
    "candle",
    "candles",
    "insufficient",
    "недостаточно",
    "30014",
    "maximum request period",
    "no cache",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(round(float(value), 6)))
    except (TypeError, ValueError):
        return None


def _percent(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(round(float(value), 4)))
    except (TypeError, ValueError):
        return None


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


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _csv_root() -> Path:
    root = Path(settings.BULK_TRADE_CSV_DIR)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _csv_download_url(batch_id: int, csv_path: Optional[str]) -> Optional[str]:
    return f"/bot-trades/random-bulk/{batch_id}/csv" if csv_path else None


def _unique_instruments(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        figi = (item.get("figi") or "").strip().upper()
        if not figi or figi in seen:
            continue
        currency = (item.get("currency") or "RUB").upper()
        instrument_type = (item.get("instrument_type") or "share").lower()
        if currency != "RUB" or instrument_type != "share":
            continue
        seen.add(figi)
        result.append({**item, "figi": figi})
    return result


def _merge_candidates(popular: Iterable[Dict[str, Any]], broad: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for source_items in (popular, broad):
        for item in source_items:
            figi = (item.get("figi") or "").strip().upper()
            if not figi or figi in seen:
                continue
            seen.add(figi)
            result.append({**item, "figi": figi})
    return result


def _load_bulk_candidates(user_id: int) -> List[Dict[str, Any]]:
    popular = _unique_instruments(list_popular_moex_shares(user_id=user_id, prefer_broker=True))
    broad = _unique_instruments(list_moex_shares(user_id=user_id, prefer_broker=True, limit=1000))
    random.shuffle(popular)
    random.shuffle(broad)
    return _merge_candidates(popular, broad)


def _candidate_skip(user_id: int, instrument: Dict[str, Any]) -> tuple[Optional[str], str, Optional[float]]:
    figi = (instrument.get("figi") or "").strip().upper()
    ticker = (instrument.get("ticker") or "").strip()
    if not figi or not ticker:
        return "invalid_instrument", "Нет FIGI или ticker", None
    if (instrument.get("currency") or "RUB").upper() != "RUB":
        return "invalid_instrument", "Инструмент не в RUB", None
    if (instrument.get("instrument_type") or "share").lower() != "share":
        return "invalid_instrument", "Инструмент не является акцией", None
    lot = _to_int(instrument.get("lot"), 0)
    if lot <= 0:
        return "invalid_lot", "Некорректный размер лота", None

    price = _to_float(instrument.get("current_price"), 0.0)
    if price <= 0:
        try:
            price = _to_float(get_current_price(user_id=user_id, figi=figi, fallback_price=0.0), 0.0)
        except Exception as exc:  # noqa: BLE001 - mark as skipped, not failed
            return "no_current_price", str(exc), None
    if price <= 0:
        return "no_current_price", "Не удалось получить текущую цену", None
    return None, "", price


def _is_data_unavailable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in DATA_UNAVAILABLE_MARKERS)


def _item_status_label(status: Optional[str]) -> str:
    return ITEM_STATUS_LABELS.get(status or "", status or "Неизвестно")


def _reason_label(reason: Optional[str], message: Optional[str] = None) -> str:
    if reason in REASON_LABELS:
        return REASON_LABELS[reason]
    return message or reason or ""


def _batch_status_label(status: Optional[str]) -> str:
    return BATCH_STATUS_LABELS.get(status or "", status or "Неизвестно")


def _next_action_label(batch: BulkTradeBatch) -> str:
    if batch.status == "queued":
        return "Batch в очереди на запуск."
    if batch.status == "running":
        return "Сканируем акции, обучаем модели и покупаем только положительные прогнозы."
    if batch.status == "scheduled_sell":
        return "Покупки сделаны. Ждём продажи через 1 час после каждой покупки."
    if batch.status == "closing":
        return "Наступило время продажи. Закрываем купленные позиции."
    if batch.status in {"completed", "partial_completed"}:
        return "Batch завершён. CSV готов, если ссылка доступна."
    if batch.status == "failed":
        return "Batch завершился ошибкой."
    return ""


def _serialize_item(item: BulkTradeItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "batch_id": item.batch_id,
        "figi": item.figi,
        "ticker": item.ticker,
        "status": item.status,
        "status_label": _item_status_label(item.status),
        "reason": item.reason,
        "reason_label": _reason_label(item.reason, item.error_message),
        "forecast_id": item.forecast_id,
        "bot_trade_id": item.bot_trade_id,
        "model_type_used": item.model_type_used,
        "validation_mae": float(item.validation_mae) if item.validation_mae is not None else None,
        "current_price": float(item.current_price) if item.current_price is not None else None,
        "predicted_price": float(item.predicted_price) if item.predicted_price is not None else None,
        "price_delta_percent": float(item.price_delta_percent) if item.price_delta_percent is not None else None,
        "quantity": item.quantity,
        "buy_price": float(item.buy_price) if item.buy_price is not None else None,
        "buy_amount": float(item.buy_amount) if item.buy_amount is not None else None,
        "scheduled_sell_at": item.scheduled_sell_at,
        "closed_at": item.closed_at,
        "realized_pnl": float(item.realized_pnl) if item.realized_pnl is not None else None,
        "realized_pnl_percent": float(item.realized_pnl_percent) if item.realized_pnl_percent is not None else None,
        "error_message": item.error_message,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _best_forecast(compare_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    summary = compare_result.get("summary") if isinstance(compare_result.get("summary"), dict) else {}
    best = summary.get("best_forecast")
    return best if isinstance(best, dict) else None


def _apply_forecast_to_item(item: BulkTradeItem, best: Dict[str, Any], compare_result: Dict[str, Any]) -> None:
    metrics = best.get("metrics") if isinstance(best.get("metrics"), dict) else {}
    item.forecast_id = _to_int(best.get("forecast_id"), 0) or None
    item.model_type_used = best.get("model_type_effective") or best.get("model_type")
    item.validation_mae = _money(metrics.get("validation_mae") if metrics.get("validation_mae") is not None else metrics.get("MAE"))
    item.current_price = _money(best.get("current_price"))
    item.predicted_price = _money(best.get("predicted_price"))
    item.price_delta_percent = _percent(best.get("price_delta_percent"))
    item.raw_result = {
        "summary": compare_result.get("summary"),
        "best_forecast": {
            "forecast_id": best.get("forecast_id"),
            "model_type": best.get("model_type"),
            "model_type_effective": best.get("model_type_effective"),
            "price_delta_percent": best.get("price_delta_percent"),
            "metrics": metrics,
        },
    }


def _refresh_counts(db: Session, batch: BulkTradeBatch) -> BulkTradeBatch:
    items = db.query(BulkTradeItem).filter(BulkTradeItem.batch_id == batch.id).all()
    batch.scanned_count = len(items)
    batch.bought_count = sum(1 for item in items if item.bot_trade_id is not None)
    batch.skipped_count = sum(1 for item in items if item.status == "skipped")
    batch.failed_count = sum(1 for item in items if item.status == "failed")
    batch.closed_count = sum(1 for item in items if item.status == "closed")
    return batch


def serialize_bulk_batch(db: Session, batch: BulkTradeBatch, include_items: bool = True) -> Dict[str, Any]:
    if batch is None:
        raise HTTPException(status_code=404, detail="Bulk trade batch not found")
    _refresh_counts(db, batch)
    items = []
    if include_items:
        rows = (
            db.query(BulkTradeItem)
            .filter(BulkTradeItem.batch_id == batch.id)
            .order_by(BulkTradeItem.id.asc())
            .all()
        )
        items = [_serialize_item(row) for row in rows]
    nearest_scheduled_sell_at = None
    if include_items:
        open_sell_times = [
            item.get("scheduled_sell_at")
            for item in items
            if item.get("bot_trade_id") and item.get("status") in {"bought", "scanning"} and item.get("scheduled_sell_at")
        ]
        nearest_scheduled_sell_at = min(open_sell_times) if open_sell_times else None
    realized_pnl_total = sum(_to_float(item.get("realized_pnl"), 0.0) for item in items)
    buy_amount_total = sum(_to_float(item.get("buy_amount"), 0.0) for item in items if item.get("buy_amount") is not None)
    realized_pnl_percent_total = (realized_pnl_total / buy_amount_total * 100) if buy_amount_total > 0 else None
    return {
        "id": batch.id,
        "batch_id": batch.id,
        "user_id": batch.user_id,
        "account_id": batch.account_id,
        "status": batch.status,
        "status_label": _batch_status_label(batch.status),
        "next_action_label": _next_action_label(batch),
        "target_count": batch.target_count,
        "growth_threshold_percent": float(batch.growth_threshold_percent or 0),
        "candidate_count": batch.candidate_count,
        "scanned_count": batch.scanned_count,
        "bought_count": batch.bought_count,
        "skipped_count": batch.skipped_count,
        "failed_count": batch.failed_count,
        "closed_count": batch.closed_count,
        "mode": batch.mode,
        "csv_download_url": _csv_download_url(batch.id, batch.csv_path),
        "nearest_scheduled_sell_at": nearest_scheduled_sell_at,
        "realized_pnl_total": round(realized_pnl_total, 6),
        "realized_pnl_percent_total": round(realized_pnl_percent_total, 4) if realized_pnl_percent_total is not None else None,
        "error_message": batch.error_message,
        "started_at": batch.started_at,
        "finished_at": batch.finished_at,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
        "items": items,
    }


def get_user_bulk_batch(db: Session, user_id: int, batch_id: int) -> BulkTradeBatch:
    batch = (
        db.query(BulkTradeBatch)
        .filter(BulkTradeBatch.id == batch_id, BulkTradeBatch.user_id == user_id)
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Batch рандомной покупки не найден")
    return batch


def list_user_bulk_batches(db: Session, user_id: int, limit: int = 5) -> List[BulkTradeBatch]:
    return (
        db.query(BulkTradeBatch)
        .filter(BulkTradeBatch.user_id == user_id)
        .order_by(BulkTradeBatch.created_at.desc(), BulkTradeBatch.id.desc())
        .limit(max(1, min(int(limit or 5), 20)))
        .all()
    )


def get_latest_user_bulk_batch(db: Session, user_id: int) -> BulkTradeBatch:
    active = (
        db.query(BulkTradeBatch)
        .filter(BulkTradeBatch.user_id == user_id, BulkTradeBatch.status.in_(list(OPEN_BATCH_STATUSES)))
        .order_by(BulkTradeBatch.created_at.desc(), BulkTradeBatch.id.desc())
        .first()
    )
    if active:
        return active
    latest = (
        db.query(BulkTradeBatch)
        .filter(BulkTradeBatch.user_id == user_id)
        .order_by(BulkTradeBatch.created_at.desc(), BulkTradeBatch.id.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="Batch рандомной покупки не найден")
    return latest


def assert_random_bulk_start_allowed(*, has_tinkoff_token: bool) -> None:
    if not settings.USE_SANDBOX:
        raise HTTPException(status_code=403, detail="Рандомная покупка 30 акций доступна только в sandbox-режиме")
    if not settings.BULK_TRADE_WORKER_ENABLED:
        raise HTTPException(status_code=403, detail="Bulk worker выключен. Установите BULK_TRADE_WORKER_ENABLED=true")
    if settings.AUTO_SELL_DRY_RUN:
        raise HTTPException(status_code=403, detail="AUTO_SELL_DRY_RUN должен быть false, чтобы включить sandbox-автопродажу")
    if not has_tinkoff_token:
        raise HTTPException(status_code=400, detail="Для sandbox-покупок нужен Tinkoff token")


def create_random_bulk_batch(
    db: Session,
    *,
    user_id: int,
    account_id: Optional[str],
    target_count: int = 30,
) -> BulkTradeBatch:
    account_id = (account_id or "").strip() or None
    target_count = max(1, min(int(target_count or 30), 30))
    batch = BulkTradeBatch(
        user_id=user_id,
        account_id=account_id,
        status="queued",
        target_count=target_count,
        growth_threshold_percent=Decimal("0"),
        mode="sandbox",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def _mark_item_skipped(db: Session, batch: BulkTradeBatch, item: BulkTradeItem, reason: str, message: str = "") -> None:
    item.status = "skipped"
    item.reason = reason
    item.error_message = message or None
    db.add(item)
    _refresh_counts(db, batch)
    db.add(batch)
    db.commit()


def _mark_item_failed(db: Session, batch: BulkTradeBatch, item: BulkTradeItem, reason: str, message: str) -> None:
    item.status = "failed"
    item.reason = reason
    item.error_message = message
    db.add(item)
    _refresh_counts(db, batch)
    db.add(batch)
    db.commit()


def _forecast_request_for_item(batch: BulkTradeBatch, instrument: Dict[str, Any]) -> ForecastRequest:
    return ForecastRequest(
        figi=instrument["figi"],
        ticker=instrument.get("ticker"),
        account_id=batch.account_id,
        source="bulk",
        horizon="1h",
        model_type="adaptive",
        hyperparam_mode="auto",
        flat_threshold_percent=0.0,
        days=3,
        lags=10,
        adaptive_params={"ensemble_enabled": True},
    )


def _buy_item_from_forecast(
    db: Session,
    *,
    batch: BulkTradeBatch,
    item: BulkTradeItem,
    best: Dict[str, Any],
    instrument: Dict[str, Any],
) -> None:
    forecast_id = _to_int(best.get("forecast_id"), 0)
    if forecast_id <= 0:
        _mark_item_failed(db, batch, item, "missing_forecast", "Best model result has no saved forecast")
        return

    lot = max(_to_int(best.get("lot") or instrument.get("lot"), 1), 1)
    scheduled_sell_at = _utc_now() + timedelta(hours=1)
    trade = confirm_bot_trade(
        db=db,
        user_id=batch.user_id,
        request=BotTradeConfirmRequest(
            forecast_id=forecast_id,
            side="buy",
            action=best.get("recommendation", {}).get("action") if isinstance(best.get("recommendation"), dict) else None,
            quantity=lot,
            auto_sell_enabled=True,
            auto_sell_target_enabled=False,
            scheduled_sell_at=scheduled_sell_at,
            sell_target_price=None,
            idempotency_key=f"random-bulk:{batch.id}:{item.figi}:buy",
            account_id=batch.account_id,
        ),
    )
    trade.batch_id = batch.id
    item.status = "bought"
    item.reason = "scheduled_sell"
    item.bot_trade_id = trade.id
    item.quantity = trade.quantity
    item.buy_price = trade.price
    item.buy_amount = trade.amount
    item.scheduled_sell_at = trade.scheduled_sell_at
    db.add(trade)
    db.add(item)
    _refresh_counts(db, batch)
    db.add(batch)
    db.commit()


def process_random_bulk_batch(batch_id: int) -> None:
    db = SessionLocal()
    try:
        batch = db.query(BulkTradeBatch).filter(BulkTradeBatch.id == batch_id).first()
        if not batch or batch.status not in {"queued", "running"}:
            return

        batch.status = "running"
        batch.started_at = batch.started_at or _utc_now()
        db.add(batch)
        db.commit()

        instruments = _load_bulk_candidates(batch.user_id)
        batch.candidate_count = len(instruments)
        db.add(batch)
        db.commit()

        for instrument in instruments:
            db.refresh(batch)
            if batch.bought_count >= batch.target_count:
                break

            item = BulkTradeItem(
                batch_id=batch.id,
                user_id=batch.user_id,
                figi=instrument["figi"],
                ticker=instrument.get("ticker"),
                status="scanning",
            )
            db.add(item)
            db.commit()
            db.refresh(item)

            try:
                skip_reason, skip_message, current_price = _candidate_skip(batch.user_id, instrument)
                if skip_reason:
                    _mark_item_skipped(db, batch, item, skip_reason, skip_message)
                    continue
                if current_price is not None:
                    item.current_price = _money(current_price)
                    db.add(item)
                    db.commit()

                compare_result = compare_forecast_models(
                    db=db,
                    user_id=batch.user_id,
                    request=_forecast_request_for_item(batch, instrument),
                )
                best = _best_forecast(compare_result)
                if not best:
                    _mark_item_skipped(db, batch, item, "no_successful_model", "No successful model result")
                    continue

                _apply_forecast_to_item(item, best, compare_result)
                db.add(item)
                db.commit()
                delta_percent = _to_float(best.get("price_delta_percent"), 0.0)
                if delta_percent <= 0:
                    _mark_item_skipped(db, batch, item, "predicted_not_positive")
                    continue

                _buy_item_from_forecast(db, batch=batch, item=item, best=best, instrument=instrument)
            except HTTPException as exc:
                db.rollback()
                item = db.query(BulkTradeItem).filter(BulkTradeItem.id == item.id).first()
                if item:
                    detail = str(exc.detail)
                    status_code = int(getattr(exc, "status_code", 500) or 500)
                    if status_code == 400:
                        _mark_item_skipped(db, batch, item, "trade_rejected", detail)
                    else:
                        _mark_item_failed(db, batch, item, "trade_error", detail)
            except Exception as exc:  # noqa: BLE001 - keep scanning remaining instruments
                db.rollback()
                logger.exception("Random bulk item failed batch_id=%s figi=%s: %s", batch.id, instrument.get("figi"), exc)
                item = db.query(BulkTradeItem).filter(BulkTradeItem.id == item.id).first()
                if item:
                    if _is_data_unavailable_error(exc):
                        _mark_item_skipped(db, batch, item, "insufficient_candles", str(exc))
                    else:
                        _mark_item_failed(db, batch, item, "unexpected_error", str(exc))

        sync_bulk_batch_from_trades(db, batch.id)
        batch = db.query(BulkTradeBatch).filter(BulkTradeBatch.id == batch.id).first()
        if not batch:
            return

        if batch.bought_count > 0:
            batch.status = "scheduled_sell"
        else:
            batch.status = "partial_completed"
            batch.finished_at = _utc_now()
            generate_bulk_trade_csv(db, batch)

        batch.raw_summary = {
            "candidate_count": batch.candidate_count,
            "scanned_count": batch.scanned_count,
            "bought_count": batch.bought_count,
            "target_count": batch.target_count,
        }
        db.add(batch)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Random bulk batch failed batch_id=%s: %s", batch_id, exc)
        batch = db.query(BulkTradeBatch).filter(BulkTradeBatch.id == batch_id).first()
        if batch:
            batch.status = "failed"
            batch.error_message = str(exc)
            batch.finished_at = _utc_now()
            db.add(batch)
            db.commit()
            generate_bulk_trade_csv(db, batch)
    finally:
        db.close()


def sync_bulk_batch_from_trades(db: Session, batch_id: int) -> Optional[BulkTradeBatch]:
    batch = db.query(BulkTradeBatch).filter(BulkTradeBatch.id == batch_id).first()
    if not batch:
        return None

    items = db.query(BulkTradeItem).filter(BulkTradeItem.batch_id == batch.id).all()
    trade_ids = [item.bot_trade_id for item in items if item.bot_trade_id]
    trades = {}
    if trade_ids:
        trades = {
            trade.id: trade
            for trade in db.query(BotTrade).filter(BotTrade.id.in_(trade_ids)).all()
        }

    for item in items:
        trade = trades.get(item.bot_trade_id)
        if not trade:
            continue
        item.buy_price = item.buy_price or trade.price
        item.buy_amount = item.buy_amount or trade.amount
        item.quantity = item.quantity or trade.quantity
        item.scheduled_sell_at = item.scheduled_sell_at or trade.scheduled_sell_at
        if trade.status == "closed":
            item.status = "closed"
            item.closed_at = trade.closed_at
            item.realized_pnl = trade.realized_pnl
            item.realized_pnl_percent = trade.realized_pnl_percent
            item.error_message = None
        elif trade.status == "failed":
            item.status = "failed"
            item.error_message = trade.error_message or "Auto-sell failed"
        elif item.status not in {"failed", "closed"}:
            item.status = "bought"
        db.add(item)

    _refresh_counts(db, batch)
    if batch.status in {"scheduled_sell", "closing"} and batch.bought_count > 0:
        open_items = [item for item in items if item.bot_trade_id and item.status not in {"closed", "failed"}]
        if not open_items:
            batch.status = "completed" if batch.bought_count >= batch.target_count and batch.failed_count == 0 else "partial_completed"
            batch.finished_at = batch.finished_at or _utc_now()
            generate_bulk_trade_csv(db, batch)
    db.add(batch)
    db.commit()
    return batch


def generate_bulk_trade_csv(db: Session, batch: BulkTradeBatch) -> Path:
    sync_items = (
        db.query(BulkTradeItem)
        .filter(BulkTradeItem.batch_id == batch.id)
        .order_by(BulkTradeItem.id.asc())
        .all()
    )
    path = _csv_root() / f"random_bulk_batch_{batch.id}.csv"
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for item in sync_items:
            writer.writerow({
                "batch_id": batch.id,
                "item_id": item.id,
                "figi": item.figi,
                "ticker": item.ticker,
                "status": item.status,
                "reason": item.reason,
                "forecast_id": item.forecast_id,
                "bot_trade_id": item.bot_trade_id,
                "model_type_used": item.model_type_used,
                "validation_mae": _to_float(item.validation_mae, 0.0) if item.validation_mae is not None else "",
                "current_price": _to_float(item.current_price, 0.0) if item.current_price is not None else "",
                "predicted_price": _to_float(item.predicted_price, 0.0) if item.predicted_price is not None else "",
                "price_delta_percent": _to_float(item.price_delta_percent, 0.0) if item.price_delta_percent is not None else "",
                "quantity": item.quantity,
                "buy_price": _to_float(item.buy_price, 0.0) if item.buy_price is not None else "",
                "buy_amount": _to_float(item.buy_amount, 0.0) if item.buy_amount is not None else "",
                "scheduled_sell_at": _iso(item.scheduled_sell_at),
                "closed_at": _iso(item.closed_at),
                "realized_pnl": _to_float(item.realized_pnl, 0.0) if item.realized_pnl is not None else "",
                "realized_pnl_percent": _to_float(item.realized_pnl_percent, 0.0) if item.realized_pnl_percent is not None else "",
                "error_message": item.error_message,
            })
    batch.csv_path = str(path)
    db.add(batch)
    db.commit()
    return path


def process_due_bulk_batches(db: Session, limit: int = 20) -> Dict[str, int]:
    batches = (
        db.query(BulkTradeBatch)
        .filter(BulkTradeBatch.status.in_(["scheduled_sell", "closing"]))
        .order_by(BulkTradeBatch.created_at.asc(), BulkTradeBatch.id.asc())
        .limit(max(1, min(int(limit or 20), 100)))
        .all()
    )
    processed = 0
    completed = 0
    due_batches = 0
    for batch in batches:
        counts = count_auto_sell_candidates(db=db, user_id=batch.user_id, batch_id=batch.id)
        if counts.get("due_count", 0) <= 0:
            sync_bulk_batch_from_trades(db, batch.id)
            continue

        due_batches += 1
        batch.status = "closing"
        db.add(batch)
        db.commit()
        summary = process_due_auto_sells(db=db, limit=200, user_id=batch.user_id, batch_id=batch.id)
        batch.raw_summary = {**(batch.raw_summary or {}), "last_auto_sell_summary": summary}
        db.add(batch)
        db.commit()
        refreshed = sync_bulk_batch_from_trades(db, batch.id)
        processed += 1
        if refreshed and refreshed.status in TERMINAL_BATCH_STATUSES:
            completed += 1
    return {"processed": processed, "completed": completed, "candidates": due_batches}


async def run_random_bulk_worker(poll_seconds: int = 60) -> None:
    poll_seconds = max(15, int(poll_seconds or 60))
    logger.info("Random bulk worker started; poll_seconds=%s", poll_seconds)

    while True:
        db = SessionLocal()
        try:
            summary = process_due_bulk_batches(db)
            if summary.get("completed"):
                logger.info("Random bulk worker cycle summary: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Random bulk worker cycle failed: %s", exc)
        finally:
            db.close()

        await asyncio.sleep(poll_seconds)
