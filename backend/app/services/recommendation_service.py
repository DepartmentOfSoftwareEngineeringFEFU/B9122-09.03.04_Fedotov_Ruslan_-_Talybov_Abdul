from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PortfolioPosition:
    has_position: bool
    quantity: float = 0.0
    average_buy_price: float = 0.0
    cash_balance: float = 0.0


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_trade_recommendation(
    *,
    price_delta_percent: float,
    flat_threshold_percent: float,
    position: PortfolioPosition,
    current_price: float,
    predicted_price: float,
    lot: int = 1,
) -> Dict[str, Any]:
    threshold = max(_to_float(flat_threshold_percent, 1.0), 0.01)
    delta_percent = _to_float(price_delta_percent, 0.0)
    quantity = max(int(position.quantity), 0)
    lot_size = max(int(lot or 1), 1)
    lot_price = current_price * lot_size if current_price > 0 else 0.0
    predicted_lot_price = predicted_price * lot_size if predicted_price > 0 else 0.0
    max_affordable_lots = int(position.cash_balance // lot_price) if lot_price > 0 else 0
    max_affordable_quantity = max_affordable_lots * lot_size
    expected_profit_from_avg = 0.0
    expected_profit_from_avg_percent = 0.0

    if position.has_position and position.average_buy_price > 0:
        expected_profit_from_avg = predicted_price - position.average_buy_price
        expected_profit_from_avg_percent = expected_profit_from_avg / position.average_buy_price * 100

    def payload(
        action: str,
        reason_code: str,
        message: str,
        recommended_side: Optional[str] = None,
        recommended_quantity: int = 0,
        requires_confirmation: bool = False,
        allow_auto_sell: bool = False,
    ) -> Dict[str, Any]:
        safe_quantity = max(int(recommended_quantity or 0), 0)
        return {
            "action": action,
            "reason_code": reason_code,
            "message": message,
            "has_position": position.has_position,
            "quantity": float(position.quantity),
            "average_buy_price": float(position.average_buy_price),
            "cash_balance": float(position.cash_balance),
            "expected_profit_from_avg": float(expected_profit_from_avg),
            "expected_profit_from_avg_percent": float(expected_profit_from_avg_percent),
            "recommended_side": recommended_side,
            "recommended_quantity": safe_quantity,
            "lot": lot_size,
            "lot_price": float(lot_price),
            "predicted_lot_price": float(predicted_lot_price),
            "estimated_trade_amount": float(current_price * safe_quantity) if safe_quantity else 0.0,
            "max_affordable_quantity": max_affordable_quantity,
            "requires_confirmation": requires_confirmation,
            "allow_auto_sell": allow_auto_sell,
        }

    if delta_percent <= -threshold:
        if position.has_position:
            return payload(
                action="SELL",
                reason_code="predicted_drop_existing_position",
                message="Модель прогнозирует падение. Рекомендуется продать позицию после явного подтверждения пользователя.",
                recommended_side="sell",
                recommended_quantity=quantity,
                requires_confirmation=True,
                allow_auto_sell=False,
            )
        return payload(
            action="DO_NOT_BUY",
            reason_code="predicted_drop_without_position",
            message="Модель прогнозирует падение. Покупать сейчас не рекомендуется.",
        )

    if delta_percent >= threshold:
        if position.has_position:
            if position.average_buy_price > 0 and expected_profit_from_avg_percent >= threshold:
                return payload(
                    action="HOLD_AND_OPTIONAL_BUY",
                    reason_code="predicted_growth_existing_position",
                    message=(
                        "Модель прогнозирует рост. Акцию рекомендуется держать. "
                        "Можно докупить после подтверждения; автопродажу через выбранный горизонт можно только запланировать."
                    ),
                    recommended_side="buy",
                    recommended_quantity=lot_size if max_affordable_quantity >= lot_size else 0,
                    requires_confirmation=True,
                    allow_auto_sell=True,
                )
            return payload(
                action="HOLD",
                reason_code="predicted_growth_but_avg_profit_too_small",
                message="Модель прогнозирует рост, но запас относительно средней цены покупки недостаточный. Рекомендация: держать позицию.",
            )
        return payload(
            action="BUY_OPTIONAL",
            reason_code="predicted_growth_without_position",
            message="Модель прогнозирует рост. Акции нет в портфеле; можно купить после подтверждения пользователя.",
            recommended_side="buy",
            recommended_quantity=lot_size if max_affordable_quantity >= lot_size else 0,
            requires_confirmation=True,
            allow_auto_sell=False,
        )

    if position.has_position:
        return payload(
            action="HOLD",
            reason_code="flat_existing_position",
            message="Существенного изменения цены не ожидается. Рекомендация: держать позицию и повторить прогноз позже.",
        )
    return payload(
        action="WAIT",
        reason_code="flat_without_position",
        message="Существенного движения не ожидается. Лучше подождать и повторить прогноз позже.",
    )
