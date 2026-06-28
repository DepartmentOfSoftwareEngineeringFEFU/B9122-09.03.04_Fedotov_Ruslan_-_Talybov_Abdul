# app/services/data_service.py
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.core.db import SessionLocal
from app.core.tinkoff_client import TinkoffClient
from app.models.candle import Candle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryCandle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class ForecastCandleLoad:
    candles: List[Any]
    interval: str
    source: str
    attempts: List[Dict[str, Any]]
    error_message: Optional[str] = None


CHUNK_WINDOWS = {
    "1min": timedelta(hours=12),
    "5min": timedelta(days=2),
}


def _money_to_float(money) -> float:
    return float(getattr(money, "units", 0) or 0) + float(getattr(money, "nano", 0) or 0) / 1_000_000_000


def _normalize_ts(ts):
    """Store timestamps in DB as naive UTC.

    T-Invest returns timezone-aware UTC datetimes, while the existing MySQL
    ``DateTime`` column returns naive datetimes. If we keep aware datetimes in
    memory and compare them with rows loaded from MySQL, duplicate detection can
    miss already saved candles and the unique index raises IntegrityError.
    """
    if ts is None:
        return None
    if getattr(ts, "tzinfo", None) is not None:
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def _normalize_interval(interval: str) -> str:
    normalized = (interval or "1min").strip().lower()
    aliases = {
        "1m": "1min",
        "minute": "1min",
        "5m": "5min",
    }
    return aliases.get(normalized, normalized)


def _chunk_ranges(days: int, interval: str) -> List[tuple[datetime, datetime]]:
    normalized_interval = _normalize_interval(interval)
    to_dt = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(days=max(1, int(days or 1)))
    window = CHUNK_WINDOWS.get(normalized_interval)
    if window is None:
        return [(from_dt, to_dt)]

    ranges = []
    cursor = from_dt
    while cursor < to_dt:
        next_cursor = min(cursor + window, to_dt)
        ranges.append((cursor, next_cursor))
        cursor = next_cursor
    return ranges


def _dedupe_raw_candles(raw_candles: List[Any]) -> List[Any]:
    by_ts = {}
    for candle in raw_candles:
        ts = _normalize_ts(getattr(candle, "time", None))
        if ts is None:
            continue
        by_ts[ts] = candle
    return [by_ts[ts] for ts in sorted(by_ts)]


def _fetch_raw_candles_chunked(client: TinkoffClient, figi: str, days: int, interval: str) -> List[Any]:
    chunks = []
    for from_dt, to_dt in _chunk_ranges(days, interval):
        chunks.extend(client.get_candles(figi, interval=interval, from_=from_dt, to=to_dt))
    return _dedupe_raw_candles(chunks)


def _raw_candles_to_memory(raw_candles: List[Any]) -> List[MemoryCandle]:
    result = []
    for candle in _dedupe_raw_candles(raw_candles):
        ts = _normalize_ts(getattr(candle, "time", None))
        if ts is None:
            continue
        result.append(MemoryCandle(
            ts=ts,
            open=_money_to_float(candle.open),
            high=_money_to_float(candle.high),
            low=_money_to_float(candle.low),
            close=_money_to_float(candle.close),
            volume=float(getattr(candle, "volume", 0) or 0),
        ))
    return result


def _chart_iso(ts) -> str:
    normalized = _normalize_ts(ts)
    if normalized is None:
        return ""
    return normalized.replace(tzinfo=timezone.utc).isoformat()


def _candle_row_to_chart(row: Candle) -> Dict:
    return {
        "x": _chart_iso(row.ts),
        "o": round(float(row.open), 6),
        "h": round(float(row.high), 6),
        "l": round(float(row.low), 6),
        "c": round(float(row.close), 6),
        "v": int(row.volume or 0),
        "source": "cache",
    }


def _bucket_key(ts, interval: str):
    normalized = (interval or "1min").strip().lower()
    if normalized in {"day", "1d"}:
        return ts.date()
    if normalized in {"hour", "1h"}:
        return ts.replace(minute=0, second=0, microsecond=0)
    if normalized in {"15min", "15m"}:
        return ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)
    if normalized in {"5min", "5m"}:
        return ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)
    return ts


def _compress_cached_rows(rows: List[Candle], interval: str) -> List[Dict]:
    if not rows:
        return []

    buckets = []
    current_key = None
    current = None
    for row in rows:
        key = _bucket_key(row.ts, interval)
        if key != current_key:
            if current:
                buckets.append(current)
            current_key = key
            current = {
                "x": _chart_iso(row.ts),
                "o": float(row.open),
                "h": float(row.high),
                "l": float(row.low),
                "c": float(row.close),
                "v": int(row.volume or 0),
                "source": "cache",
            }
            continue

        current["h"] = max(current["h"], float(row.high))
        current["l"] = min(current["l"], float(row.low))
        current["c"] = float(row.close)
        current["v"] += int(row.volume or 0)
        current["x"] = _chart_iso(row.ts)

    if current:
        buckets.append(current)

    return [
        {
            **item,
            "o": round(item["o"], 6),
            "h": round(item["h"], 6),
            "l": round(item["l"], 6),
            "c": round(item["c"], 6),
        }
        for item in buckets
    ]


def load_cached_candles(figi: str, days: int = 1, user_id: int = None, interval: str = "1min") -> List[Dict]:
    normalized_figi = (figi or "").strip().upper()
    if not normalized_figi or not user_id:
        return []

    db = SessionLocal()
    try:
        latest_ts = db.query(func.max(Candle.ts)).filter(
            Candle.user_id == user_id,
            Candle.figi == normalized_figi,
        ).scalar()
        if not latest_ts:
            return []

        from_ts = latest_ts - timedelta(days=max(1, int(days or 1)))
        rows = db.query(Candle).filter(
            Candle.user_id == user_id,
            Candle.figi == normalized_figi,
            Candle.ts >= from_ts,
        ).order_by(Candle.ts.asc()).all()

        if interval and interval.strip().lower() not in {"1min", "1m", "minute"}:
            return _compress_cached_rows(rows, interval)
        return [_candle_row_to_chart(row) for row in rows]
    finally:
        db.close()


def fetch_and_store_candles(figi: str, days: int = 1, user_id: int = None, interval: str = "1min") -> List[Dict]:
    logger.info("Starting candle load figi=%s days=%s interval=%s user_id=%s", figi, days, interval, user_id)
    if not user_id:
        raise ValueError("user_id is required for storing candles")

    normalized_figi = (figi or "").strip().upper()
    client = TinkoffClient(user_id=user_id)
    try:
        raw_candles = _fetch_raw_candles_chunked(client, normalized_figi, days=days, interval=interval)
    except Exception:
        cached = load_cached_candles(normalized_figi, days=days, user_id=user_id, interval=interval)
        if cached:
            logger.warning(
                "T-Invest candle load failed, serving cached candles user_id=%s figi=%s days=%s interval=%s count=%s",
                user_id,
                normalized_figi,
                days,
                interval,
                len(cached),
                exc_info=True,
            )
            return cached
        logger.exception("T-Invest candle load failed and no cache is available user_id=%s figi=%s", user_id, normalized_figi)
        return []

    logger.info("Received %s candles from T-Invest figi=%s user_id=%s", len(raw_candles), figi, user_id)

    prepared_by_ts = {}
    for candle in raw_candles:
        ts = _normalize_ts(candle.time)
        if ts is None:
            continue

        open_price = _money_to_float(candle.open)
        high_price = _money_to_float(candle.high)
        low_price = _money_to_float(candle.low)
        close_price = _money_to_float(candle.close)
        # Dict by timestamp makes the endpoint safe even if the broker returns
        # the same candle twice in a single response. Keep the latest payload.
        prepared_by_ts[ts] = {
            "user_id": user_id,
            "figi": normalized_figi,
            "ts": ts,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": candle.volume,
        }

    prepared = [prepared_by_ts[ts] for ts in sorted(prepared_by_ts)]
    chart_candles = [
        {
            "x": _chart_iso(item["ts"]),
            "o": round(item["open"], 6),
            "h": round(item["high"], 6),
            "l": round(item["low"], 6),
            "c": round(item["close"], 6),
            "v": item["volume"],
        }
        for item in prepared
    ]

    if not prepared:
        return []

    db = SessionLocal()
    try:
        if db.bind and db.bind.dialect.name == "mysql":
            stmt = mysql_insert(Candle).values(prepared)
            update_columns = {
                "open": stmt.inserted.open,
                "high": stmt.inserted.high,
                "low": stmt.inserted.low,
                "close": stmt.inserted.close,
                "volume": stmt.inserted.volume,
            }
            result = db.execute(stmt.on_duplicate_key_update(**update_columns))
            db.commit()
            logger.info(
                "Candles upserted user_id=%s figi=%s received=%s affected=%s",
                user_id,
                normalized_figi,
                len(prepared),
                getattr(result, "rowcount", None),
            )
        else:
            timestamps = [item["ts"] for item in prepared]
            existing = {
                _normalize_ts(row.ts): row
                for row in db.query(Candle).filter(
                    Candle.user_id == user_id,
                    Candle.figi == normalized_figi,
                    Candle.ts.in_(timestamps),
                ).all()
            }
            to_insert = []
            updated_count = 0
            for item in prepared:
                existing_row = existing.get(item["ts"])
                if existing_row:
                    existing_row.open = item["open"]
                    existing_row.high = item["high"]
                    existing_row.low = item["low"]
                    existing_row.close = item["close"]
                    existing_row.volume = item["volume"]
                    updated_count += 1
                else:
                    to_insert.append(Candle(**item))

            if to_insert:
                db.bulk_save_objects(to_insert)
            db.commit()
            logger.info(
                "Candles processed user_id=%s figi=%s received=%s created=%s updated=%s",
                user_id,
                normalized_figi,
                len(prepared),
                len(to_insert),
                updated_count,
            )
    except IntegrityError:
        # Last line of defense for non-MySQL test/dev DBs and rare races: the
        # endpoint must not die only because another request inserted the same
        # candle first. Re-read and update rows one by one.
        db.rollback()
        logger.warning(
            "Candle unique conflict, retrying row-by-row user_id=%s figi=%s",
            user_id,
            normalized_figi,
            exc_info=True,
        )
        timestamps = [item["ts"] for item in prepared]
        existing = {
            _normalize_ts(row.ts): row
            for row in db.query(Candle).filter(
                Candle.user_id == user_id,
                Candle.figi == normalized_figi,
                Candle.ts.in_(timestamps),
            ).all()
        }
        for item in prepared:
            row = existing.get(item["ts"])
            if row is None:
                db.add(Candle(**item))
                continue
            row.open = item["open"]
            row.high = item["high"]
            row.low = item["low"]
            row.close = item["close"]
            row.volume = item["volume"]
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Database error while saving candles user_id=%s figi=%s", user_id, normalized_figi)
        cached = load_cached_candles(normalized_figi, days=days, user_id=user_id, interval=interval)
        if cached:
            logger.warning(
                "Serving cached candles after save failure user_id=%s figi=%s count=%s",
                user_id,
                normalized_figi,
                len(cached),
            )
            return cached
        raise
    finally:
        db.close()

    return chart_candles


def load_candles_for_forecast(
    db,
    *,
    figi: str,
    days: int,
    user_id: int,
    min_required_by_interval: Dict[str, int],
) -> ForecastCandleLoad:
    normalized_figi = (figi or "").strip().upper()
    attempts: List[Dict[str, Any]] = []

    cached = (
        db.query(Candle)
        .filter(Candle.user_id == user_id, Candle.figi == normalized_figi)
        .order_by(Candle.ts.asc())
        .all()
    )
    min_1min = int(min_required_by_interval.get("1min") or 0)
    attempts.append({"interval": "1min", "source": "cache", "count": len(cached)})
    if len(cached) >= min_1min:
        return ForecastCandleLoad(candles=cached, interval="1min", source="cache", attempts=attempts)

    try:
        fetch_and_store_candles(figi=normalized_figi, days=max(days, 1), user_id=user_id, interval="1min")
        db.expire_all()
        cached = (
            db.query(Candle)
            .filter(Candle.user_id == user_id, Candle.figi == normalized_figi)
            .order_by(Candle.ts.asc())
            .all()
        )
        attempts.append({"interval": "1min", "source": "broker_chunked", "count": len(cached)})
        if len(cached) >= min_1min:
            return ForecastCandleLoad(candles=cached, interval="1min", source="broker_chunked", attempts=attempts)
    except Exception as exc:  # noqa: BLE001 - fallback to 5min below
        attempts.append({"interval": "1min", "source": "broker_chunked", "count": len(cached), "error": str(exc)})
        logger.warning("Chunked 1min candle load failed user_id=%s figi=%s: %s", user_id, normalized_figi, exc)

    client = TinkoffClient(user_id=user_id)
    try:
        raw_5min = _fetch_raw_candles_chunked(client, normalized_figi, days=max(days, 1), interval="5min")
        memory_5min = _raw_candles_to_memory(raw_5min)
        min_5min = int(min_required_by_interval.get("5min") or min_1min)
        attempts.append({"interval": "5min", "source": "broker_fallback", "count": len(memory_5min)})
        if len(memory_5min) >= min_5min:
            return ForecastCandleLoad(candles=memory_5min, interval="5min", source="broker_fallback", attempts=attempts)
        return ForecastCandleLoad(
            candles=memory_5min,
            interval="5min",
            source="broker_fallback",
            attempts=attempts,
            error_message=f"Недостаточно свечей 5min: нужно минимум {min_5min}, доступно {len(memory_5min)}",
        )
    except Exception as exc:  # noqa: BLE001
        attempts.append({"interval": "5min", "source": "broker_fallback", "count": 0, "error": str(exc)})
        return ForecastCandleLoad(
            candles=cached,
            interval="1min",
            source="unavailable",
            attempts=attempts,
            error_message=str(exc),
        )
