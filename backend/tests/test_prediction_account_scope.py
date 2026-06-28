from types import SimpleNamespace

import numpy as np

from app.models import backtest_result, bot_trade, ml_model, model_forecast, stock, training_session  # noqa: F401
from app.schemas.model import ForecastRequest
from app.services import prediction_service
from app.services.recommendation_service import PortfolioPosition


class FakeDb:
    def add(self, obj):
        self.added = obj

    def commit(self):
        pass

    def refresh(self, obj):
        obj.id = 77


def test_forecast_uses_account_id_for_position_recommendation(monkeypatch):
    seen = {}

    monkeypatch.setattr(
        prediction_service,
        "_load_candles",
        lambda *_args, **_kwargs: [SimpleNamespace(close=100.0), SimpleNamespace(close=100.0)],
    )
    monkeypatch.setattr(prediction_service, "validate_min_samples", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        prediction_service,
        "build_features_for_forecast",
        lambda *_args, **_kwargs: SimpleNamespace(
            X=np.array([[1.0], [2.0]]),
            y=np.array([100.0, 100.0]),
            next_features=np.array([[3.0]]),
            feature_names=["close_lag_1"],
        ),
    )
    monkeypatch.setattr(prediction_service, "_resolve_params", lambda *_args, **_kwargs: {"svr": {}, "gpr": {}, "adaptive": {}})
    monkeypatch.setattr(
        prediction_service,
        "_predict_by_model",
        lambda *_args, **_kwargs: (99.0, {"MAE": 1.0, "RMSE": 1.0, "R2": 0.0}, "svr"),
    )
    monkeypatch.setattr(prediction_service, "get_current_price", lambda *_args, **_kwargs: 100.0)
    monkeypatch.setattr(prediction_service, "get_lot_size", lambda *_args, **_kwargs: 10)

    def fake_position(user_id, figi, account_id=None):
        seen["user_id"] = user_id
        seen["figi"] = figi
        seen["account_id"] = account_id
        return PortfolioPosition(has_position=False, quantity=0, average_buy_price=0, cash_balance=1_000_000)

    monkeypatch.setattr(prediction_service, "get_portfolio_position", fake_position)

    result = prediction_service.build_forecast(
        db=FakeDb(),
        user_id=1,
        request=ForecastRequest(
            figi="bbg004730n88",
            ticker="SBER",
            account_id="acc-new",
            source="popular",
            horizon="1h",
            model_type="svr",
        ),
    )

    assert seen == {"user_id": 1, "figi": "BBG004730N88", "account_id": "acc-new"}
    assert result["account_id"] == "acc-new"
    assert result["model_params"]["account_id"] == "acc-new"
    assert result["recommendation"]["has_position"] is False
    assert result["recommendation"]["action"] == "DO_NOT_BUY"
