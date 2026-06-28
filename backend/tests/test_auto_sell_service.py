from types import SimpleNamespace

import pytest

from app.models import backtest_result, bot_trade, ml_model, stock, training_session  # noqa: F401
from app.services import auto_sell_service


def test_auto_sell_converts_scheduled_share_quantity_to_lots(monkeypatch):
    monkeypatch.setattr(auto_sell_service, "get_lot_size", lambda user_id, figi: 10)

    trade = SimpleNamespace(user_id=1, figi="BBG004731489", quantity=1000)

    assert auto_sell_service._order_lots_for_trade(trade) == 100


def test_auto_sell_rejects_quantity_not_multiple_of_lot(monkeypatch):
    monkeypatch.setattr(auto_sell_service, "get_lot_size", lambda user_id, figi: 10)

    trade = SimpleNamespace(user_id=1, figi="BBG004731489", quantity=1001)

    with pytest.raises(ValueError) as exc:
        auto_sell_service._order_lots_for_trade(trade)

    assert "кратно размеру лота" in str(exc.value)
