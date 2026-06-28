from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api import routes_analytics, routes_auth, routes_trade
from app.core import tinkoff_client
from app.core.crypto import ENCRYPTED_PREFIX, mask_secret
from app.schemas.auth import TinkoffTokenUpdate, UserResponse


class FakeDb:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def add(self, _obj):
        pass

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        pass

    def rollback(self):
        self.rolled_back = True


class FakeUser:
    id = 7
    username = "alice"
    email = "alice@example.com"
    tinkoff_token = None

    @property
    def has_tinkoff_token(self):
        return bool((self.tinkoff_token or "").strip())

    @property
    def tinkoff_token_masked(self):
        return mask_secret(self.tinkoff_token)


def test_token_update_rejects_too_short_token():
    with pytest.raises(ValidationError):
        TinkoffTokenUpdate(tinkoff_token="short")


def test_token_update_validates_before_saving(monkeypatch):
    user = FakeUser()
    db = FakeDb()
    validate_calls = []

    def fake_validate_tinkoff_token(token, use_sandbox):
        validate_calls.append((token, use_sandbox))

    monkeypatch.setattr(routes_auth, "validate_tinkoff_token", fake_validate_tinkoff_token)

    result = routes_auth.update_tinkoff_token(
        payload=TinkoffTokenUpdate(tinkoff_token="  token-1234567890  "),
        db=db,
        current_user=user,
    )

    assert db.committed is True
    assert validate_calls == [("token-1234567890", routes_auth.settings.USE_SANDBOX)]
    assert user.tinkoff_token != "token-1234567890"
    assert user.tinkoff_token.startswith(ENCRYPTED_PREFIX)
    assert result == {
        "status": "ok",
        "has_tinkoff_token": True,
        "tinkoff_token_masked": "to***7890",
    }


def test_user_response_never_exposes_raw_tinkoff_token():
    user = FakeUser()
    user.tinkoff_token = "token-raw-secret"

    payload = UserResponse.model_validate(user).model_dump()

    assert payload["has_tinkoff_token"] is True
    assert payload["tinkoff_token_masked"] == "to***cret"
    assert "tinkoff_token" not in payload


def test_tinkoff_enum_name_returns_stable_account_status():
    class FakeEnum:
        name = "ACCOUNT_STATUS_OPEN"

        def __str__(self):
            return "2"

    assert tinkoff_client._enum_name(FakeEnum()) == "ACCOUNT_STATUS_OPEN"


def test_format_portfolio_uses_broker_expected_yield(monkeypatch):
    monkeypatch.setattr(routes_trade, "get_average_buy_price", lambda *_args: 20.0)

    formatted = routes_trade.format_portfolio(
        {
            "status": "success",
            "portfolio": {
                "summary": {"cash_balance": 100.0},
                "portfolio": [
                    {
                        "instrument_type": "share",
                        "figi": "FIGI1",
                        "ticker": "AAA",
                        "balance": 10,
                        "price": 12,
                        "value": 120,
                        "expected_yield": 20,
                        "currency": "RUB",
                    }
                ],
            },
        },
        user_id=1,
    )

    assert formatted["total_value"] == 220.0
    assert formatted["total_profit"] == 20.0
    assert formatted["total_profit_percent"] == 20.0
    assert formatted["positions"][0]["average_price"] == 10.0
    assert formatted["positions"][0]["expected_yield_percent"] == 20.0


class EmptyQuery:
    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def all(self):
        return []


class EmptyDb:
    def query(self, *_args):
        return EmptyQuery()


class ForecastQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self.rows


class ForecastDb:
    def __init__(self, forecasts):
        self.forecasts = forecasts

    def query(self, *_args):
        return ForecastQuery(self.forecasts)


def make_forecast(**overrides):
    defaults = {
        "id": 1,
        "figi": "BBG004730N88",
        "ticker": "SBER",
        "horizon": "1h",
        "model_type": "svr",
        "model_type_effective": "svr",
        "hyperparam_mode": "auto",
        "model_params": {"account_id": "acc-new"},
        "metrics": {"MAE": 1.0, "RMSE": 2.0, "R2": 0.5, "train_samples": 120},
        "current_price": 100.0,
        "predicted_price": 99.0,
        "price_delta_percent": -1.0,
        "recommendation": "SELL",
        "created_at": datetime(2026, 1, 1, 12, 0, 0),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_model_quality_filters_forecasts_by_account_id():
    forecasts = [
        make_forecast(id=1, model_params={"account_id": "acc-new"}, recommendation="SELL"),
        make_forecast(id=2, model_params={"account_id": "old"}, recommendation="BUY_OPTIONAL"),
        make_forecast(id=3, model_params={}, recommendation="WAIT"),
        make_forecast(id=4, model_params=None, recommendation="HOLD"),
    ]

    result = routes_analytics._model_quality(ForecastDb(forecasts), user_id=7, account_id="acc-new")

    assert result["total_forecasts"] == 1
    assert result["effective_distribution"] == {"svr": 1}
    assert result["recommendation_distribution"] == {"SELL": 1}
    assert [item["id"] for item in result["recent_forecasts"]] == [1]
    assert result["recent_forecasts"][0]["account_id"] == "acc-new"


def test_model_quality_without_account_keeps_full_user_history():
    forecasts = [
        make_forecast(id=1, model_params={"account_id": "acc-new"}),
        make_forecast(id=2, model_params={"account_id": "old"}),
        make_forecast(id=3, model_params={}),
        make_forecast(id=4, model_params=None),
    ]

    result = routes_analytics._model_quality(ForecastDb(forecasts), user_id=7)

    assert result["total_forecasts"] == 4
    assert [item["id"] for item in result["recent_forecasts"]] == [1, 2, 3, 4]
    assert [item["account_id"] for item in result["recent_forecasts"]] == ["acc-new", "old", None, None]


def test_analytics_overview_returns_empty_shapes(monkeypatch):
    seen_portfolio_kwargs = {}
    seen_bot_kwargs = {}
    seen_history_kwargs = {}
    seen_model_quality_kwargs = {}

    def fake_get_portfolio(**kwargs):
        seen_portfolio_kwargs.update(kwargs)
        return {"status": "success", "portfolio": {"summary": {}, "portfolio": []}}

    def fake_bot_analytics(*_args, **kwargs):
        seen_bot_kwargs.update(kwargs)
        return {
            "total_trades": 0,
            "closed_trades": 0,
            "open_trades": 0,
            "scheduled_auto_sells": 0,
            "failed_trades": 0,
            "realized_pnl": 0.0,
            "realized_pnl_percent": 0.0,
            "win_rate": 0.0,
            "avg_trade_return_percent": 0.0,
            "best_trade_percent": 0.0,
            "worst_trade_percent": 0.0,
            "by_model": {},
        }

    def fake_recent_bot_trades(*_args, **kwargs):
        seen_history_kwargs.update(kwargs)
        return []

    def fake_model_quality(*_args, **kwargs):
        seen_model_quality_kwargs.update(kwargs)
        return {
            "total_forecasts": 0,
            "rows": [],
            "effective_distribution": {},
            "recommendation_distribution": {},
            "horizon_distribution": {},
            "recent_forecasts": [],
        }

    monkeypatch.setattr(
        routes_analytics,
        "get_portfolio",
        fake_get_portfolio,
    )
    monkeypatch.setattr(
        routes_analytics,
        "calculate_bot_trade_analytics",
        fake_bot_analytics,
    )
    monkeypatch.setattr(routes_analytics, "_recent_bot_trades", fake_recent_bot_trades)
    monkeypatch.setattr(routes_analytics, "_model_quality", fake_model_quality)

    result = routes_analytics.overview(db=EmptyDb(), current_user=FakeUser(), account_id="acc-1")

    assert seen_portfolio_kwargs["account_id"] == "acc-1"
    assert seen_bot_kwargs["account_id"] == "acc-1"
    assert seen_history_kwargs["account_id"] == "acc-1"
    assert seen_model_quality_kwargs["account_id"] == "acc-1"
    assert result["filters"]["account_id"] == "acc-1"
    assert result["data_scope"]["portfolio"] == "selected_account"
    assert result["data_scope"]["bot_trades"] == "selected_account"
    assert result["data_scope"]["model_forecasts"] == "selected_account"
    assert result["portfolio"]["total_value"] == 0.0
    assert result["portfolio"]["positions"] == []
    assert result["manual_trades"]["total_trades"] == 0
    assert result["bot_history"] == []


def test_risk_warnings_do_not_count_failed_ml_when_filtered_analytics_has_none():
    portfolio = {
        "total_value": 1000.0,
        "cash_balance": 1000.0,
        "total_stocks_value": 0.0,
        "positions": [],
    }
    model_quality = {"rows": []}
    backtests = {"total_backtests": 0}

    clean = routes_analytics._risk_warnings(
        portfolio,
        {"failed_trades": 0, "closed_trades": 0, "win_rate": 0, "scheduled_auto_sells": 0},
        model_quality,
        backtests,
    )
    failed = routes_analytics._risk_warnings(
        portfolio,
        {"failed_trades": 2, "closed_trades": 0, "win_rate": 0, "scheduled_auto_sells": 0},
        model_quality,
        backtests,
    )

    assert all(warning.get("metric") != "2" for warning in clean)
    assert all("backtest" not in str(warning.get("title", "")).lower() for warning in clean)
    assert any(warning.get("metric") == "2" and warning.get("severity") == "warning" for warning in failed)
