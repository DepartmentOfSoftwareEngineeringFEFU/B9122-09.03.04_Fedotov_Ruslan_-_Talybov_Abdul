from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import backtest_result, ml_model, stock, training_session  # noqa: F401
from app.schemas.model import BotTradeConfirmRequest
from app.services import bot_trade_service


class FakeQuery:
    def __init__(self, forecast):
        self.forecast = forecast

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.forecast


class FakeDB:
    def __init__(self, forecast):
        self.forecast = forecast

    def query(self, _model):
        return FakeQuery(self.forecast)

    def add(self, _obj):
        pass

    def commit(self):
        pass

    def refresh(self, _obj):
        pass


def forecast(**overrides):
    defaults = {
        "id": 10,
        "user_id": 1,
        "figi": "BBG004730N88",
        "ticker": "SBER",
        "recommendation": "BUY_OPTIONAL",
        "horizon": "1h",
        "model_type": "adaptive",
        "model_type_effective": "ensemble",
        "hyperparam_mode": "auto",
        "model_params": {"source": "popular"},
        "metrics": {},
        "current_price": 100.0,
        "predicted_price": 103.0,
        "price_delta_percent": 3.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture(autouse=True)
def patch_market(monkeypatch):
    monkeypatch.setattr(bot_trade_service, "get_instrument_by_figi", lambda user_id, figi: {
        "figi": figi,
        "currency": "RUB",
        "instrument_type": "share",
    })
    monkeypatch.setattr(bot_trade_service, "get_current_price", lambda user_id, figi, fallback_price=None: 100.0)


def test_confirm_buy_rejects_quantity_above_cash(monkeypatch):
    executed = {"called": False}
    monkeypatch.setattr(bot_trade_service, "get_portfolio_snapshot", lambda user_id, figi, **_kwargs: {
        "quantity": 0,
        "cash_balance": 150.0,
        "average_buy_price": 0.0,
    })
    monkeypatch.setattr(bot_trade_service, "execute_order", lambda *args, **kwargs: executed.update(called=True))

    with pytest.raises(HTTPException) as exc:
        bot_trade_service.confirm_bot_trade(
            FakeDB(forecast()),
            user_id=1,
            request=BotTradeConfirmRequest(forecast_id=10, side="buy", quantity=2),
        )

    assert exc.value.status_code == 400
    assert "Not enough cash" in exc.value.detail
    assert executed["called"] is False


def test_confirm_buy_rejects_lot_amount_above_cash(monkeypatch):
    executed = {"called": False}
    monkeypatch.setattr(bot_trade_service, "get_instrument_by_figi", lambda user_id, figi: {
        "figi": figi,
        "currency": "RUB",
        "instrument_type": "share",
        "lot": 10,
    })
    monkeypatch.setattr(bot_trade_service, "get_portfolio_snapshot", lambda user_id, figi, **_kwargs: {
        "quantity": 0,
        "cash_balance": 1500.0,
        "average_buy_price": 0.0,
    })
    monkeypatch.setattr(bot_trade_service, "execute_order", lambda *args, **kwargs: executed.update(called=True))

    with pytest.raises(HTTPException) as exc:
        bot_trade_service.confirm_bot_trade(
            FakeDB(forecast()),
            user_id=1,
            request=BotTradeConfirmRequest(forecast_id=10, side="buy", quantity=20),
        )

    assert exc.value.status_code == 400
    assert "Not enough cash" in exc.value.detail
    assert executed["called"] is False


def test_confirm_sell_rejects_quantity_above_position(monkeypatch):
    executed = {"called": False}
    monkeypatch.setattr(bot_trade_service, "get_portfolio_snapshot", lambda user_id, figi, **_kwargs: {
        "quantity": 1,
        "cash_balance": 1000.0,
        "average_buy_price": 90.0,
    })
    monkeypatch.setattr(bot_trade_service, "execute_order", lambda *args, **kwargs: executed.update(called=True))

    with pytest.raises(HTTPException) as exc:
        bot_trade_service.confirm_bot_trade(
            FakeDB(forecast(recommendation="SELL")),
            user_id=1,
            request=BotTradeConfirmRequest(forecast_id=10, side="sell", quantity=2),
        )

    assert exc.value.status_code == 400
    assert "Not enough shares" in exc.value.detail
    assert executed["called"] is False


def test_confirm_sell_rejects_share_quantity_above_position_for_lotted_instrument(monkeypatch):
    executed = {"called": False}
    monkeypatch.setattr(bot_trade_service, "get_instrument_by_figi", lambda user_id, figi: {
        "figi": figi,
        "currency": "RUB",
        "instrument_type": "share",
        "lot": 10,
    })
    monkeypatch.setattr(bot_trade_service, "get_portfolio_snapshot", lambda user_id, figi, **_kwargs: {
        "quantity": 15,
        "cash_balance": 1000.0,
        "average_buy_price": 90.0,
    })
    monkeypatch.setattr(bot_trade_service, "execute_order", lambda *args, **kwargs: executed.update(called=True))

    with pytest.raises(HTTPException) as exc:
        bot_trade_service.confirm_bot_trade(
            FakeDB(forecast(recommendation="SELL")),
            user_id=1,
            request=BotTradeConfirmRequest(forecast_id=10, side="sell", quantity=20),
        )

    assert exc.value.status_code == 400
    assert "Not enough shares" in exc.value.detail
    assert executed["called"] is False


def test_confirm_sell_converts_requested_shares_to_broker_lots(monkeypatch):
    seen = {}
    monkeypatch.setattr(bot_trade_service, "get_instrument_by_figi", lambda user_id, figi: {
        "figi": figi,
        "currency": "RUB",
        "instrument_type": "share",
        "lot": 10,
    })
    monkeypatch.setattr(bot_trade_service, "get_portfolio_snapshot", lambda user_id, figi, **_kwargs: {
        "quantity": 2000,
        "cash_balance": 33.0,
        "average_buy_price": 128.8,
    })

    def fake_execute_order(figi, side, quantity, **kwargs):
        seen["figi"] = figi
        seen["side"] = side
        seen["quantity"] = quantity
        seen["account_id"] = kwargs.get("account_id")
        return {
            "status": "success",
            "order_id": 99,
            "broker_order_id": "broker-99",
            "price": 128.4,
            "qty": 1000,
            "amount": 128400.0,
        }

    monkeypatch.setattr(bot_trade_service, "execute_order", fake_execute_order)

    trade = bot_trade_service.confirm_bot_trade(
        FakeDB(forecast(recommendation="SELL", figi="BBG004731489", ticker="GMKN")),
        user_id=1,
        request=BotTradeConfirmRequest(forecast_id=10, side="sell", quantity=1000, account_id="acc-1"),
    )

    assert seen == {
        "figi": "BBG004731489",
        "side": "sell",
        "quantity": 100,
        "account_id": "acc-1",
    }
    assert trade.quantity == 1000
    assert trade.status == "closed"
    assert float(trade.amount) == 128400.0
    assert trade.raw_response["requested_shares"] == 1000
    assert trade.raw_response["requested_lots"] == 100


def test_confirm_rejects_share_quantity_not_multiple_of_lot(monkeypatch):
    executed = {"called": False}
    monkeypatch.setattr(bot_trade_service, "get_instrument_by_figi", lambda user_id, figi: {
        "figi": figi,
        "currency": "RUB",
        "instrument_type": "share",
        "lot": 10,
    })
    monkeypatch.setattr(bot_trade_service, "get_portfolio_snapshot", lambda user_id, figi, **_kwargs: {
        "quantity": 2000,
        "cash_balance": 100000.0,
        "average_buy_price": 128.8,
    })
    monkeypatch.setattr(bot_trade_service, "execute_order", lambda *args, **kwargs: executed.update(called=True))

    with pytest.raises(HTTPException) as exc:
        bot_trade_service.confirm_bot_trade(
            FakeDB(forecast(recommendation="SELL")),
            user_id=1,
            request=BotTradeConfirmRequest(forecast_id=10, side="sell", quantity=1001),
        )

    assert exc.value.status_code == 400
    assert "кратно размеру лота" in exc.value.detail
    assert executed["called"] is False


def test_confirm_trade_persists_and_uses_account_id(monkeypatch):
    seen = {}

    def fake_snapshot(user_id, figi, account_id=None):
        seen["snapshot_account_id"] = account_id
        return {
            "quantity": 0,
            "cash_balance": 1000.0,
            "average_buy_price": 0.0,
        }

    def fake_execute_order(figi, side, quantity, **kwargs):
        seen["order_account_id"] = kwargs.get("account_id")
        return {
            "status": "success",
            "order_id": 99,
            "broker_order_id": "broker-99",
            "price": 100.0,
            "qty": quantity,
            "amount": 100.0 * quantity,
        }

    monkeypatch.setattr(bot_trade_service, "get_portfolio_snapshot", fake_snapshot)
    monkeypatch.setattr(bot_trade_service, "execute_order", fake_execute_order)

    trade = bot_trade_service.confirm_bot_trade(
        FakeDB(forecast()),
        user_id=1,
        request=BotTradeConfirmRequest(forecast_id=10, side="buy", quantity=1, account_id="acc-1"),
    )

    assert seen["snapshot_account_id"] == "acc-1"
    assert seen["order_account_id"] == "acc-1"
    assert trade.account_id == "acc-1"
    assert trade.status == "executed"


def test_real_mode_ai_trading_is_blocked_without_explicit_flag(monkeypatch):
    monkeypatch.setattr(bot_trade_service.settings, "USE_SANDBOX", False)
    monkeypatch.setattr(bot_trade_service.settings, "AI_BOT_REAL_TRADING_ENABLED", False)

    with pytest.raises(HTTPException) as exc:
        bot_trade_service.confirm_bot_trade(
            FakeDB(forecast()),
            user_id=1,
            request=BotTradeConfirmRequest(forecast_id=10, side="buy", quantity=1),
        )

    assert exc.value.status_code == 403
    assert "disabled in real broker mode" in exc.value.detail
