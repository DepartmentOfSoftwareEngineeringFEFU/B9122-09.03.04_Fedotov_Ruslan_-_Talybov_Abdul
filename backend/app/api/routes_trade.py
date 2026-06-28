import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models.user import User
from app.services.trade_service import execute_order, get_average_buy_price, get_portfolio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trade", tags=["Trade"])


class ExecuteOrderRequest(BaseModel):
    figi: str = Field(min_length=1, max_length=32)
    side: str = Field(pattern="^(buy|sell)$")
    qty: int = Field(ge=1, le=1_000_000)
    account_id: Optional[str] = Field(default=None, max_length=128)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


@router.post("/execute")
def execute(order_request: ExecuteOrderRequest, current_user: User = Depends(get_current_user)):
    logger.debug("Execute order request user_id=%s payload=%s", current_user.id, order_request.model_dump())

    try:
        result = execute_order(
            order_request.figi,
            order_request.side,
            order_request.qty,
            user_id=current_user.id,
            source="manual",
            account_id=order_request.account_id,
            idempotency_key=order_request.idempotency_key,
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Trading error"))

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Order execution failed for user_id=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Internal Server Error")


def normalize_money(obj):
    if not obj:
        return 0.0
    units = obj.get("units", 0)
    nano = obj.get("nano", 0)
    try:
        return float(units) + float(nano) / 1_000_000_000
    except Exception as exc:
        logger.warning("Money normalization failed for %s: %s", obj, exc)
        return 0.0


def format_portfolio(raw, user_id: int):
    """Return a frontend-friendly portfolio from the local orders portfolio shape."""
    inner = raw.get("portfolio", raw)
    if isinstance(inner, dict) and "positions" in inner:
        return inner

    portfolio_data = inner.get("portfolio", [])
    summary = inner.get("summary", {})

    positions = []
    total_stocks_value = 0.0
    cash_balance = float(summary.get("cash_balance") or 0.0)
    total_profit = 0.0
    total_cost_basis = 0.0

    for item in portfolio_data:
        if not isinstance(item, dict):
            continue

        instrument_type = item.get("instrument_type")
        quantity = float(item.get("balance", 0.0) or 0.0)
        price = float(item.get("price", 0.0) or 0.0)
        value = float(item.get("value") or (price * quantity))
        figi = item.get("figi")

        if instrument_type == "currency" and item.get("currency") == "RUB":
            if not cash_balance:
                cash_balance += quantity
            continue

        if instrument_type != "share":
            continue

        broker_profit = float(item.get("expected_yield") or 0.0)
        explicit_average_price = float(item.get("average_price") or 0.0)
        explicit_cost_basis = float(item.get("cost_basis") or 0.0)
        local_average_price = get_average_buy_price(user_id, figi) if figi else 0.0
        broker_cost_basis = value - broker_profit

        if explicit_cost_basis > 0 and explicit_average_price > 0:
            cost_basis = explicit_cost_basis
            average_price = explicit_average_price
            profit = value - cost_basis
        elif broker_cost_basis > 0 and quantity > 0:
            cost_basis = broker_cost_basis
            average_price = cost_basis / quantity
            profit = broker_profit
        elif local_average_price > 0 and quantity > 0:
            average_price = local_average_price
            cost_basis = average_price * quantity
            profit = value - cost_basis
        else:
            average_price = price
            cost_basis = value
            profit = broker_profit

        expected_yield_percent = (profit / cost_basis) * 100 if cost_basis > 0 else 0.0
        total_stocks_value += value
        total_profit += profit
        total_cost_basis += cost_basis
        lot = int(item.get("lot") or 1)
        lot_price = float(item.get("lot_price") or price * lot)

        positions.append({
            "figi": figi,
            "ticker": item.get("ticker"),
            "instrument_type": instrument_type,
            "quantity": quantity,
            "price": round(price, 6),
            "unit_price": round(float(item.get("unit_price") or price), 6),
            "lot": lot,
            "lot_price": round(lot_price, 6),
            "value": round(value, 2),
            "average_price": round(average_price, 6),
            "cost_basis": round(cost_basis, 2),
            "expected_yield": round(profit, 2),
            "expected_yield_percent": round(expected_yield_percent, 2),
            "currency": item.get("currency", "RUB"),
            "price_status": item.get("price_status", "unknown"),
        })

    total_value = float(summary.get("totalAmountPortfolio") or (total_stocks_value + cash_balance))
    total_profit = float(summary.get("total_profit") if summary.get("total_profit") is not None else total_profit)
    total_profit_percent = float(
        summary.get("total_profit_percent")
        if summary.get("total_profit_percent") is not None
        else ((total_profit / total_cost_basis) * 100 if total_cost_basis > 0 else 0.0)
    )

    return {
        "total_value": round(total_value, 2),
        "cash_balance": round(cash_balance, 2),
        "total_stocks_value": round(total_stocks_value, 2),
        "total_profit": round(total_profit, 2),
        "total_profit_percent": round(total_profit_percent, 2),
        "positions_count": len(positions),
        "positions": positions,
    }


@router.get("/portfolio")
def portfolio(
    account_id: Optional[str] = Query(default=None, max_length=128),
    current_user: User = Depends(get_current_user),
):
    logger.debug("Portfolio request user_id=%s account_id=%s", current_user.id, account_id)
    try:
        raw_result = get_portfolio(user_id=current_user.id, account_id=account_id)
        logger.debug("Raw get_portfolio response: %s", json.dumps(raw_result, ensure_ascii=False, indent=2))

        if raw_result.get("status") == "error":
            raise HTTPException(status_code=400, detail=raw_result.get("message", "Portfolio error"))

        formatted = format_portfolio(raw_result, user_id=current_user.id)
        return formatted

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Portfolio request failed for user_id=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Internal Server Error")
