import json
import logging
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.tinkoff_client import TinkoffClient
from app.models.order import Order
from app.models.trade import Trade

logger = logging.getLogger(__name__)


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _round_money(value: float) -> float:
    return round(float(value or 0.0), 6)


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool, list, tuple, dict)):
        raw = value
    elif hasattr(value, "model_dump"):
        raw = value.model_dump()
    elif hasattr(value, "dict"):
        raw = value.dict()
    elif hasattr(value, "__dict__"):
        raw = value.__dict__
    else:
        raw = str(value)
    try:
        return json.loads(json.dumps(raw, default=str, ensure_ascii=False))
    except TypeError:
        return str(value)


def _money_to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    units = getattr(value, "units", None)
    nano = getattr(value, "nano", None)
    if isinstance(value, dict):
        units = value.get("units")
        nano = value.get("nano")
    if units is None and nano is None:
        return _to_float(value, default)
    return _to_float(units, 0.0) + _to_float(nano, 0.0) / 1_000_000_000


def _response_status(response: Any) -> str:
    status = getattr(response, "execution_report_status", None)
    if status is not None:
        return getattr(status, "name", str(status))
    if isinstance(response, dict):
        return str(response.get("status") or "UNKNOWN")
    return "UNKNOWN"


def _response_order_id(response: Any) -> Optional[str]:
    for attr in ("order_id", "id"):
        value = getattr(response, attr, None)
        if value is not None:
            return str(value)
    if isinstance(response, dict):
        value = response.get("broker_order_id") or response.get("order_id") or response.get("id")
        if value is not None:
            return str(value)
    return None


def _field(response: Any, name: str, default: Any = None) -> Any:
    if response is None:
        return default
    if isinstance(response, dict):
        return response.get(name, default)
    return getattr(response, name, default)


def _money_field(response: Any, name: str) -> float:
    return _money_to_float(_field(response, name), 0.0)


def _number_field(response: Any, name: str, default: int = 0) -> int:
    return _to_int(_field(response, name), default)


def _lot_size(user_id: int | None, figi: str, *, prefer_broker: bool = True) -> int:
    """Return broker lot size for an instrument.

    T-Invest order requests use lots, but portfolio positions and business
    accounting in this project are shown and stored in instruments/shares. The
    import is intentionally local to avoid a module-level circular dependency
    with instrument_service.
    """
    try:
        from app.services.instrument_service import find_static_instrument, get_lot_size

        if not prefer_broker:
            static = find_static_instrument(figi) or {}
            return max(_to_int(static.get("lot"), 1), 1)

        return max(_to_int(get_lot_size(user_id=user_id, figi=figi), 1), 1)
    except Exception as exc:  # noqa: BLE001 - fallback must not break order accounting
        logger.warning("Could not resolve lot size for figi=%s user_id=%s: %s", figi, user_id, exc)
        return 1


def _looks_like_total_price(value: float, quantity: int, reference_price: float = 0.0) -> bool:
    if value <= 0 or quantity <= 1:
        return False
    per_unit = value / quantity
    if reference_price > 0:
        return abs(per_unit - reference_price) < abs(value - reference_price)
    return False


def _normalize_unit_price(value: float, quantity: int, reference_price: float = 0.0) -> float:
    if _looks_like_total_price(value, quantity, reference_price):
        return value / quantity
    return value


def _response_price(response: Any, quantity: int = 0, reference_price: float = 0.0) -> float:
    """Legacy unit-price extraction for old tests/fallbacks.

    T-Invest OrderState has multiple price fields with different semantics:
    `initial_security_price` is price for one instrument, while
    `executed_order_price` / `initial_order_price` are order totals. New order
    saving code uses `_execution_from_broker_response` below to avoid losing the
    lot multiplier; this helper remains for historical normalization paths.
    """
    for key in ("average_position_price", "initial_security_price", "price"):
        price = _money_field(response, key) if not isinstance(response, dict) else _to_float(response.get(key), 0.0)
        if price > 0:
            return price
    for key in ("executed_order_price", "total_order_amount", "initial_order_price"):
        price = _money_field(response, key) if not isinstance(response, dict) else _to_float(response.get(key), 0.0)
        if price > 0:
            return _normalize_unit_price(price, quantity, reference_price)
    return 0.0


def _execution_from_broker_response(
    response: Any,
    *,
    requested_lots: int,
    fallback_unit_price: float,
    fallback_lot: int,
) -> Dict[str, float]:
    """Extract canonical execution values from T-Invest order response/state.

    Per T-Invest API docs, `initial_security_price` is the price of one
    instrument; to get a lot price it must be multiplied by instrument `lot`.
    `executed_order_price` / `initial_order_price` in OrderState are order
    totals (average price * lots). Prefer those totals when present because they
    are the broker's authoritative amount for the executed order.
    """
    lots = _number_field(response, "lots_executed", 0) or _number_field(response, "lots_requested", 0) or requested_lots
    lots = max(_to_int(lots, requested_lots), 1)

    unit_price = (
        _money_field(response, "initial_security_price")
        or _money_field(response, "average_position_price")
        or _money_field(response, "price")
        or _to_float(fallback_unit_price, 0.0)
    )

    total_amount = (
        _money_field(response, "executed_order_price")
        or _money_field(response, "initial_order_price")
        or _money_field(response, "total_order_amount")
    )

    lot = max(_to_int(fallback_lot, 1), 1)
    lot_price = unit_price * lot if unit_price > 0 else 0.0

    if total_amount > 0 and lots > 0:
        broker_lot_price = total_amount / lots
        # Trust the order total for accounting. If unit price is available, keep
        # it for diagnostics; if lot metadata was unavailable/wrong, infer the
        # effective lot price from the total instead of undercounting the deal.
        lot_price = broker_lot_price
        if unit_price > 0:
            inferred_lot = round(broker_lot_price / unit_price)
            if inferred_lot > 0:
                lot = int(inferred_lot)
        else:
            unit_price = broker_lot_price / lot if lot > 0 else broker_lot_price
    elif lot_price > 0:
        total_amount = lot_price * lots

    return {
        "unit_price": float(unit_price or 0.0),
        "lot": int(lot),
        "lots": int(lots),
        "lot_price": float(lot_price or 0.0),
        "amount": float(total_amount or 0.0),
    }


def _latest_market_price(client: TinkoffClient, figi: str) -> float:
    try:
        prices = client.get_current_prices([figi])
        for item in prices:
            if (item.get("figi") or "").upper() == figi.upper():
                return _to_float(item.get("price"), 0.0)
    except Exception as exc:  # noqa: BLE001 - price fallback should not hide executed order
        logger.warning("Could not fetch fallback execution price figi=%s user_id=%s: %s", figi, client.user_id, exc)
    return 0.0


def _order_price(order: Order, reference_price: float = 0.0) -> float:
    price = _to_float(order.price, 0.0)
    if price > 0:
        qty = _to_int(order.qty, 0)
        normalized = _normalize_unit_price(price, qty, reference_price)
        if normalized != price:
            logger.warning(
                "Normalizing historical order price as total amount user_id=%s figi=%s order_id=%s raw_price=%s qty=%s unit_price=%s",
                getattr(order, "user_id", None),
                order.figi,
                getattr(order, "id", None),
                price,
                qty,
                normalized,
            )
        return normalized
    qty = _to_int(order.qty, 0)
    if qty > 0:
        return _to_float(order.amount, 0.0) / qty
    return 0.0


def _apply_weighted_state(state: Dict[str, float], side: str, qty: int, price: float) -> Dict[str, float]:
    quantity = _to_int(state.get("quantity"), 0)
    cost_basis = _to_float(state.get("cost_basis"), 0.0)
    realized_pnl_total = _to_float(state.get("realized_pnl_total"), 0.0)
    realized_pnl = 0.0
    realized_pnl_percent = 0.0

    if qty <= 0 or price <= 0:
        return {
            **state,
            "metrics_status": "invalid_price_or_quantity",
            "realized_pnl": realized_pnl,
            "realized_pnl_percent": realized_pnl_percent,
        }

    if side == "buy":
        quantity += qty
        cost_basis += price * qty
    elif side == "sell":
        average_price = cost_basis / quantity if quantity > 0 else 0.0
        sell_qty = min(qty, quantity)
        if sell_qty > 0 and average_price > 0:
            realized_pnl = (price - average_price) * sell_qty
            base = average_price * sell_qty
            realized_pnl_percent = (realized_pnl / base) * 100 if base > 0 else 0.0
            realized_pnl_total += realized_pnl
            cost_basis -= average_price * sell_qty
            quantity -= sell_qty
        if quantity <= 0:
            quantity = 0
            cost_basis = 0.0
    else:
        return {
            **state,
            "metrics_status": "unknown_side",
            "realized_pnl": realized_pnl,
            "realized_pnl_percent": realized_pnl_percent,
        }

    average_price_after = cost_basis / quantity if quantity > 0 else 0.0
    return {
        "quantity": quantity,
        "cost_basis": max(cost_basis, 0.0),
        "average_price": average_price_after,
        "realized_pnl": realized_pnl,
        "realized_pnl_percent": realized_pnl_percent,
        "realized_pnl_total": realized_pnl_total,
        "last_price": price,
        "metrics_status": "calculated",
    }


def _position_state_from_orders(orders: Iterable[Order], reference_price: float = 0.0) -> Dict[str, float]:
    state: Dict[str, float] = {
        "quantity": 0,
        "cost_basis": 0.0,
        "average_price": 0.0,
        "realized_pnl_total": 0.0,
        "last_price": 0.0,
        "metrics_status": "empty",
    }
    for order in orders:
        side = (order.side or "").lower()
        if side not in {"buy", "sell"}:
            continue
        state = _apply_weighted_state(state, side, _to_int(order.qty, 0), _order_price(order, reference_price))
    return state


def _orders_for_position(db: Session, user_id: int, figi: str, account_id: str | None = None) -> List[Order]:
    normalized_account_id = (account_id or "").strip() or None
    query = db.query(Order).filter(Order.user_id == user_id, func.upper(Order.figi) == figi.upper())
    orders = query.order_by(Order.created_at.asc(), Order.id.asc()).all()
    orders = [order for order in orders if (order.figi or "").upper() == figi.upper()]
    if not normalized_account_id:
        return orders
    return [order for order in orders if (order.account_id or "").strip() == normalized_account_id]


def _order_response(order: Order, idempotent: bool = False) -> Dict[str, Any]:
    return {
        "status": order.status,
        "figi": order.figi,
        "side": order.side,
        "qty": order.qty,
        "price": order.price,
        "amount": order.amount,
        "average_price_after": order.average_price_after,
        "position_qty_after": order.position_qty_after,
        "cost_basis_after": order.cost_basis_after,
        "realized_pnl": order.realized_pnl,
        "realized_pnl_percent": order.realized_pnl_percent,
        "order_id": order.id,
        "broker_order_id": order.broker_order_id,
        "account_id": order.account_id,
        "idempotency_key": order.idempotency_key,
        "idempotent": idempotent,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def _try_named_lock(db: Session, lock_name: str, timeout_seconds: int = 5) -> bool:
    try:
        value = db.execute(text("SELECT GET_LOCK(:name, :timeout)"), {"name": lock_name, "timeout": timeout_seconds}).scalar()
        return value == 1
    except Exception as exc:  # noqa: BLE001 - tests/dev DBs may not support MySQL locks
        logger.debug("Named DB lock is unavailable, continuing without it: %s", exc)
        return True


def _release_named_lock(db: Session, lock_name: str) -> None:
    try:
        db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
    except Exception as exc:  # noqa: BLE001
        logger.debug("Named DB lock release skipped: %s", exc)


def execute_order(
    figi: str,
    side: str,
    qty: int,
    user_id: int,
    source: str = "manual",
    account_id: str | None = None,
    idempotency_key: str | None = None,
):
    normalized_figi = (figi or "").strip().upper()
    normalized_side = (side or "").strip().lower()
    quantity = _to_int(qty, 0)
    idempotency_key = (idempotency_key or "").strip() or None
    logger.info(
        "Order execution started user_id=%s figi=%s side=%s qty=%s source=%s idempotency=%s",
        user_id,
        normalized_figi,
        normalized_side,
        quantity,
        source,
        bool(idempotency_key),
    )

    if quantity <= 0:
        return {"status": "error", "message": "Quantity must be positive"}
    if normalized_side not in {"buy", "sell"}:
        return {"status": "error", "message": "Side must be buy or sell"}

    lock_db = SessionLocal() if idempotency_key else None
    lock_name = f"trade-order:{user_id}:{idempotency_key}" if idempotency_key else None
    try:
        if idempotency_key and lock_db is not None:
            existing = lock_db.query(Order).filter(
                Order.user_id == user_id,
                Order.idempotency_key == idempotency_key,
            ).first()
            if existing:
                return _order_response(existing, idempotent=True)
            if not _try_named_lock(lock_db, lock_name):
                return {"status": "error", "message": "Duplicate order is already being processed"}

        client = TinkoffClient(user_id=user_id)
        target_account_id = client.resolve_account_id(account_id)
        response = client.place_order(normalized_figi, quantity, normalized_side, account_id=target_account_id)
        status_value = _response_status(response)
        broker_order_id = _response_order_id(response)
        reference_price = _latest_market_price(client, normalized_figi)
        order_state = None
        if broker_order_id:
            try:
                order_state = client.get_order_state(broker_order_id, account_id=target_account_id)
                logger.debug(
                    "Broker order state fetched user_id=%s figi=%s broker_order_id=%s",
                    user_id,
                    normalized_figi,
                    broker_order_id,
                )
            except Exception as exc:  # noqa: BLE001 - post-order response remains usable
                logger.warning(
                    "Could not fetch broker order state user_id=%s figi=%s broker_order_id=%s: %s",
                    user_id,
                    normalized_figi,
                    broker_order_id,
                    exc,
                )

        lot = _lot_size(user_id, normalized_figi)
        broker_source = order_state if order_state is not None else response
        execution = _execution_from_broker_response(
            broker_source,
            requested_lots=quantity,
            fallback_unit_price=reference_price,
            fallback_lot=lot,
        )
        price = execution["unit_price"]
        lot = int(execution["lot"] or lot)
        executed_lots = max(_to_int(execution.get("lots"), quantity), 1)
        executed_quantity = executed_lots * max(lot, 1)
        lot_price_value = execution["lot_price"]
        amount = execution["amount"]
        if amount <= 0 and price > 0 and executed_quantity > 0:
            amount = price * executed_quantity
        if lot_price_value <= 0:
            logger.warning(
                "Executed order has no lot price user_id=%s figi=%s side=%s raw_execution=%s",
                user_id,
                normalized_figi,
                normalized_side,
                execution,
            )
        raw_response = {
            "post_order_response": _safe_json(response),
            "order_state": _safe_json(order_state),
            "execution": execution,
        }

        db = lock_db or SessionLocal()
        close_db = lock_db is None
        try:
            if idempotency_key:
                existing = db.query(Order).filter(
                    Order.user_id == user_id,
                    Order.idempotency_key == idempotency_key,
                ).first()
                if existing:
                    return _order_response(existing, idempotent=True)

            previous_orders = _orders_for_position(db, user_id, normalized_figi, account_id=target_account_id)
            previous_state = _position_state_from_orders(previous_orders, reference_price=reference_price)
            new_state = _apply_weighted_state(previous_state, normalized_side, executed_quantity, price)

            order = Order(
                user_id=user_id,
                figi=normalized_figi,
                side=normalized_side,
                qty=executed_quantity,
                price=_round_money(price),
                amount=_round_money(amount),
                average_price_after=_round_money(new_state.get("average_price", 0.0)),
                position_qty_after=_to_int(new_state.get("quantity"), 0),
                cost_basis_after=_round_money(new_state.get("cost_basis", 0.0)),
                realized_pnl=_round_money(new_state.get("realized_pnl", 0.0)),
                realized_pnl_percent=round(_to_float(new_state.get("realized_pnl_percent"), 0.0), 4),
                status=status_value,
                broker_order_id=broker_order_id,
                account_id=target_account_id,
                source=source,
                idempotency_key=idempotency_key,
                raw_response=raw_response,
                metrics_status=str(new_state.get("metrics_status") or "calculated"),
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            logger.info(
                "Order saved user_id=%s order_id=%s broker_order_id=%s figi=%s side=%s lots=%s shares=%s price=%s",
                user_id,
                order.id,
                broker_order_id,
                normalized_figi,
                normalized_side,
                quantity,
                executed_quantity,
                order.price,
            )
            return _order_response(order)
        except Exception as db_error:  # noqa: BLE001
            db.rollback()
            logger.exception("Order database save failed user_id=%s figi=%s: %s", user_id, normalized_figi, db_error)
            return {"status": "error", "message": "Database error while saving order"}
        finally:
            if close_db:
                db.close()

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Order execution failed user_id=%s figi=%s side=%s qty=%s source=%s: %s",
            user_id,
            normalized_figi,
            normalized_side,
            quantity,
            source,
            exc,
        )
        return {"status": "error", "message": str(exc)}
    finally:
        if idempotency_key and lock_db is not None:
            if lock_name:
                _release_named_lock(lock_db, lock_name)
            lock_db.close()

def _current_prices(user_id: int, figis: List[str]) -> Dict[str, float]:
    if not figis:
        return {}
    try:
        prices = TinkoffClient(user_id=user_id).get_current_prices(figis)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch current prices for local portfolio user_id=%s: %s", user_id, exc)
        return {}
    return {
        (item.get("figi") or "").upper(): _to_float(item.get("price"), 0.0)
        for item in prices
        if item.get("figi") and _to_float(item.get("price"), 0.0) > 0
    }


def _account_balance(user_id: int, account_id: str | None = None) -> Dict[str, Any]:
    try:
        return TinkoffClient(user_id=user_id).get_account_balance(account_id=account_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch broker balance for local portfolio user_id=%s: %s", user_id, exc)
        return {"total_amount": 0.0, "available_amount": 0.0}


def _extract_portfolio_parts(raw: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not isinstance(raw, dict):
        return [], {}

    inner = raw.get("portfolio", raw)
    summary = raw.get("summary", {})
    if isinstance(inner, dict):
        summary = inner.get("summary", summary)
        positions = inner.get("portfolio", [])
    elif isinstance(inner, list):
        positions = inner
    else:
        positions = []

    return [item for item in positions if isinstance(item, dict)], summary if isinstance(summary, dict) else {}


def _broker_portfolio(user_id: int, account_id: str | None = None) -> tuple[List[Dict[str, Any]], Dict[str, Any], bool]:
    try:
        raw = TinkoffClient(user_id=user_id).get_portfolio(account_id=account_id)
        positions, summary = _extract_portfolio_parts(raw)
        return positions, summary, True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch broker portfolio for user_id=%s account_id=%s: %s", user_id, account_id, exc)
        return [], {}, False


def _share_positions_by_figi(positions: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for position in positions:
        figi = (position.get("figi") or "").strip().upper()
        if not figi:
            continue
        if (position.get("instrument_type") or "").lower() != "share":
            continue
        quantity = _to_float(position.get("balance") or position.get("quantity"), 0.0)
        if quantity <= 0:
            continue
        result[figi] = position
    return result


def _orders_in_account_scope(
    orders: Iterable[Order],
    account_id: str | None,
) -> List[Order]:
    normalized_account_id = (account_id or "").strip() or None
    ordered = list(orders)
    if not normalized_account_id:
        return ordered
    return [order for order in ordered if (order.account_id or "").strip() == normalized_account_id]


def get_portfolio(user_id: int, account_id: str | None = None):
    normalized_account_id = (account_id or "").strip() or None
    logger.info("Building portfolio user_id=%s account_id=%s", user_id, normalized_account_id)
    db = SessionLocal()
    try:
        query = db.query(Order).filter(Order.user_id == user_id)
        all_orders = query.order_by(Order.created_at.asc(), Order.id.asc()).all()
        broker_positions, broker_summary, broker_available = _broker_portfolio(user_id, account_id=normalized_account_id)
        if normalized_account_id and not broker_available:
            return {"status": "error", "message": "Broker portfolio is unavailable for selected account"}

        broker_by_figi = _share_positions_by_figi(broker_positions)
        orders = _orders_in_account_scope(all_orders, normalized_account_id)
        all_figis = sorted(
            {(order.figi or "").upper() for order in orders if order.figi}
            | set(broker_by_figi.keys())
        )
        prices = _current_prices(user_id, all_figis)
        states: Dict[str, Dict[str, float]] = {}
        for order in orders:
            figi = (order.figi or "").upper()
            side = (order.side or "").lower()
            if not figi or side not in {"buy", "sell"}:
                continue
            states.setdefault(figi, {
                "quantity": 0,
                "cost_basis": 0.0,
                "average_price": 0.0,
                "realized_pnl_total": 0.0,
                "last_price": 0.0,
                "metrics_status": "empty",
            })
            states[figi] = _apply_weighted_state(
                states[figi],
                side,
                _to_int(order.qty, 0),
                _order_price(order, prices.get(figi, 0.0)),
            )

        local_open_figis = {figi for figi, state in states.items() if _to_float(state.get("quantity"), 0.0) > 0}
        open_figis = sorted(set(broker_by_figi.keys()) if normalized_account_id else (local_open_figis | set(broker_by_figi.keys())))

        positions = []
        total_stocks_value = 0.0
        total_profit = 0.0
        total_cost_basis = 0.0

        for figi in open_figis:
            state = states.get(figi, {
                "quantity": 0,
                "cost_basis": 0.0,
                "average_price": 0.0,
                "last_price": 0.0,
            })
            broker_position = broker_by_figi.get(figi)
            local_quantity = _to_float(state.get("quantity"), 0.0)
            broker_quantity = _to_float(
                (broker_position or {}).get("balance") or (broker_position or {}).get("quantity"),
                0.0,
            )
            quantity = broker_quantity if broker_quantity > 0 else local_quantity
            if quantity <= 0:
                continue

            local_cost_basis = _to_float(state.get("cost_basis"), 0.0)
            local_average_price = _to_float(state.get("average_price"), 0.0)
            fallback_price = _to_float(state.get("last_price"), 0.0)
            broker_price = _to_float((broker_position or {}).get("price"), 0.0)
            live_price = prices.get(figi, 0.0)
            if broker_price > 0:
                current_price = broker_price
                price_status = "broker"
            elif live_price > 0:
                current_price = live_price
                price_status = "live"
            elif fallback_price > 0:
                current_price = fallback_price
                price_status = "fallback_last_order_price"
                logger.warning("Using last order price for portfolio figi=%s user_id=%s", figi, user_id)
            else:
                current_price = 0.0
                price_status = "missing"
                logger.warning("No current or fallback price for portfolio figi=%s user_id=%s", figi, user_id)

            lot = _lot_size(user_id, figi, prefer_broker=False)
            current_lot_price = current_price * lot
            value = quantity * current_price
            broker_value = _to_float((broker_position or {}).get("value"), 0.0)
            if broker_value > 0 and broker_quantity > 0:
                value = broker_value

            broker_profit = _to_float((broker_position or {}).get("expected_yield"), 0.0)
            explicit_average_price = _to_float((broker_position or {}).get("average_price"), 0.0)
            explicit_cost_basis = _to_float((broker_position or {}).get("cost_basis"), 0.0)
            broker_cost_basis = value - broker_profit

            if local_cost_basis > 0 and local_quantity > 0:
                average_price = local_average_price or (local_cost_basis / local_quantity)
                cost_basis = average_price * quantity
                profit = value - cost_basis
            elif explicit_cost_basis > 0 and explicit_average_price > 0:
                cost_basis = explicit_cost_basis
                average_price = explicit_average_price
                profit = value - cost_basis
            elif broker_cost_basis > 0 and quantity > 0:
                cost_basis = broker_cost_basis
                average_price = cost_basis / quantity
                profit = broker_profit
            else:
                average_price = current_price
                cost_basis = value
                profit = 0.0

            expected_yield_percent = (profit / cost_basis) * 100 if cost_basis > 0 else 0.0

            total_stocks_value += value
            total_profit += profit
            total_cost_basis += cost_basis

            positions.append({
                "figi": figi,
                "ticker": (broker_position or {}).get("ticker") or figi,
                "instrument_type": "share",
                "balance": quantity,
                "quantity": quantity,
                "price": _round_money(current_price),
                "unit_price": _round_money(current_price),
                "lot": lot,
                "lot_price": _round_money(current_lot_price),
                "value": round(value, 2),
                "average_price": _round_money(average_price),
                "cost_basis": round(cost_basis, 2),
                "expected_yield": round(profit, 2),
                "expected_yield_percent": round(expected_yield_percent, 2),
                "currency": "RUB",
                "price_status": price_status,
            })

        broker_balance = _account_balance(user_id, account_id=normalized_account_id)
        broker_total_value = _to_float(broker_balance.get("total_amount"), 0.0)
        broker_cash = _to_float(broker_balance.get("available_amount"), 0.0)
        if broker_total_value <= 0:
            broker_total_value = _to_float(broker_summary.get("totalAmountPortfolio"), 0.0)
        if broker_cash <= 0:
            broker_cash = _to_float(broker_summary.get("cash_balance"), 0.0)
        if broker_total_value > 0:
            cash_balance = max(broker_cash, broker_total_value - total_stocks_value, 0.0)
            total_value = broker_total_value
        else:
            cash_balance = broker_cash
            total_value = total_stocks_value + cash_balance
        total_profit_percent = (total_profit / total_cost_basis) * 100 if total_cost_basis > 0 else 0.0

        logger.info(
            "Portfolio built user_id=%s positions=%s total_value=%s total_profit=%s",
            user_id,
            len(positions),
            round(total_value, 2),
            round(total_profit, 2),
        )
        return {
            "status": "success",
            "portfolio": {
                "summary": {
                    "totalAmountPortfolio": round(total_value, 2),
                    "cash_balance": round(cash_balance, 2),
                    "total_stocks_value": round(total_stocks_value, 2),
                    "total_profit": round(total_profit, 2),
                    "total_profit_percent": round(total_profit_percent, 2),
                    "account_id": normalized_account_id,
                    "source": "broker_and_local_orders" if broker_available else "local_orders",
                },
                "portfolio": positions,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Portfolio build failed user_id=%s: %s", user_id, exc)
        return {"status": "error", "message": str(exc)}
    finally:
        db.close()


def save_trade(user_id, figi, side, qty, price):
    """Legacy compatibility helper. New portfolio accounting uses orders."""
    db = SessionLocal()
    try:
        amount = qty * float(price)
        trade = Trade(
            user_id=user_id,
            figi=figi,
            side=side,
            quantity=qty,
            price=price,
            amount=amount,
            status="completed",
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        logger.info("Legacy trade saved user_id=%s figi=%s side=%s qty=%s", user_id, figi, side, qty)
        return trade
    except Exception:
        db.rollback()
        logger.exception("Legacy trade save failed user_id=%s figi=%s", user_id, figi)
        raise
    finally:
        db.close()


def get_average_buy_price(user_id: int, figi: str, account_id: str | None = None) -> float:
    normalized_figi = (figi or "").strip().upper()
    db = SessionLocal()
    try:
        state = _position_state_from_orders(_orders_for_position(db, user_id, normalized_figi, account_id=account_id))
        return _round_money(state.get("average_price", 0.0))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Average buy price calculation failed user_id=%s figi=%s: %s", user_id, normalized_figi, exc)
        return 0.0
    finally:
        db.close()
