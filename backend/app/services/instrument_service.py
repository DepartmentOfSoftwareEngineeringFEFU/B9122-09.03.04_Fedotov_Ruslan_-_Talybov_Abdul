from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.tinkoff_client import TinkoffClient
from app.services.recommendation_service import PortfolioPosition
from app.services.trade_service import get_average_buy_price, get_portfolio

logger = logging.getLogger(__name__)


POPULAR_MOEX_SHARES: List[Dict[str, Any]] = [
    {"figi": "BBG004730N88", "ticker": "SBER", "name": "Сбер Банк", "exchange": "MOEX", "currency": "RUB", "lot": 10},
    {"figi": "BBG004731032", "ticker": "LKOH", "name": "Лукойл", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG004730RP0", "ticker": "GAZP", "name": "Газпром", "exchange": "MOEX", "currency": "RUB", "lot": 10},
    {"figi": "BBG004731489", "ticker": "GMKN", "name": "Норникель", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG004731354", "ticker": "ROSN", "name": "Роснефть", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG00475KKY8", "ticker": "NVTK", "name": "Новатэк", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG000R607Y3", "ticker": "PLZL", "name": "Полюс", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG004S689R0", "ticker": "PHOR", "name": "ФосАгро", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG004S681M2", "ticker": "NLMK", "name": "НЛМК", "exchange": "MOEX", "currency": "RUB", "lot": 10},
    {"figi": "BBG00475K6C3", "ticker": "CHMF", "name": "Северсталь", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG004S68507", "ticker": "MAGN", "name": "ММК", "exchange": "MOEX", "currency": "RUB", "lot": 100},
    {"figi": "BBG004RVFFC0", "ticker": "TATN", "name": "Татнефть", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG004S68829", "ticker": "TATNP", "name": "Татнефть ап", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG0047315D0", "ticker": "SNGS", "name": "Сургутнефтегаз", "exchange": "MOEX", "currency": "RUB", "lot": 100},
    {"figi": "BBG004S681W1", "ticker": "SNGSP", "name": "Сургутнефтегаз ап", "exchange": "MOEX", "currency": "RUB", "lot": 100},
    {"figi": "BBG004S68473", "ticker": "SIBN", "name": "Газпром нефть", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG004S681B4", "ticker": "MTSS", "name": "МТС", "exchange": "MOEX", "currency": "RUB", "lot": 10},
    {"figi": "BBG004S683W7", "ticker": "AFLT", "name": "Аэрофлот", "exchange": "MOEX", "currency": "RUB", "lot": 100},
    {"figi": "BBG004S68B31", "ticker": "ALRS", "name": "АЛРОСА", "exchange": "MOEX", "currency": "RUB", "lot": 10},
    {"figi": "BBG004730JJ5", "ticker": "MOEX", "name": "Московская биржа", "exchange": "MOEX", "currency": "RUB", "lot": 10},
    {"figi": "BBG004730ZJ9", "ticker": "VTBR", "name": "Банк ВТБ", "exchange": "MOEX", "currency": "RUB", "lot": 10000},
    {"figi": "BBG004S684M6", "ticker": "IRAO", "name": "Интер РАО", "exchange": "MOEX", "currency": "RUB", "lot": 1000},
    {"figi": "BBG00475JZZ6", "ticker": "FEES", "name": "ФСК Россети", "exchange": "MOEX", "currency": "RUB", "lot": 10000},
    {"figi": "BBG00475K2X9", "ticker": "HYDR", "name": "РусГидро", "exchange": "MOEX", "currency": "RUB", "lot": 1000},
    {"figi": "BBG004S68BH6", "ticker": "PIKK", "name": "ПИК", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG004S68614", "ticker": "AFKS", "name": "АФК Система", "exchange": "MOEX", "currency": "RUB", "lot": 100},
    {"figi": "BBG004RVFCY3", "ticker": "MGNT", "name": "Магнит", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG009GSYN76", "ticker": "CBOM", "name": "МКБ", "exchange": "MOEX", "currency": "RUB", "lot": 100},
    {"figi": "BBG00475KHX6", "ticker": "TRNFP", "name": "Транснефть ап", "exchange": "MOEX", "currency": "RUB", "lot": 1},
    {"figi": "BBG008F2T3T2", "ticker": "RUAL", "name": "Русал", "exchange": "MOEX", "currency": "RUB", "lot": 10},
]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 1) -> int:
    try:
        if value is None:
            return default
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def lot_price(unit_price: Optional[float], lot: Optional[int]) -> Optional[float]:
    price = _to_float(unit_price, 0.0)
    lot_size = _to_int(lot, 1)
    return round(price * lot_size, 6) if price > 0 else None


def _extract_portfolio(raw: Dict[str, Any]) -> tuple[list, Dict[str, Any]]:
    inner = raw.get("portfolio", raw) if isinstance(raw, dict) else {}
    if isinstance(inner, dict) and "portfolio" in inner and isinstance(inner.get("portfolio"), dict):
        inner = inner.get("portfolio")
    positions = inner.get("portfolio", []) if isinstance(inner, dict) else []
    summary = inner.get("summary", {}) if isinstance(inner, dict) else {}
    return positions, summary


def list_popular_moex_shares(user_id: Optional[int] = None, prefer_broker: bool = True) -> List[Dict[str, Any]]:
    """Return a stable list of popular MOEX shares.

    We prefer broker-validated instruments, but keep the static seed as a safe
    fallback because FIGI selection must still work when the instruments API is
    temporarily unavailable.
    """
    if user_id and prefer_broker:
        try:
            items = TinkoffClient(user_id=user_id).get_popular_moex_shares(limit=30)
            if items:
                return [_normalize_instrument(item) for item in items]
        except Exception as exc:
            logger.warning("Could not fetch popular MOEX shares from T-Invest; using static seed: %s", exc)
    return [_normalize_instrument(item) for item in POPULAR_MOEX_SHARES]


def list_moex_shares(user_id: Optional[int] = None, prefer_broker: bool = True, limit: int = 1000) -> List[Dict[str, Any]]:
    """Return a broad MOEX RUB share list for searchable instrument pickers."""
    normalized_limit = max(1, min(int(limit or 1000), 1000))
    if user_id and prefer_broker:
        try:
            items = TinkoffClient(user_id=user_id).get_moex_shares(limit=normalized_limit)
            if items:
                normalized = [_normalize_instrument(item) for item in items]
                return normalized[:normalized_limit]
        except Exception as exc:
            logger.warning("Could not fetch MOEX shares from T-Invest; using static seed: %s", exc)
    return [_normalize_instrument(item) for item in POPULAR_MOEX_SHARES][:normalized_limit]


def find_static_instrument(figi: str) -> Optional[Dict[str, Any]]:
    normalized_figi = (figi or "").strip().upper()
    for item in POPULAR_MOEX_SHARES:
        if item["figi"].upper() == normalized_figi:
            return item
    return None


def _normalize_instrument(item: Dict[str, Any]) -> Dict[str, Any]:
    current_price = item.get("current_price")
    lot = _to_int(item.get("lot"), 1)
    return {
        "figi": (item.get("figi") or "").strip().upper(),
        "ticker": item.get("ticker"),
        "name": item.get("name"),
        "currency": (item.get("currency") or "RUB").upper(),
        "exchange": item.get("exchange") or "MOEX",
        "current_price": current_price,
        "lot": lot,
        "lot_price": lot_price(current_price, lot),
        "instrument_type": item.get("instrument_type") or "share",
    }


def get_instrument_by_figi(user_id: int, figi: str) -> Dict[str, Any]:
    normalized_figi = (figi or "").strip().upper()
    if not normalized_figi:
        raise ValueError("figi is required")

    static = find_static_instrument(normalized_figi) or {}
    broker_instrument: Dict[str, Any] = {}
    try:
        broker_instrument = TinkoffClient(user_id=user_id).get_instrument_by_figi(normalized_figi)
    except Exception as exc:
        logger.warning("Could not validate instrument %s through T-Invest; using fallback: %s", normalized_figi, exc)

    instrument = _normalize_instrument({**static, **broker_instrument, "figi": normalized_figi})
    instrument["current_price"] = get_current_price(user_id=user_id, figi=normalized_figi, fallback_price=None)
    instrument["lot_price"] = lot_price(instrument.get("current_price"), instrument.get("lot"))
    return instrument


def get_lot_size(user_id: Optional[int], figi: str) -> int:
    normalized_figi = (figi or "").strip().upper()
    static = find_static_instrument(normalized_figi) or {}
    if user_id:
        try:
            broker_instrument = TinkoffClient(user_id=user_id).get_instrument_by_figi(normalized_figi)
            return _to_int(broker_instrument.get("lot") or static.get("lot"), 1)
        except Exception as exc:
            logger.warning("Could not fetch lot size for %s through T-Invest; using fallback: %s", normalized_figi, exc)
    return _to_int(static.get("lot"), 1)


def get_current_price(user_id: int, figi: str, fallback_price: Optional[float] = 0.0) -> Optional[float]:
    normalized_figi = (figi or "").strip().upper()
    try:
        prices = TinkoffClient(user_id=user_id).get_current_prices([normalized_figi])
        for item in prices or []:
            if (item.get("figi") or "").upper() == normalized_figi:
                price = _to_float(item.get("price"), 0.0)
                return price if price > 0 else fallback_price
    except Exception as exc:
        logger.warning("Could not fetch current T-Invest price for %s: %s", normalized_figi, exc)
    return fallback_price


def get_trading_mode(user_id: Optional[int] = None) -> Dict[str, Any]:
    if user_id:
        try:
            return TinkoffClient(user_id=user_id).get_trading_mode()
        except Exception as exc:
            logger.warning("Could not read user-specific trading mode: %s", exc)
    return {
        "sandbox": bool(settings.USE_SANDBOX),
        "mode": "sandbox" if settings.USE_SANDBOX else "real",
        "auto_sell_worker_enabled": bool(settings.AUTO_SELL_WORKER_ENABLED),
        "auto_sell_poll_seconds": int(settings.AUTO_SELL_POLL_SECONDS),
        "auto_sell_dry_run": bool(settings.AUTO_SELL_DRY_RUN),
        "bulk_trade_worker_enabled": bool(settings.BULK_TRADE_WORKER_ENABLED),
        "bulk_trade_worker_poll_seconds": int(settings.BULK_TRADE_WORKER_POLL_SECONDS),
        "real_trading_enabled": bool(settings.AI_BOT_REAL_TRADING_ENABLED),
    }


def get_portfolio_position(user_id: int, figi: str, account_id: Optional[str] = None) -> PortfolioPosition:
    normalized_figi = (figi or "").strip().upper()
    try:
        raw = get_portfolio(user_id=user_id, account_id=account_id)
        if isinstance(raw, dict) and raw.get("status") == "error":
            logger.warning("Could not read portfolio for user_id=%s: %s", user_id, raw.get("message"))
            return PortfolioPosition(has_position=False)

        positions, summary = _extract_portfolio(raw)
        cash_balance = _to_float(summary.get("cash_balance"), 0.0)

        for position in positions:
            if not isinstance(position, dict):
                continue
            if (position.get("figi") or "").upper() != normalized_figi:
                continue
            quantity = _to_float(position.get("balance") or position.get("quantity"), 0.0)
            return PortfolioPosition(
                has_position=quantity > 0,
                quantity=quantity,
                average_buy_price=get_average_buy_price(user_id, normalized_figi, account_id=account_id) if quantity > 0 else 0.0,
                cash_balance=cash_balance,
            )

        return PortfolioPosition(has_position=False, cash_balance=cash_balance)
    except Exception as exc:
        logger.warning("Could not read portfolio for recommendation: %s", exc)
        return PortfolioPosition(has_position=False)


def get_portfolio_snapshot(user_id: int, figi: str, account_id: Optional[str] = None) -> Dict[str, float]:
    position = get_portfolio_position(user_id=user_id, figi=figi, account_id=account_id)
    return {
        "quantity": float(position.quantity),
        "cash_balance": float(position.cash_balance),
        "average_buy_price": float(position.average_buy_price),
    }
